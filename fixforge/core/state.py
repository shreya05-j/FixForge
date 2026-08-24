from typing import TypedDict, List, Dict, Any, Optional

class GraphState(TypedDict):
    issue_id: str
    github_url: str
    issue_description: str
    repo_path: str
    context_files: List[str]
    retrieved_code: str
    diagnosis: str
    severity: int
    proposed_patch: str
    patch_diff: str
    verification_logs: str
    verification_success: bool
    confidence_score: float
    report_markdown: str
    current_step: str
    iteration_count: int
