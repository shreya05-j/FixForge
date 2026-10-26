"""
test_persistence_stage4.py — Stage 4 Gate Tests.

Verifies:
1. After a real run, child rows are written into SQLite:
   - AgentAttempt (one per retry iteration)
   - DiagnosisRecord (classification, severity, root cause/diff trees)
   - ConfidenceMetric (overall, compilation, test_pass, semantic_preservation)
2. GET /api/sessions/{id} returns the full normalized breakdown matching the DB rows.
3. The failure case persists readable error records in all child tables and marks status='failed'.
"""

import uuid
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import ReviewSession, AgentAttempt, DiagnosisRecord, ConfidenceMetric
from db.session import AsyncSessionLocal, engine, Base
from api.routes.sessions import run_repair_workflow, get_session


@pytest.mark.asyncio
async def test_gate_stage4_persistence_matching():
    """
    Gate: Run a workflow, print the rows from each table and the JSON from
    GET /api/sessions/{id}. Verify they match completely.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_id = uuid.uuid4()

    # Create initial pending session
    async with AsyncSessionLocal() as db:
        sess = ReviewSession(
            id=session_id,
            repo_url="https://github.com/pallets/flask/issues/5012",
            branch="main",
            status="pending"
        )
        db.add(sess)
        await db.commit()

    initial_state = {
        "repo_name": "pallets/flask",
        "repo_url": "https://github.com/pallets/flask/issues/5012",
        "branch": "main",
        "issue_id": "5012",
        "issue_title": "Fix TypeError on invalid cookie encoding",
        "issue_body": "Cookies with invalid bytes crash request parsing.",
        "target_files": ["flask/wrappers.py"],
        "plan": "Sanitize cookie header before decoding",
        "retrieved_ast_context": {"functions": ["def parse_cookie(header): pass"]},
        "historical_fix_context": [{"document": "Cookie fix", "distance": 0.10}],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Invalid byte in cookie header raises TypeError",
        "failure_category": "Runtime Error",
        "severity": "Medium",
        "candidate_diff": """--- a/flask/wrappers.py
+++ b/flask/wrappers.py
@@ -10,2 +10,4 @@
 def parse_cookie(header):
+    if not header:
+        return {}
     return header.split(';')
""",
        "test_results": {},
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": "running",
        "attempt_history": []
    }

    # Simulate 2 attempts (Attempt 1 failed, Attempt 2 passed)
    sandbox_responses = [
        {
            "status": "failed",
            "passed": False,
            "exit_code": 1,
            "stdout": "FAILED tests/test_cookies.py::test_cookie_encoding",
            "stderr": "TypeError: unexpected byte"
        },
        {
            "status": "passed",
            "passed": True,
            "exit_code": 0,
            "stdout": "tests/test_cookies.py ...\n3 passed in 0.04s",
            "stderr": ""
        }
    ]

    fixer_outputs = [
        {"candidate_diff": "--- a/flask/wrappers.py\n+++ b/flask/wrappers.py\n@@ -1 +1 @@\n-old\n+temp\n", "status": "fixer_completed"},
        {"candidate_diff": "--- a/flask/wrappers.py\n+++ b/flask/wrappers.py\n@@ -10,2 +10,4 @@\n def parse_cookie(header):\n+    if not header:\n+        return {}\n     return header.split(';')\n", "status": "fixer_completed"}
    ]

    async def mock_fixer(state):
        idx = min(state.get("retry_count", 0), len(fixer_outputs) - 1)
        return fixer_outputs[idx]

    with patch("graph.nodes.run_planner", new_callable=AsyncMock) as mock_p, \
         patch("graph.nodes.run_diagnoser", new_callable=AsyncMock) as mock_d, \
         patch("graph.nodes.run_fixer", side_effect=mock_fixer), \
         patch("agents.verifier.run_in_sandbox", side_effect=sandbox_responses), \
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock):

        mock_p.return_value = {
            "plan": "Sanitize cookie header before decoding",
            "target_files": ["flask/wrappers.py"],
            "status": "planner_completed"
        }
        mock_d.return_value = {
            "diagnosis_summary": "Invalid byte in cookie header raises TypeError",
            "failure_category": "Runtime Error",
            "severity": "Medium",
            "status": "diagnoser_completed"
        }

        await run_repair_workflow(session_id, initial_state)

    # -------------------------------------------------------------------------
    # 1. READ RAW DATABASE ROWS
    # -------------------------------------------------------------------------
    async with AsyncSessionLocal() as db:
        # A. ReviewSession
        res = await db.execute(select(ReviewSession).where(ReviewSession.id == session_id))
        db_sess = res.scalars().first()
        assert db_sess is not None

        # B. AgentAttempt rows
        res = await db.execute(select(AgentAttempt).where(AgentAttempt.session_id == session_id).order_by(AgentAttempt.attempt_number))
        db_attempts = res.scalars().all()

        # C. DiagnosisRecord
        res = await db.execute(select(DiagnosisRecord).where(DiagnosisRecord.session_id == session_id))
        db_diag = res.scalars().first()
        assert db_diag is not None

        # D. ConfidenceMetric
        res = await db.execute(select(ConfidenceMetric).where(ConfidenceMetric.session_id == session_id))
        db_metric = res.scalars().first()
        assert db_metric is not None

        # ---------------------------------------------------------------------
        # 2. CALL API GET /api/sessions/{session_id}
        # ---------------------------------------------------------------------
        api_json = await get_session(str(session_id), db)

    # -------------------------------------------------------------------------
    # PRINT RAW DATABASE ROWS AS GATE PROOF
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STAGE 4 GATE PROOF: RAW DATABASE ROWS")
    print("=" * 70)
    print(f"[Table: review_sessions]")
    print(f"  id:         {db_sess.id}")
    print(f"  status:     {db_sess.status}")
    print(f"  repo_url:   {db_sess.repo_url}")
    print(f"  branch:     {db_sess.branch}")

    print(f"\n[Table: diagnosis_records]")
    print(f"  id:                     {db_diag.id}")
    print(f"  failure_classification: {db_diag.failure_classification}")
    print(f"  severity_rating:        {db_diag.severity_rating}")
    print(f"  ast_context:            {db_diag.ast_context}")
    print(f"  diff_trees:             {db_diag.diff_trees}")

    print(f"\n[Table: confidence_metrics]")
    print(f"  id:                          {db_metric.id}")
    print(f"  overall_score:               {db_metric.overall_score}")
    print(f"  compilation_confidence:      {db_metric.compilation_confidence}")
    print(f"  test_pass_confidence:        {db_metric.test_pass_confidence}")
    print(f"  semantic_preservation_score: {db_metric.semantic_preservation_score}")

    print(f"\n[Table: agent_attempts ({len(db_attempts)} rows)]")
    for att in db_attempts:
        print(f"  Attempt #{att.attempt_number}: status={att.status}, patch_diff={att.patch_diff[:35].strip()}..., logs={att.test_logs[:40].strip()}...")

    print("\n" + "=" * 70)
    print("STAGE 4 GATE PROOF: GET /api/sessions/{id} JSON OUTPUT")
    print("=" * 70)
    import json
    # Print formatted JSON representation of API response
    api_copy = dict(api_json)
    api_copy["created_at"] = str(api_copy["created_at"])
    api_copy["updated_at"] = str(api_copy["updated_at"])
    attempts_list = api_copy.get("attempts")
    if isinstance(attempts_list, list):
        for att in attempts_list:
            if isinstance(att, dict) and "created_at" in att:
                att["created_at"] = str(att["created_at"])
    print(json.dumps(api_copy, indent=2))

    # -------------------------------------------------------------------------
    # 3. VERIFY ROWS AND API RESPONSE MATCH EXACTLY
    # -------------------------------------------------------------------------
    assert str(db_sess.id) == api_json["id"]
    assert str(db_sess.status) == api_json["status"]
    assert str(db_sess.repo_url) == api_json["repository"]
    assert str(db_sess.branch) == api_json["branch"]

    # Diagnosis matches
    assert db_diag is not None
    assert api_json["diagnosis"] is not None
    assert db_diag.failure_classification == api_json["diagnosis"]["failure_classification"]
    assert db_diag.severity_rating == api_json["diagnosis"]["severity_rating"]
    assert db_diag.ast_context == api_json["diagnosis"]["ast_context"]
    assert db_diag.diff_trees == api_json["diagnosis"]["diff_trees"]

    # Metrics match
    assert db_metric is not None
    assert api_json["metrics"] is not None
    assert db_metric.overall_score == api_json["metrics"]["overall_score"]
    assert db_metric.compilation_confidence == api_json["metrics"]["compilation_confidence"]
    assert db_metric.test_pass_confidence == api_json["metrics"]["test_pass_confidence"]
    assert db_metric.semantic_preservation_score == api_json["metrics"]["semantic_preservation_score"]

    # Attempts match
    assert len(db_attempts) == 2
    assert len(api_json["attempts"]) == 2
    for i in range(len(db_attempts)):
        assert db_attempts[i].attempt_number == api_json["attempts"][i]["attempt_number"]
        assert db_attempts[i].status == api_json["attempts"][i]["status"]
        assert db_attempts[i].patch_diff == api_json["attempts"][i]["patch_diff"]
        assert db_attempts[i].test_logs == api_json["attempts"][i]["test_logs"]


@pytest.mark.asyncio
async def test_gate_stage4_failure_case_persists_readable_error():
    """
    Gate: Persist the failure case too. A failed run must leave a readable error record
    in ReviewSession, AgentAttempt, DiagnosisRecord, and ConfidenceMetric.
    """
    session_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        sess = ReviewSession(
            id=session_id,
            repo_url="https://github.com/mock/failure_repo",
            branch="main",
            status="pending"
        )
        db.add(sess)
        await db.commit()

    initial_state = {
        "repo_name": "mock/failure_repo",
        "repo_url": "https://github.com/mock/failure_repo",
        "branch": "main",
        "issue_id": "999",
        "issue_title": "Fatal crash trigger",
        "issue_body": "This run is designed to fail abruptly.",
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

    # Simulate an unexpected pipeline crash
    with patch("api.routes.sessions.build_workflow", side_effect=RuntimeError("Docker daemon connection abruptly terminated")):
        await run_repair_workflow(session_id, initial_state)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ReviewSession).where(ReviewSession.id == session_id))
        db_sess = res.scalars().first()
        assert db_sess is not None

        res = await db.execute(select(AgentAttempt).where(AgentAttempt.session_id == session_id))
        db_attempts = res.scalars().all()

        res = await db.execute(select(DiagnosisRecord).where(DiagnosisRecord.session_id == session_id))
        db_diag = res.scalars().first()
        assert db_diag is not None

        res = await db.execute(select(ConfidenceMetric).where(ConfidenceMetric.session_id == session_id))
        db_metric = res.scalars().first()
        assert db_metric is not None

        api_json = await get_session(str(session_id), db)

    print("\n[Stage 4 Gate Failure Case Proof]:")
    print(f"  Session Status:           {db_sess.status} (API: {api_json['status']})")
    print(f"  Attempt Test Logs:        {db_attempts[0].test_logs}")
    print(f"  Diagnosis Diff Trees:     {db_diag.diff_trees}")
    print(f"  Metrics Overall Score:    {db_metric.overall_score}")

    assert str(db_sess.status) == "failed"
    assert api_json["status"] == "failed"

    # Readable error preserved in attempt test logs
    assert len(db_attempts) == 1
    assert "Workflow failure: Docker daemon connection abruptly terminated" in str(db_attempts[0].test_logs)
    assert db_attempts[0].test_logs == api_json["attempts"][0]["test_logs"]

    # Readable error preserved in diagnosis diff_trees
    assert isinstance(db_diag.diff_trees, dict)
    assert "Docker daemon connection abruptly terminated" in str(db_diag.diff_trees.get("error", ""))
    assert db_diag.diff_trees == api_json["diagnosis"]["diff_trees"]

    # Confidence metric is 0.0
    assert getattr(db_metric, "overall_score") == 0.0
    assert api_json["metrics"]["overall_score"] == 0.0
