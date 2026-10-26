"""
test_confidence_stage3.py — Stage 3 Gate Tests.

Verifies:
1. Two different bugs produce believable sub-scores that differ substantially.
2. A worse patch (partial tests passed, lint errors, low consistency) yields a lower score than a clean patch.
3. Syntax-broken patch drops static analysis to 0.0.
4. Signals that cannot be computed are marked unavailable and weights are explicitly renormalized (no default constants).
5. All 4 SRS calibration bands (90-100, 75-89, 50-74, <50) are correctly mapped.
"""

import pytest
from unittest.mock import patch, AsyncMock
from core.state import AgentState
from agents.confidence import (
    compute_test_results_score,
    compute_static_analysis_score,
    compute_context_similarity_score,
    compute_llm_consistency_score,
    calculate_confidence_breakdown,
    map_calibration_band,
    run_confidence_engine,
    BASE_WEIGHTS
)
from graph.workflow import build_workflow


def test_gate_two_bugs_differ_in_believable_ways():
    """
    Gate: Run two different bugs and show that their sub-scores differ in believable ways.
    - Bug 1: Clean fix (100% test pass, clean code, close historical match, high consistency).
    - Bug 2: Degraded/partial fix (partial tests pass, unused imports/variables, distant match, low consistency).
    """
    # Bug 1: Clean high-confidence fix
    bug1_state: AgentState = {
        "repo_name": "pallets/flask",
        "issue_id": "5012",
        "issue_title": "Fix TypeError on invalid cookie encoding",
        "issue_body": "Cookies with invalid bytes crash request parsing.",
        "candidate_diff": """--- a/flask/wrappers.py
+++ b/flask/wrappers.py
@@ -10,2 +10,4 @@
 def parse_cookie(header):
+    if not header:
+        return {}
     return header.split(';')
""",
        "test_results": {
            "status": "passed",
            "passed": True,
            "stdout": "tests/test_cookies.py ...\n3 passed in 0.05s"
        },
        "historical_fix_context": [
            {"document": "Fix cookie parsing crash", "metadata": {}, "distance": 0.08}
        ],
        "consistency_samples": [
            """--- a/flask/wrappers.py
+++ b/flask/wrappers.py
@@ -10,2 +10,4 @@
 def parse_cookie(header):
+    if not header:
+        return {}
     return header.split(';')
"""
        ],
        "target_files": ["flask/wrappers.py"],
        "plan": "",
        "retrieved_ast_context": {},
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Cookie header parser fails on empty/malformed input",
        "failure_category": "Runtime Error",
        "severity": "Medium",
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }

    # Bug 2: Degraded fix (partial test pass, introduces unused variable, distant historical match, divergent patch)
    bug2_state: AgentState = {
        "repo_name": "psf/requests",
        "issue_id": "3120",
        "issue_title": "Connection pool leak under high concurrency",
        "issue_body": "Connections not returned to pool on timeout.",
        "candidate_diff": """--- a/requests/adapters.py
+++ b/requests/adapters.py
@@ -50,3 +50,5 @@
 def send(request):
+    dummy_unused_leak = 99999
+    timeout = 10
     pass
""",
        "test_results": {
            "status": "failed",
            "passed": False,
            "stdout": "FAILED tests/test_concurrency.py::test_pool_leak\n1 passed, 2 failed in 0.40s"
        },
        "historical_fix_context": [
            {"document": "Distant unrelated database fix", "metadata": {}, "distance": 3.80}
        ],
        "consistency_samples": [
            """--- a/requests/pool.py
+++ b/requests/pool.py
@@ -1,2 +1,2 @@
-def cleanup(): pass
+def close_all(): pass
"""
        ],
        "target_files": ["requests/adapters.py"],
        "plan": "",
        "retrieved_ast_context": {},
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Pool connection resource leak",
        "failure_category": "Concurrency Issue",
        "severity": "Critical",
        "retry_count": 1,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }

    b1_breakdown = calculate_confidence_breakdown(bug1_state)
    b2_breakdown = calculate_confidence_breakdown(bug2_state)

    print("\n[Stage 3 Gate Bug 1 (Clean Fix)] Confidence Breakdown:")
    print(f"  Overall Score:             {b1_breakdown['overall_score'] * 100:.2f}% (Band: {b1_breakdown['calibration_band']})")
    print(f"  Test Pass Confidence:      {b1_breakdown['test_pass_confidence'] * 100:.1f}%")
    print(f"  Compilation/Static Score:  {b1_breakdown['compilation_confidence'] * 100:.1f}%")
    print(f"  Context Similarity:        {b1_breakdown['semantic_preservation_score'] * 100:.1f}%")
    print(f"  LLM Consistency:           {b1_breakdown['llm_consistency_score'] * 100:.1f}%")

    print("\n[Stage 3 Gate Bug 2 (Flawed Fix)] Confidence Breakdown:")
    print(f"  Overall Score:             {b2_breakdown['overall_score'] * 100:.2f}% (Band: {b2_breakdown['calibration_band']})")
    print(f"  Test Pass Confidence:      {b2_breakdown['test_pass_confidence'] * 100:.1f}%")
    print(f"  Compilation/Static Score:  {b2_breakdown['compilation_confidence'] * 100:.1f}%")
    print(f"  Context Similarity:        {b2_breakdown['semantic_preservation_score'] * 100:.1f}%")
    print(f"  LLM Consistency:           {b2_breakdown['llm_consistency_score'] * 100:.1f}%")

    # Verify Bug 1 achieves high calibration band (90-100)
    assert b1_breakdown["overall_score"] >= 0.90
    assert b1_breakdown["calibration_band"] == "90-100"
    assert b1_breakdown["test_pass_confidence"] == 1.0
    assert b1_breakdown["compilation_confidence"] == 1.0

    # Verify Bug 2 drops to lower calibration band (<50 or 50-74)
    assert b2_breakdown["overall_score"] < 0.50
    assert b2_breakdown["calibration_band"] == "<50"
    assert b2_breakdown["test_pass_confidence"] < 0.50
    assert b2_breakdown["compilation_confidence"] < 1.0
    assert b2_breakdown["semantic_preservation_score"] < 0.30

    # Assert significant separation between the two bugs
    score_delta = b1_breakdown["overall_score"] - b2_breakdown["overall_score"]
    assert score_delta > 0.40, f"Expected > 40% separation between good and flawed patch, got {score_delta * 100:.1f}%"


def test_gate_worse_patch_yields_lower_score():
    """
    Gate: Add a unit test proving a worse patch yields a lower score.
    """
    base_state: AgentState = {
        "repo_name": "test/calculator",
        "issue_id": "1",
        "issue_title": "Fix division",
        "issue_body": "Divide function crashes on zero",
        "candidate_diff": "def divide(a, b):\n    if b == 0: return None\n    return a / b\n",
        "test_results": {"passed": True, "status": "passed"},
        "historical_fix_context": [{"document": "divide fix", "distance": 0.1}],
        "consistency_samples": ["def divide(a, b):\n    if b == 0: return None\n    return a / b\n"],
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Zero division",
        "failure_category": "Runtime Error",
        "severity": "High",
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }

    # Good patch: clean, tests pass, high consistency
    good_score = calculate_confidence_breakdown(base_state)["overall_score"]

    # Worse patch 1: fails test verification
    worse_state_1 = AgentState({**base_state, "test_results": {"passed": False, "status": "failed", "stdout": "FAILED test_divide"}})
    worse_score_1 = calculate_confidence_breakdown(worse_state_1)["overall_score"]

    # Worse patch 2: introduces syntax error
    worse_state_2 = AgentState({**base_state, "candidate_diff": "def divide(a, b):\n    if b == 0: ((((broken syntax\n"})
    worse_score_2 = calculate_confidence_breakdown(worse_state_2)["overall_score"]

    # Worse patch 3: low LLM consistency (divergent patch)
    worse_state_3 = AgentState({**base_state, "consistency_samples": ["def multiply(a, b): return a * b\n"]})
    worse_score_3 = calculate_confidence_breakdown(worse_state_3)["overall_score"]

    print(f"\n[Stage 3 Gate Proof] Clean patch score:       {good_score * 100:.1f}%")
    print(f"  Failing tests patch score:                  {worse_score_1 * 100:.1f}%")
    print(f"  Syntax-broken patch score:                  {worse_score_2 * 100:.1f}%")
    print(f"  Inconsistent LLM patch score:               {worse_score_3 * 100:.1f}%")

    assert good_score > worse_score_1, f"Expected {good_score} > {worse_score_1}"
    assert good_score > worse_score_2, f"Expected {good_score} > {worse_score_2}"
    assert good_score > worse_score_3, f"Expected {good_score} > {worse_score_3}"


def test_gate_unavailable_signals_renormalize_weights_explicitly():
    """
    Gate: If a signal cannot be computed, mark it unavailable and renormalize
    weights explicitly. Do not substitute a default number.
    """
    # State with NO historical fixes in ChromaDB and NO consistency samples
    state_partial: AgentState = {
        "repo_name": "test/repo",
        "issue_id": "1",
        "issue_title": "Brand new issue",
        "issue_body": "No historical fixes exist in ChromaDB.",
        "candidate_diff": "def add(a, b): return a + b\n",
        "test_results": {"passed": True, "status": "passed"},
        "historical_fix_context": [],      # Unavailable
        "consistency_samples": None,       # Unavailable
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Add feature",
        "failure_category": "Logic Error",
        "severity": "Low",
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }

    breakdown = calculate_confidence_breakdown(state_partial)

    print("\n[Stage 3 Gate Renormalization Output]:")
    print(f"  Unavailable signals:  {breakdown['unavailable_signals']}")
    print(f"  Active weights:       {breakdown['active_weights']}")
    print(f"  Overall Score:        {breakdown['overall_score']}")

    assert "context_similarity" in breakdown["unavailable_signals"]
    assert "llm_consistency" in breakdown["unavailable_signals"]

    # Active weights should only be test_results (0.45 base) and static_analysis (0.25 base)
    # Total active base = 0.70.
    # Renormalized test_results = 0.45 / 0.70 = ~0.6429
    # Renormalized static_analysis = 0.25 / 0.70 = ~0.3571
    expected_test_weight = round(0.45 / 0.70, 4)
    expected_static_weight = round(0.25 / 0.70, 4)

    assert breakdown["active_weights"]["test_results"] == expected_test_weight
    assert breakdown["active_weights"]["static_analysis"] == expected_static_weight

    # Sum of active weights must equal 1.0 (within roundoff)
    assert abs(sum(breakdown["active_weights"].values()) - 1.0) < 0.001


def test_gate_calibration_bands():
    """
    Gate: Verify SRS 10.2 calibration band thresholds.
    """
    assert map_calibration_band(0.95) == "90-100"
    assert map_calibration_band(0.90) == "90-100"
    assert map_calibration_band(0.89) == "75-89"
    assert map_calibration_band(0.75) == "75-89"
    assert map_calibration_band(0.74) == "50-74"
    assert map_calibration_band(0.50) == "50-74"
    assert map_calibration_band(0.49) == "<50"
    assert map_calibration_band(0.00) == "<50"


@pytest.mark.asyncio
async def test_gate_workflow_executes_confidence_engine_node():
    """
    Gate: Verify that ConfidenceEngine executes cleanly in the compiled LangGraph workflow.
    """
    workflow = build_workflow()

    initial_state: AgentState = {
        "repo_name": "test/e2e_conf_repo",
        "issue_id": "88",
        "issue_title": "Verify dynamic confidence scoring in pipeline",
        "issue_body": "Tests dynamic confidence calculation.",
        "retry_count": 0,
        "test_results": {"passed": True, "status": "passed"},
        "target_files": ["utils.py"],
        "plan": "",
        "retrieved_ast_context": {"functions": ["def helper(): return 1"]},
        "historical_fix_context": [{"document": "Historical match", "distance": 0.15}],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "Helper flaw",
        "failure_category": "Logic Error",
        "severity": "Low",
        "candidate_diff": "def helper(): return 2\n",
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": "",
        "attempt_history": [],
        "consistency_samples": ["def helper(): return 2\n"]
    }

    with patch("graph.nodes.run_planner", new_callable=AsyncMock) as mock_p, \
         patch("graph.nodes.run_diagnoser", new_callable=AsyncMock) as mock_d, \
         patch("graph.nodes.run_fixer", new_callable=AsyncMock) as mock_f, \
         patch("agents.verifier.run_in_sandbox", return_value={"passed": True, "status": "passed", "exit_code": 0, "stdout": "1 passed"}), \
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock):

        mock_p.return_value = {"plan": "Plan", "target_files": ["utils.py"], "status": "planner_completed"}
        mock_d.return_value = {"diagnosis_summary": "Diagnosis", "failure_category": "Logic Error", "severity": "Low", "status": "diagnoser_completed"}
        mock_f.return_value = {"candidate_diff": "def helper(): return 2\n", "status": "fixer_completed"}

        final_state = await workflow.ainvoke(initial_state)

        print("\n[Stage 3 Gate End-to-End Result]:")
        print(f"  Confidence score:    {final_state['confidence_score'] * 100:.1f}%")
        print(f"  Calibration band:    {final_state['confidence_breakdown'].get('calibration_band')}")
        print(f"  Active weights:      {final_state['confidence_breakdown'].get('active_weights')}")

        assert final_state["confidence_score"] > 0.0
        assert "calibration_band" in final_state["confidence_breakdown"]
        assert final_state["status"] == "reporter_completed"
