from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    repository: Dict[str, str]
    issue_id: str
    pr_id: Optional[str]
    issue_description: str
    stack_trace: str
    plan: str
    retrieved_context: str
    diagnosis: str
    failure_category: str
    severity: str
    diff: str
    test_results: str
    test_passed: bool
    retry_count: int
    confidence_score: float
    confidence_signals: Dict[str, float]
    status: str
