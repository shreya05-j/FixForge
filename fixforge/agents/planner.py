import logging
from core.state import AgentState
from core.llm import get_async_client
from core.llm_caller import call_structured_llm

async_llm_client = get_async_client()
from pydantic import BaseModel, Field
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class PlannerOutput(BaseModel):
    plan: str = Field(description="Step-by-step investigation strategy")
    target_files: List[str] = Field(description="List of target file paths to investigate")

async def run_planner(state: AgentState) -> Dict[str, Any]:
    """
    ForgePlanner: Evaluates issue to generate prioritized target files and search directives.
    """
    hint_info = ""
    if state.get("target_file"):
        hint_info += f"\nTarget File: {state.get('target_file')}"
    if state.get("target_hint"):
        hint_info += f"\nTarget Algorithm/Symbol Hint: {state.get('target_hint')}"

    prompt = f"Issue Title: {state.get('issue_title')}\nIssue Body: {state.get('issue_body')}\nTrace: {state.get('stack_trace')}{hint_info}"
    messages = [
        {"role": "system", "content": "You are a Principal Software Engineer planning a bug fix. Output a structured plan and list of files."},
        {"role": "user", "content": prompt}
    ]

    response, telemetry = await call_structured_llm(
        agent_name="Planner",
        response_model=PlannerOutput,
        messages=messages,
        temperature=0.0,
        client=async_llm_client
    )

    if response:
        plan_val = response.plan
        target_files_val = list(response.target_files)
    else:
        plan_val = "Fallback plan: Identify fault and patch."
        target_files_val = []

    if state.get("target_file") and state.get("target_file") not in target_files_val:
        target_files_val.insert(0, str(state.get("target_file")))

    return {
        'plan': plan_val,
        'target_files': target_files_val,
        'planner_telemetry': telemetry,
        'status': 'planner_completed'
    }

