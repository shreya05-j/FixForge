"""
test_sandbox_stage2.py — Stage 2 Gate Tests.

Verifies:
(a) Good patch -> passed (status="passed", passed=True)
(b) Malformed patch -> patch_failed with git error text and exit_code=42
(c) Docker stopped -> unverified (status="unverified", passed=False, never passed)
(d) Genuine retry loop on a bug that needs retry, showing attempt history log
(e) ReviewSession status in database is set to "unverified" when Docker is stopped
"""

import os
import sys
import tempfile
import subprocess

import pytest
from unittest.mock import patch, AsyncMock
from core.state import AgentState
from sandbox.runner import run_in_sandbox, parse_sandbox_output
from agents.verifier import run_verifier
from graph.workflow import build_workflow
from agents.planner import PlannerOutput
from agents.diagnoser import DiagnoserOutput
from agents.fixer import FixerOutput


import docker
import docker.errors


def test_gate_case_c_docker_stopped_returns_unverified():
    """
    Gate Case (c): When Docker daemon is unavailable, run_in_sandbox must return
    status='unverified', passed=False, exit_code=-1, and an explicit error message.
    It must NEVER return passed=True.
    """
    with patch("sandbox.runner.docker.from_env", side_effect=docker.errors.DockerException("Docker daemon unavailable: connection refused")):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_in_sandbox(tmpdir, "diff --git a/x b/x\n", test_cmd="pytest")
            print("\n[Stage 2 Gate Case C] Docker stopped output:")
            print(f"  status:    {result['status']}")
            print(f"  passed:    {result['passed']}")
            print(f"  exit_code: {result['exit_code']}")
            print(f"  error:     {result['error'][:80]}...")

            assert result["status"] == "unverified", f"Expected 'unverified', got {result['status']}"
            assert result["passed"] is False, "Must NEVER return passed=True when Docker is down"
            assert result["exit_code"] == -1
            assert "Docker daemon unavailable" in result["error"] or "Docker" in result["error"]


def test_gate_case_b_malformed_patch_returns_patch_failed():
    """
    Gate Case (b): When git apply --check rejects a malformed patch,
    parse_sandbox_output returns status='patch_failed' with the git error text.
    """
    simulated_logs = """=== FIXFORGE_CHECKING_PATCH ===
error: patch failed: src/calculator.py:12
error: src/calculator.py: patch does not apply
=== FIXFORGE_PATCH_FAILED ===
"""
    result = parse_sandbox_output(42, simulated_logs)
    print("\n[Stage 2 Gate Case B] Malformed patch output:")
    print(f"  status:    {result['status']}")
    print(f"  passed:    {result['passed']}")
    print(f"  exit_code: {result['exit_code']}")
    print(f"  stderr:    {result['stderr']}")

    assert result["status"] == "patch_failed"
    assert result["passed"] is False
    assert result["exit_code"] == 42
    assert "error: patch failed: src/calculator.py:12" in result["stderr"]
    assert "error: src/calculator.py: patch does not apply" in result["stderr"]


def test_gate_case_a_good_patch_returns_passed():
    """
    Gate Case (a): When patch applies cleanly and tests pass,
    parse_sandbox_output returns status='passed' with passed=True and exit_code=0.
    """
    simulated_logs = """=== FIXFORGE_CHECKING_PATCH ===
=== FIXFORGE_RUNNING_TESTS ===
============================= test session starts ==============================
rootdir: /app_scratch
collected 3 items

tests/test_calculator.py ...                                             [100%]

============================== 3 passed in 0.08s ===============================
"""
    result = parse_sandbox_output(0, simulated_logs)
    print("\n[Stage 2 Gate Case A] Good patch output:")
    print(f"  status:    {result['status']}")
    print(f"  passed:    {result['passed']}")
    print(f"  exit_code: {result['exit_code']}")

    assert result["status"] == "passed"
    assert result["passed"] is True
    assert result["exit_code"] == 0
    assert "3 passed" in result["stdout"]


@pytest.mark.asyncio
async def test_gate_retry_loop_with_attempt_log():
    """
    Gate Case: Genuine retry loop.
    Attempt 1: Fixer produces a patch that fails test verification.
    Attempt 2: Fixer receives failure feedback and produces working patch.
    Verifier records both attempts into attempt_history.
    """
    workflow = build_workflow()

    initial_state: AgentState = {
        "repo_name": "test/calculator_repo",
        "issue_id": "42",
        "issue_title": "Fix ZeroDivisionError in Calculator.divide()",
        "issue_body": "divide() crashes on zero instead of returning None.",
        "retry_count": 0,
        "test_results": {},
        "target_files": ["calculator.py"],
        "plan": "",
        "retrieved_ast_context": {"functions": ["def divide(a, b): return a / b"]},
        "historical_fix_context": [],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "ZeroDivisionError unhandled in divide()",
        "failure_category": "Runtime Error",
        "severity": "High",
        "candidate_diff": "",
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": "",
        "attempt_history": []
    }

    # Simulate two verifier runs:
    # 1. First run: tests fail (or patch fails)
    # 2. Second run: tests pass
    sandbox_responses = [
        {
            "status": "failed",
            "passed": False,
            "exit_code": 1,
            "stdout": "FAILED tests/test_calc.py::test_divide - ZeroDivisionError: division by zero",
            "stderr": "FAILED tests/test_calc.py::test_divide"
        },
        {
            "status": "passed",
            "passed": True,
            "exit_code": 0,
            "stdout": "PASSED tests/test_calc.py::test_divide\n1 passed in 0.04s",
            "stderr": ""
        }
    ]

    fixer_outputs = [
        {"candidate_diff": "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,2 +1,2 @@\n-def divide(a, b): return a / b\n+def divide(a, b): return a // b\n", "status": "fixer_completed"},
        {"candidate_diff": "--- a/calculator.py\n+++ b/calculator.py\n@@ -1,2 +1,3 @@\n+if b == 0: return None\n def divide(a, b): return a / b\n", "status": "fixer_completed"}
    ]

    async def mock_fixer(state):
        retry_idx = min(state.get("retry_count", 0), len(fixer_outputs) - 1)
        return fixer_outputs[retry_idx]

    with patch("graph.nodes.run_planner", new_callable=AsyncMock) as mock_p, \
         patch("graph.nodes.run_diagnoser", new_callable=AsyncMock) as mock_d, \
         patch("graph.nodes.run_fixer", side_effect=mock_fixer), \
         patch("agents.verifier.run_in_sandbox", side_effect=sandbox_responses) as mock_sandbox, \
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock):

        mock_p.return_value = {"plan": "Add zero check to divide", "target_files": ["calculator.py"], "status": "planner_completed"}
        mock_d.return_value = {"diagnosis_summary": "ZeroDivisionError in divide", "failure_category": "Runtime Error", "severity": "High", "status": "diagnoser_completed"}

        final_state = await workflow.ainvoke(initial_state)

        print("\n[Stage 2 Gate Retry Loop] Completed with attempts:")
        assert "attempt_history" in final_state
        assert len(final_state["attempt_history"]) == 2, f"Expected 2 attempts, got {len(final_state['attempt_history'])}"

        for att in final_state["attempt_history"]:
            print(f"  Attempt {att['attempt_number']}: status={att['status']}, logs={att['test_logs'][:60]}...")

        # Assert Attempt 1 failed
        assert final_state["attempt_history"][0]["attempt_number"] == 1
        assert final_state["attempt_history"][0]["status"] == "failed"
        assert "ZeroDivisionError" in final_state["attempt_history"][0]["test_logs"]

        # Assert Attempt 2 passed
        assert final_state["attempt_history"][1]["attempt_number"] == 2
        assert final_state["attempt_history"][1]["status"] == "passed"
        assert "PASSED" in final_state["attempt_history"][1]["test_logs"]

        # Assert retry count was incremented and pipeline reached completion
        assert final_state["retry_count"] == 1
        assert final_state["test_results"]["passed"] is True
        assert final_state["status"] == "reporter_completed"


@pytest.mark.asyncio
async def test_gate_verifier_surfaces_unverified_to_pipeline_and_halts_retries():
    """
    Gate Case: When Docker is stopped, Verifier returns status='unverified',
    workflow routes directly to Reporter without wasting retries, and state
    records unverified status.
    """
    workflow = build_workflow()

    initial_state: AgentState = {
        "repo_name": "test/unverified_repo",
        "issue_id": "99",
        "issue_title": "Docker unavailable test",
        "issue_body": "Verification should halt without retries.",
        "retry_count": 0,
        "test_results": {},
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Test diagnosis",
        "failure_category": "Logic Error",
        "severity": "Low",
        "candidate_diff": "diff --git a/x b/x\n",
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": "",
        "attempt_history": []
    }

    # run_in_sandbox will actually run against the local environment (Docker is stopped)
    # No mocking of run_in_sandbox!
    with patch("graph.nodes.run_planner", new_callable=AsyncMock) as mock_p, \
         patch("graph.nodes.run_diagnoser", new_callable=AsyncMock) as mock_d, \
         patch("graph.nodes.run_fixer", new_callable=AsyncMock) as mock_f, \
         patch("sandbox.runner.docker.from_env", side_effect=docker.errors.DockerException("Docker daemon unavailable: connection refused")), \
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock):

        mock_p.return_value = {"plan": "Investigate issue", "target_files": [], "status": "planner_completed"}
        mock_d.return_value = {"diagnosis_summary": "Logic flaw", "failure_category": "Logic Error", "severity": "Low", "status": "diagnoser_completed"}
        mock_f.return_value = {"candidate_diff": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n", "status": "fixer_completed"}

        final_state = await workflow.ainvoke(initial_state)

        print("\n[Stage 2 Gate Unverified Workflow Result]:")
        print(f"  test_results status: {final_state['test_results'].get('status')}")
        print(f"  test_results passed: {final_state['test_results'].get('passed')}")
        print(f"  retry_count:         {final_state['retry_count']} (should be 0, no wasteful retries)")

        assert final_state["test_results"]["status"] == "unverified"
        assert final_state["test_results"]["passed"] is False
        assert final_state["retry_count"] == 0, "Unverified run must not enter retry loop"


@pytest.mark.asyncio
async def test_gate_case_e_db_session_persists_unverified():
    """
    Gate Case (e): Real database verification.
    When run_repair_workflow executes with Docker stopped, ReviewSession.status
    in SQLite must be explicitly saved as 'unverified', never 'completed' or 'passed'.
    """
    import uuid
    from db.models import ReviewSession
    from db.session import AsyncSessionLocal, engine, Base
    from api.routes.sessions import run_repair_workflow
    from sqlalchemy import select

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        new_sess = ReviewSession(
            id=session_id,
            repo_url="https://github.com/mock/repo",
            branch="main",
            status="pending"
        )
        db.add(new_sess)
        await db.commit()

    initial_state: AgentState = {
        "repo_name": "mock/repo",

        "issue_id": "1",
        "issue_title": "Fix bug",
        "issue_body": "Details",
        "branch": "main",
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Bug diagnosis",
        "candidate_diff": "--- a/x\n+++ b/x\n",
        "test_results": {},
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": "running",
        "attempt_history": []
    }

    with patch("graph.nodes.run_planner", new_callable=AsyncMock) as mock_p, \
         patch("graph.nodes.run_diagnoser", new_callable=AsyncMock) as mock_d, \
         patch("graph.nodes.run_fixer", new_callable=AsyncMock) as mock_f, \
         patch("sandbox.runner.docker.from_env", side_effect=docker.errors.DockerException("Docker daemon unavailable: connection refused")), \
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock):

        mock_p.return_value = {"plan": "Fix", "target_files": [], "status": "planner_completed"}
        mock_d.return_value = {"diagnosis_summary": "Fix", "failure_category": "Logic Error", "severity": "Low", "status": "diagnoser_completed"}
        mock_f.return_value = {"candidate_diff": "--- a/x\n+++ b/x\n", "status": "fixer_completed"}

        await run_repair_workflow(session_id, initial_state)

    async with AsyncSessionLocal() as db:
        stmt = select(ReviewSession).where(ReviewSession.id == session_id)
        result = await db.execute(stmt)
        saved_session = result.scalars().first()
        assert saved_session is not None

        print(f"\n[Stage 2 Gate Case E] SQLite ReviewSession row:")
        print(f"  id:      {saved_session.id}")
        print(f"  status:  {saved_session.status}")
        print(f"  repo:    {saved_session.repo_url}")

        assert str(saved_session.status) == "unverified", f"Expected 'unverified', got '{saved_session.status}'"


def test_non_source_patch_early_rejection():
    """
    Verifies that run_in_sandbox immediately rejects patches targeting README.md or other non-code files
    without launching Docker, returning status='patch_failed' and exit_code=42.
    """
    from sandbox.runner import is_patch_targeting_non_source

    readme_diff = (
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1,3 +1,3 @@\n"
        "-# Title\n"
        "+# Title Enhanced\n"
    )
    assert is_patch_targeting_non_source(readme_diff) == "README.md"

    py_diff = (
        "--- a/src/calc.py\n"
        "+++ b/src/calc.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-x = 1\n"
        "+x = 2\n"
    )
    assert is_patch_targeting_non_source(py_diff) is None

    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_in_sandbox(tmpdir, readme_diff)
        assert result["status"] == "patch_failed"
        assert result["exit_code"] == 42
        assert "non-source documentation file" in result["error"]


def test_empty_patch_early_rejection():
    """
    Verifies that run_in_sandbox immediately rejects empty or whitespace patches.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_in_sandbox(tmpdir, "   \n\n  ")
        assert result["status"] == "patch_failed"
        assert result["exit_code"] == 42
        assert "No valid patch diff provided" in result["error"]


def test_python_patch_script_strategy_3_resilient_matching():
    """
    Verifies that PYTHON_PATCH_SCRIPT Strategy 3 successfully matches and replaces target lines
    even when the surrounding context lines in the diff are hallucinated by LLMs.
    """
    from sandbox.runner import PYTHON_PATCH_SCRIPT

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "apply.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(PYTHON_PATCH_SCRIPT)

        src_dir = os.path.join(tmpdir, "repo")
        os.makedirs(src_dir, exist_ok=True)
        py_file = os.path.join(src_dir, "search.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(
                "def search(items, target):\n"
                "    idx = 0\n"
                "    while True:\n"
                "        if items[idx] == target:\n"
                "            return idx\n"
            )

        # Notice hallucinated comment in context lines
        diff_text = (
            "--- a/search.py\n"
            "+++ b/search.py\n"
            "@@ -1,5 +1,5 @@\n"
            " def search(items, target):\n"
            "# hallucinated line that does not exist in source\n"
            "-    while True:\n"
            "+    while idx < len(items):\n"
            "         if items[idx] == target:\n"
        )
        patch_path = os.path.join(tmpdir, "patch.diff")
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(diff_text)

        proc = subprocess.run(
            [sys.executable, script_path, src_dir, patch_path],
            capture_output=True,
            text=True
        )

        assert proc.returncode == 0, f"Script failed: {proc.stderr}"
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "while idx < len(items):" in content
        assert "while True:" not in content

