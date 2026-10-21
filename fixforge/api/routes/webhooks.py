from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header, Depends
import hmac
import hashlib
import json
import logging
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from db.session import get_db
from db.models import ReviewSession
from api.routes.sessions import run_repair_workflow
from api.routes.streams import stream_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_signature(payload: bytes, signature: Optional[str]) -> bool:
    """Verifies GitHub HMAC SHA-256 signature if GITHUB_WEBHOOK_SECRET is configured."""
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True  # Skip validation if no secret is configured
    if not signature:
        return False
    mac = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Receives GitHub webhook events (issues, pull requests, and ping).
    Validates HMAC signature, persists the ReviewSession row into the database,
    broadcasts initial webhook events to stream_manager, and initiates the repair workflow.
    """
    payload_bytes = await request.body()
    if not verify_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Handle GitHub ping event
    if x_github_event == "ping" or "zen" in payload:
        return {"status": "pong", "message": "FixForge GitHub Webhook Active"}

    action = payload.get("action")
    is_pr = "pull_request" in payload or x_github_event == "pull_request"
    is_issue = "issue" in payload or x_github_event == "issues"

    # Listen for pull_request and issues events
    if action in ["opened", "synchronize", "reopened", "labeled"]:
        item_data = payload.get("pull_request") or payload.get("issue")
        if not item_data:
            return {"status": "ignored", "reason": "No pull_request or issue data found"}

        repo_info = payload.get("repository", {})
        repo_name = repo_info.get("full_name", "unknown/repo")
        repo_clone_url = repo_info.get("clone_url") or repo_info.get("html_url") or f"https://github.com/{repo_name}"

        issue_id = str(item_data.get("number", "1"))
        issue_title = item_data.get("title", "")
        issue_body = item_data.get("body", "") or ""

        # Determine target branch
        if is_pr and "pull_request" in payload:
            branch = payload["pull_request"].get("head", {}).get("ref") or repo_info.get("default_branch", "main")
        else:
            branch = repo_info.get("default_branch", "main")

        session_id = uuid.uuid4()
        session_id_str = str(session_id)

        try:
            new_session = ReviewSession(
                id=session_id,
                repo_url=repo_clone_url,
                branch=branch,
                status="running"
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
        except Exception as db_err:
            await db.rollback()
            logger.exception(f"Database write failed while initializing webhook session: {db_err}")
            raise HTTPException(status_code=500, detail="Database error initializing session")

        # Initialize stream manager session and publish webhook receipt event
        stream_manager.init_session(session_id_str)
        stream_manager.publish_event(session_id_str, "webhook_received", {
            "source": "github_webhook",
            "event": x_github_event or ("pull_request" if is_pr else "issue"),
            "action": action,
            "repo": repo_name,
            "issue_id": issue_id,
            "branch": branch
        })

        initial_state = {
            "repo_name": repo_name,
            "repo_url": repo_clone_url,
            "branch": branch,
            "issue_id": issue_id,
            "issue_title": issue_title or f"GitHub Event {action} #{issue_id}",
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
            "status": "running"
        }

        background_tasks.add_task(run_repair_workflow, session_id, initial_state)

        return {
            "status": "accepted",
            "session_id": session_id_str,
            "issue_id": issue_id,
            "repository": repo_name,
            "branch": branch
        }

    return {"status": "ignored", "action": action}
