"""
webhooks.py — GitHub webhook receiver.

Handles:
  - issue events: opened, reopened, labeled
  - pull_request events: opened, synchronize, reopened
  - issue_comment events: body contains /fix-bug command
  - ping: returns pong
  - everything else: ignored with reason

HMAC SHA-256 signature validated (401 on failure).
Duplicate deliveries (same X-GitHub-Delivery) are idempotent.
All accepted events create a ReviewSession row and call the SAME
run_repair_workflow path as POST /api/sessions/start.
"""

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header, Depends
import hmac
import hashlib
import json
import logging
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.config import settings
from db.session import get_db
from db.models import ReviewSession
from api.routes.sessions import run_repair_workflow
from api.routes.streams import stream_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory set of processed GitHub delivery IDs for idempotency.
# On restart the set is cleared — that is acceptable for duplicate-delivery protection.
_processed_deliveries: set = set()


def verify_signature(payload: bytes, signature: Optional[str]) -> bool:
    """Verifies GitHub HMAC SHA-256 signature.

    Returns True (skip validation) when no secret is configured.
    Returns False (reject) when secret is configured but signature is missing/wrong.
    """
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True  # No secret configured — skip validation
    if not signature:
        return False
    mac = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)


def _build_initial_state(
    repo_name: str,
    repo_url: str,
    branch: str,
    issue_id: str,
    issue_title: str,
    issue_body: str,
) -> dict:
    """Builds the shared initial AgentState for both webhook and /start paths."""
    return {
        "repo_name": repo_name,
        "repo_url": repo_url,
        "branch": branch,
        "issue_id": issue_id,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "stack_trace": None,
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "",
        "candidate_diff": "",
        "test_results": {},
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "attempt_history": [],
        "consistency_samples": [],
        "status": "running",
    }


async def _create_session_and_launch(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    repo_url: str,
    branch: str,
    repo_name: str,
    issue_id: str,
    issue_title: str,
    issue_body: str,
    delivery_id: Optional[str] = None,
) -> dict:
    """
    Creates a ReviewSession in DB and launches the repair workflow.
    Shared by all webhook event paths. Idempotent on delivery_id.
    """
    session_id = uuid.uuid4()
    session_id_str = str(session_id)

    # Probe active modes
    active_llm = "live" if ((settings.OPENAI_API_KEY and len(settings.OPENAI_API_KEY) > 5) or (settings.GROQ_API_KEY and len(settings.GROQ_API_KEY) > 10)) else "fallback"
    active_docker = "unavailable"

    try:
        import docker
        d_client = docker.from_env()
        d_client.ping()
        active_docker = "live"
    except Exception:
        active_docker = "unavailable"

    try:
        new_session = ReviewSession(
            id=session_id,
            repo_url=repo_url,
            branch=branch,
            status="running",
            llm_mode=active_llm,
            docker_mode=active_docker,
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
    except Exception as db_err:
        await db.rollback()
        logger.exception("DB write failed initializing webhook session: %s", db_err)
        raise HTTPException(status_code=500, detail="Database error initializing session")

    # Initialize SSE stream for this session
    stream_manager.init_session(session_id_str)
    stream_manager.publish_event(session_id_str, "webhook_received", {
        "source": "github_webhook",
        "repo": repo_name,
        "issue_id": issue_id,
        "branch": branch,
        "delivery_id": delivery_id,
    })

    initial_state = _build_initial_state(
        repo_name=repo_name,
        repo_url=repo_url,
        branch=branch,
        issue_id=issue_id,
        issue_title=issue_title,
        issue_body=issue_body,
    )

    background_tasks.add_task(run_repair_workflow, session_id, initial_state)
    logger.info("Webhook: session %s created for %s #%s", session_id_str, repo_name, issue_id)

    return {
        "status": "accepted",
        "session_id": session_id_str,
        "issue_id": issue_id,
        "repository": repo_name,
        "branch": branch,
    }


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Receives GitHub webhook events.

    Signature: HMAC SHA-256 validated — 401 on failure.
    Idempotency: duplicate X-GitHub-Delivery IDs are ignored.
    Supported events:
      - ping → pong
      - issues[opened|reopened|labeled] → create session
      - pull_request[opened|synchronize|reopened] → create session
      - issue_comment[created] with /fix-bug in body → create session
      - everything else → ignored with reason logged
    """
    payload_bytes = await request.body()

    # --- Signature validation ---
    if not verify_signature(payload_bytes, x_hub_signature_256):
        logger.warning("Webhook: invalid HMAC signature from delivery %s", x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid signature")

    # --- Idempotency ---
    if x_github_delivery and x_github_delivery in _processed_deliveries:
        logger.info("Webhook: duplicate delivery %s ignored", x_github_delivery)
        return {"status": "ignored", "reason": "duplicate_delivery", "delivery_id": x_github_delivery}
    if x_github_delivery:
        _processed_deliveries.add(x_github_delivery)

    try:
        payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # --- Ping ---
    if x_github_event == "ping" or "zen" in payload:
        return {"status": "pong", "message": "FixForge GitHub Webhook Active"}

    action = payload.get("action", "")
    repo_info = payload.get("repository", {})
    repo_name = repo_info.get("full_name", "unknown/repo")
    repo_url = repo_info.get("clone_url") or repo_info.get("html_url") or f"https://github.com/{repo_name}"

    # --- issue_comment /fix-bug trigger ---
    if x_github_event == "issue_comment" and action == "created":
        comment_body = payload.get("comment", {}).get("body", "")
        if "/fix-bug" not in comment_body:
            return {"status": "ignored", "reason": "issue_comment without /fix-bug trigger"}

        issue_data = payload.get("issue", {})
        issue_id = str(issue_data.get("number", "1"))
        issue_title = issue_data.get("title", "")
        issue_body = issue_data.get("body", "") or ""
        branch = repo_info.get("default_branch", "main")

        logger.info("Webhook: /fix-bug trigger in issue #%s of %s", issue_id, repo_name)
        return await _create_session_and_launch(
            db=db,
            background_tasks=background_tasks,
            repo_url=repo_url,
            branch=branch,
            repo_name=repo_name,
            issue_id=issue_id,
            issue_title=issue_title,
            issue_body=issue_body,
            delivery_id=x_github_delivery,
        )

    # --- issues and pull_request events ---
    HANDLED_ACTIONS = {"opened", "synchronize", "reopened", "labeled"}
    if action not in HANDLED_ACTIONS:
        logger.debug("Webhook: ignored event=%s action=%s", x_github_event, action)
        return {"status": "ignored", "reason": f"action '{action}' not handled", "event": x_github_event}

    is_pr = x_github_event == "pull_request" or "pull_request" in payload
    item_data = payload.get("pull_request") or payload.get("issue")
    if not item_data:
        return {"status": "ignored", "reason": "no pull_request or issue data found"}

    issue_id = str(item_data.get("number", "1"))
    issue_title = item_data.get("title", "")
    issue_body = item_data.get("body", "") or ""

    if is_pr and "pull_request" in payload:
        branch = payload["pull_request"].get("head", {}).get("ref") or repo_info.get("default_branch", "main")
    else:
        branch = repo_info.get("default_branch", "main")

    return await _create_session_and_launch(
        db=db,
        background_tasks=background_tasks,
        repo_url=repo_url,
        branch=branch,
        repo_name=repo_name,
        issue_id=issue_id,
        issue_title=issue_title,
        issue_body=issue_body,
        delivery_id=x_github_delivery,
    )
