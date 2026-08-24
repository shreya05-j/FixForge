import pytest
from unittest.mock import patch, AsyncMock
from core.state import AgentState
from graph.workflow import build_workflow
from agents.planner import PlannerOutput
from agents.diagnoser import DiagnoserOutput
from agents.fixer import FixerOutput

@pytest.mark.asyncio
async def test_end_to_end_repair():
    """
    End-to-End Seeded Test Harness
    Validates webhook payload ingestion mimicking, multi-agent LLM logic wrapping,
    Docker test sandbox loop termination, and confidence score generation.
    """
    workflow = build_workflow()
    
    # 1. Seeded initial state mimicking a Webhook Payload for a subtle KeyError
    initial_state: AgentState = {
        "repo_name": "test/repo",
        "issue_id": "1",
        "issue_title": "Fix KeyError in config loader",
        "issue_body": "There is a KeyError when config is missing 'host'.",
        "retry_count": 0,
        "test_results": {},
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "diagnosis_summary": "",
        "failure_category": "Runtime Error",
        "severity": "Medium",
        "candidate_diff": "",
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }
    
    # 2. Patch out the LLM calls and Docker executions to mimic a realistic pass
    with patch("agents.planner.async_llm_client.chat.completions.create", new_callable=AsyncMock) as mock_planner, \
         patch("agents.diagnoser.async_llm_client.chat.completions.create", new_callable=AsyncMock) as mock_diagnoser, \
         patch("agents.fixer.async_llm_client.chat.completions.create", new_callable=AsyncMock) as mock_fixer, \
         patch("agents.verifier.run_in_sandbox", return_value={"passed": True, "exit_code": 0, "stdout": "1 passed in 0.1s", "stderr": ""}), \
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock) as mock_post_comment:
        
        # Setup specific LLM structured mock returns
        mock_planner.return_value = PlannerOutput(plan="Find KeyError and patch with .get()", target_files=["config.py"])
        mock_diagnoser.return_value = DiagnoserOutput(diagnosis_summary="KeyError on missing dict key", failure_category="Logic Error", severity="Medium")
        mock_fixer.return_value = FixerOutput(candidate_diff="""--- a/config.py
+++ b/config.py
@@ -1,2 +1,2 @@
-def load_host(config): return config['host']
+def load_host(config): return config.get('host', 'localhost')
""")

        # 3. Execute the workflow asynchronously (End-to-End orchestration)
        final_state = await workflow.ainvoke(initial_state)
        
        # 4. Verify loop terminated cleanly and status is marked complete
        assert final_state["status"] == "reporter_completed", "Pipeline failed to terminate at Reporter."
        assert final_state["test_results"]["passed"] is True, "Test results did not verify as passed."
        assert final_state["retry_count"] == 0, "Pipeline entered unexpected retry loop."
        assert final_state["confidence_score"] > 0.0, "Confidence Engine failed to calculate a positive score."
        
        # 5. Verify GitHub Comment integration was accurately requested
        mock_post_comment.assert_called_once()
        args, kwargs = mock_post_comment.call_args
        assert args[0] == "test/repo"
        assert args[1] == "1"
        assert "FixForge Autonomous Repair Report" in args[2], "Generated report missing expected Markdown title."
