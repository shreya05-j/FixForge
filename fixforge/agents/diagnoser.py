import logging
from core.state import AgentState
from core.llm import get_async_client
from core.llm_caller import call_structured_llm

async_llm_client = get_async_client()
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any

logger = logging.getLogger(__name__)

class DiagnoserOutput(BaseModel):
    diagnosis_summary: str = Field(description="Detailed root cause summary and explanation.")
    failure_category: Literal["Syntax Error", "Logic Error", "Runtime Error", "Dependency Error", "Concurrency Issue", "Configuration Issue"]
    severity: Literal["Low", "Medium", "High", "Critical"]

async def run_diagnoser(state: AgentState) -> Dict[str, Any]:
    """
    ForgeDiagnoser: Identifies root cause and predicts severity using structured outputs.
    """
    ast_ctx = str(state.get('retrieved_ast_context', ''))[:3000]
    issue_b = state.get('issue_body', '')[:1500]
    prompt = f"Context: {ast_ctx}\nIssue: {issue_b}"
    messages = [
        {"role": "system", "content": "You are a Software Diagnoser. Determine the root cause, failure category, and severity from the provided context."},
        {"role": "user", "content": prompt}
    ]

    response, telemetry = await call_structured_llm(
        agent_name="Diagnoser",
        response_model=DiagnoserOutput,
        messages=messages,
        temperature=0.0,
        client=async_llm_client
    )

    if response:
        ds = response.diagnosis_summary
        fc = response.failure_category
        sev = response.severity
    else:
        ds = "Fallback diagnosis: Undetermined error due to LLM failure."
        fc = "Runtime Error"
        sev = "Medium"

    return {
        'diagnosis_summary': ds,
        'failure_category': fc,
        'severity': sev,
        'diagnoser_telemetry': telemetry,
        'status': 'diagnoser_completed'
    }
