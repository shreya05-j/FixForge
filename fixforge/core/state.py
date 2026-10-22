from typing import TypedDict, List, Dict, Any, Optional, Literal

class AgentState(TypedDict):
    repo_name: str
    repo_url: Optional[str]
    branch: Optional[str]
    issue_id: str
    issue_title: str
    issue_body: str
    stack_trace: Optional[str]
    target_files: List[str]
    plan: str
    retrieved_ast_context: Dict[str, Any]
    historical_fix_context: List[Dict[str, Any]]
    # Set by checkout helper before Retriever runs; None means checkout failed.
    repo_checkout_path: Optional[str]
    # True when Retriever fell back to keyword search instead of target_files.
    retriever_fallback: bool
    diagnosis_summary: str
    failure_category: Literal["Syntax Error", "Logic Error", "Runtime Error", "Dependency Error", "Concurrency Issue", "Configuration Issue"]
    severity: Literal["Low", "Medium", "High", "Critical"]
    candidate_diff: str
    test_results: Dict[str, Any]
    retry_count: int
    confidence_score: float
    confidence_breakdown: Dict[str, Any]
    status: str
    attempt_history: Optional[List[Dict[str, Any]]]
    consistency_samples: Optional[List[str]]
    planner_telemetry: Optional[Dict[str, Any]]
    diagnoser_telemetry: Optional[Dict[str, Any]]
    fixer_telemetry: Optional[Dict[str, Any]]
    consistency_telemetry: Optional[List[Dict[str, Any]]]
