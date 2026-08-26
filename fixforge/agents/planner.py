from core.state import AgentState
from core.llm import async_llm_client
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class PlannerOutput(BaseModel):
    plan: str = Field(description="Step-by-step investigation strategy")
    target_files: List[str] = Field(description="List of target file paths to investigate")

async def run_planner(state: AgentState) -> Dict[str, Any]:
    """
    ForgePlanner: Evaluates issue to generate prioritized target files and search directives using Llama 3.3.
    """
    print(f"Planning fix for issue {state.get('issue_id')}")
    prompt = f"Issue Title: {state.get('issue_title')}\nIssue Body: {state.get('issue_body')}\nTrace: {state.get('stack_trace')}"
    
    try:
        response = await async_llm_client.chat.completions.create(
            model="llama3-70b-8192", # Using supported Groq model identifier
            response_model=PlannerOutput,
            temperature=0.0, # Deterministic planning
            messages=[
                {"role": "system", "content": "You are a Principal Software Engineer planning a bug fix. Output a structured plan and list of files."},
                {"role": "user", "content": prompt}
            ],
            max_retries=3
        )
        plan_val = response.plan
        target_files_val = response.target_files
    except Exception as e:
        print(f"Error in Planner LLM: {e}")
        # Graceful fallback
        plan_val = "Fallback plan: Identify fault and patch."
        target_files_val = []
    
    return {
        'plan': plan_val,
        'target_files': target_files_val,
        'status': 'planner_completed'
    }
