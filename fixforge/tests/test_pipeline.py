import pytest
from core.state import AgentState
from graph.workflow import build_workflow
from memory.ast_parser import extract_functions_and_classes

def test_ast_parser():
    code = """
class TargetClass:
    def method(self):
        return True

def standalone_func():
    pass
    """
    result = extract_functions_and_classes(code)
    assert len(result["classes"]) == 1
    assert result["classes"][0]["name"] == "TargetClass"
    assert len(result["functions"]) == 2 # standalone_func and method

def test_langgraph_workflow_retry_loop():
    workflow = build_workflow()
    initial_state: AgentState = {
        "repo_name": "/tmp/mock",
        "issue_id": "123",
        "issue_title": "Test Issue",
        "issue_body": "This is a test.",
        "retry_count": 0,
        "test_results": {},
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "diagnosis_summary": "",
        "failure_category": "Logic Error",
        "severity": "Low",
        "candidate_diff": "",
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }
    
    # We will just run it and see if it completes
    # Since verifier is mocked, it will either pass or fail based on the logic in run_verifier
    final_state = workflow.invoke(initial_state)
    assert final_state["status"] == "reporter_completed"
