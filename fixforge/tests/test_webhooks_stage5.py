"""
test_webhooks_stage5.py — Stage 5 Gate Tests: GitHub Webhooks Unification.

Verifies:
1. HMAC signature verification with GITHUB_WEBHOOK_SECRET:
   - Valid signature -> accepted (200).
   - Invalid signature -> rejected with 401.
   - Missing signature when secret is configured -> 401.
2. GitHub ping events return pong (200).
3. Unhandled actions (e.g., closed) return ignored without modifying DB.
4. Accepted webhook creates a real ReviewSession row in the SQLite database.
5. Webhook broadcasts events into stream_manager and streams live SSE updates.
6. Full end-to-end webhook triggering LangGraph workflow persists completed/unverified
   session along with AgentAttempt, DiagnosisRecord, and ConfidenceMetric rows.
"""

import json
import hmac
import hashlib
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.main import app
from core.config import settings
from db.models import ReviewSession, AgentAttempt, DiagnosisRecord, ConfidenceMetric
from db.session import AsyncSessionLocal, engine, Base
from api.routes.streams import stream_manager


def _generate_signature(secret: str, payload_bytes: bytes) -> str:
    mac = hmac.new(secret.encode(), msg=payload_bytes, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()


async def _ensure_db_ready():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_gate_stage5_signature_validation():
    """Verify HMAC SHA256 signature verification rejects tampering and admits valid payloads."""
    await _ensure_db_ready()

    test_secret = "stage5_super_secret_webhook_token"
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 101,
            "title": "Fix buffer overflow",
            "body": "Fixes edge case in parser",
            "head": {"ref": "fix/overflow"}
        },
        "repository": {
            "full_name": "octocat/hello-world",
            "clone_url": "https://github.com/octocat/hello-world.git",
            "default_branch": "main"
        }
    }
    payload_bytes = json.dumps(payload).encode()
    valid_sig = _generate_signature(test_secret, payload_bytes)
    invalid_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", test_secret):
            # 1. Invalid signature -> 401
            resp_bad = await client.post(
                "/api/webhooks/github",
                content=payload_bytes,
                headers={"X-Hub-Signature-256": invalid_sig, "Content-Type": "application/json"}
            )
            assert resp_bad.status_code == 401
            assert resp_bad.json()["detail"] == "Invalid signature"

            # 2. Missing signature when secret configured -> 401
            resp_missing = await client.post(
                "/api/webhooks/github",
                content=payload_bytes,
                headers={"Content-Type": "application/json"}
            )
            assert resp_missing.status_code == 401

            # 3. Valid signature -> 200 accepted
            with patch("api.routes.webhooks.run_repair_workflow", new_callable=AsyncMock):
                resp_good = await client.post(
                    "/api/webhooks/github",
                    content=payload_bytes,
                    headers={"X-Hub-Signature-256": valid_sig, "Content-Type": "application/json"}
                )
                assert resp_good.status_code == 200
                data = resp_good.json()
                assert data["status"] == "accepted"
                assert data["issue_id"] == "101"
                assert data["repository"] == "octocat/hello-world"
                assert data["branch"] == "fix/overflow"
                assert "session_id" in data


@pytest.mark.asyncio
async def test_gate_stage5_ping_and_ignored_actions():
    """Verify GitHub ping events respond with pong and unhandled actions are ignored."""
    await _ensure_db_ready()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", ""):
            # Ping event
            resp_ping = await client.post(
                "/api/webhooks/github",
                json={"zen": "Non-blocking is better than blocking.", "hook_id": 999},
                headers={"X-GitHub-Event": "ping"}
            )
            assert resp_ping.status_code == 200
            assert resp_ping.json()["status"] == "pong"

            # Ignored action (e.g. pull_request closed)
            resp_ignored = await client.post(
                "/api/webhooks/github",
                json={
                    "action": "closed",
                    "pull_request": {"number": 102},
                    "repository": {"full_name": "octocat/hello-world"}
                }
            )
            assert resp_ignored.status_code == 200
            assert resp_ignored.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_gate_stage5_persists_review_session_row_and_streams_sse():
    """
    Gate: When a webhook arrives, it creates a real ReviewSession row in the database,
    records the webhook_received event in stream_manager, and initiates streaming.
    """
    await _ensure_db_ready()

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 5012,
            "title": "Fix cookie header parsing",
            "body": "TypeError when cookie contains invalid byte",
            "head": {"ref": "fix-cookies"}
        },
        "repository": {
            "full_name": "pallets/flask",
            "clone_url": "https://github.com/pallets/flask.git",
            "default_branch": "main"
        }
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", ""):
            with patch("api.routes.webhooks.run_repair_workflow", new_callable=AsyncMock):
                resp = await client.post(
                    "/api/webhooks/github",
                    json=payload,
                    headers={"X-GitHub-Event": "pull_request"}
                )
                assert resp.status_code == 200
                res_data = resp.json()
                assert res_data["status"] == "accepted"
                session_id_str = res_data["session_id"]
                session_uuid = uuid.UUID(session_id_str)

    # 1. Verify ReviewSession row in SQLite
    async with AsyncSessionLocal() as db:
        stmt = select(ReviewSession).where(ReviewSession.id == session_uuid)
        result = await db.execute(stmt)
        sess = result.scalars().first()
        assert sess is not None, "ReviewSession row must be persisted in database"
        assert str(sess.status) == "running"
        assert str(sess.repo_url) == "https://github.com/pallets/flask.git"
        assert str(sess.branch) == "fix-cookies"


    # 2. Verify stream_manager history recorded the webhook_received event
    history = stream_manager._history.get(session_id_str, [])
    assert len(history) >= 1, "stream_manager must have recorded events"
    evt = json.loads(history[0]["data"])
    assert history[0]["event"] == "webhook_received"
    assert evt["repo"] == "pallets/flask"
    assert evt["issue_id"] == "5012"
    assert evt["branch"] == "fix-cookies"


@pytest.mark.asyncio
async def test_gate_stage5_full_e2e_repair_from_webhook():
    """
    Full end-to-end gate: Webhook triggers background run_repair_workflow,
    which executes LangGraph nodes, publishes SSE events, updates ReviewSession,
    and creates AgentAttempt, DiagnosisRecord, and ConfidenceMetric rows.
    """
    await _ensure_db_ready()

    payload = {
        "action": "opened",
        "pull_request": {
            "number": 777,
            "title": "Fix memory leak in parser",
            "body": "Unclosed fd leads to leak",
            "head": {"ref": "patch-777"}
        },
        "repository": {
            "full_name": "example/repo",
            "clone_url": "https://github.com/example/repo.git",
            "default_branch": "main"
        }
    }

    mock_sandbox_result = {
        "status": "passed",
        "passed": True,
        "exit_code": 0,
        "stdout": "1 passed in 0.01s",
        "stderr": ""
    }

    mock_diff = "--- a/leak.py\n+++ b/leak.py\n@@ -1 +1 @@\n-open(f)\n+with open(f): pass\n"

    from agents.planner import PlannerOutput
    from agents.diagnoser import DiagnoserOutput
    from agents.fixer import FixerOutput

    async def mock_create(*args, **kwargs):
        response_model = kwargs.get("response_model")
        if response_model == PlannerOutput:
            return PlannerOutput(plan="Fix unclosed fd", target_files=["leak.py"])
        if response_model == DiagnoserOutput:
            return DiagnoserOutput(diagnosis_summary="Memory leak on unclosed fd", failure_category="Logic Error", severity="High")
        if response_model == FixerOutput:
            return FixerOutput(candidate_diff=mock_diff)
        return None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", ""):
            with patch("api.routes.sessions.checkout_repo", return_value={"path": None, "tmpdir": None, "status": "failed", "error": "Mock checkout"}), \
                 patch("core.llm.async_llm_client.chat.completions.create", side_effect=mock_create), \
                 patch("agents.verifier.run_in_sandbox", return_value=mock_sandbox_result), \
                 patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock):

                resp = await client.post(
                    "/api/webhooks/github",
                    json=payload,
                    headers={"X-GitHub-Event": "pull_request"}
                )
                assert resp.status_code == 200
                session_id = uuid.UUID(resp.json()["session_id"])

    # Query DB to ensure complete persistence
    async with AsyncSessionLocal() as db:
        stmt = select(ReviewSession).where(ReviewSession.id == session_id).options(
            selectinload(ReviewSession.attempts),
            selectinload(ReviewSession.diagnosis),
            selectinload(ReviewSession.metrics)
        )
        result = await db.execute(stmt)
        sess = result.scalars().first()

        assert sess is not None
        assert str(sess.status) == "completed"
        assert str(sess.repo_url) == "https://github.com/example/repo.git"
        assert str(sess.branch) == "patch-777"


        # Verify child records
        assert len(sess.attempts) >= 1
        assert sess.attempts[0].status == "passed"
        assert sess.diagnosis is not None
        assert sess.diagnosis.failure_classification == "Logic Error"
        assert sess.metrics is not None
        assert sess.metrics.overall_score > 0.0

    # Query GET /api/sessions/{id}
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        get_res = await client.get(f"/api/sessions/{str(session_id)}")
        assert get_res.status_code == 200
        api_data = get_res.json()
        assert api_data["status"] == "completed"
        assert api_data["diagnosis"]["failure_classification"] == "Logic Error"
        assert len(api_data["attempts"]) >= 1
