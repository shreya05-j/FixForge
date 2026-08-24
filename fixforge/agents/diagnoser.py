from core.state import AgentState
from core.llm import async_llm_client
from pydantic import BaseModel, Field
from typing import Literal

class DiagnoserOutput(BaseModel):
    diagnosis_summary: str = Field(description="Detailed root cause summary and explanation.")
    failure_category: Literal["Syntax Error", "Logic Error", "Runtime Error", "Dependency Error", "Concurrency Issue", "Configuration Issue"]
    severity: Literal["Low", "Medium", "High", "Critical"]

async def run_diagnoser(state: AgentState) -> AgentState:
    """
    ForgeDiagnoser: Identifies root cause and predicts severity using Llama 3.3 structured outputs.
    """
    prompt = f"Context: {state.get('retrieved_ast_context')}\nIssue: {state.get('issue_body')}"
    try:
        response = await async_llm_client.chat.completions.create(
            model="llama3-70b-8192",
            response_model=DiagnoserOutput,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "You are a Software Diagnoser. Determine the root cause, failure category, and severity from the provided context."},
                {"role": "user", "content": prompt}
            ],
            max_retries=3
        )
        state['diagnosis_summary'] = response.diagnosis_summary
        state['failure_category'] = response.failure_category
        state['severity'] = response.severity
    except Exception as e:
        print(f"Error in Diagnoser LLM: {e}")
        state['diagnosis_summary'] = "Fallback diagnosis: Undetermined error due to LLM failure."
        state['failure_category'] = "Runtime Error"
        state['severity'] = "Medium"
        
    state['status'] = 'diagnoser_completed'
    return state
