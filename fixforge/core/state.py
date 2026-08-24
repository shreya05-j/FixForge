from typing import TypedDict, List, Dict, Any, Optional, Literal

class AgentState(TypedDict):
    repo_name: str
    issue_id: str
    issue_title: str
    issue_body: str
    stack_trace: Optional[str]
    target_files: List[str]
    plan: str
    retrieved_ast_context: Dict[str, Any]
    historical_fix_context: List[Dict[str, Any]]
    diagnosis_summary: str
    failure_category: Literal["Syntax Error", "Logic Error", "Runtime Error", "Dependency Error", "Concurrency Issue", "Configuration Issue"]
    severity: Literal["Low", "Medium", "High", "Critical"]
    candidate_diff: str
    test_results: Dict[str, Any]
    retry_count: int
    confidence_score: float
    confidence_breakdown: Dict[str, float]
    status: str
