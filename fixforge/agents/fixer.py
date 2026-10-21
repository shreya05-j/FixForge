from core.state import AgentState
from core.llm import async_llm_client
from pydantic import BaseModel, Field

from typing import Dict, Any

class FixerOutput(BaseModel):
    candidate_diff: str = Field(description="Clean git unified diff string addressing the issue. Must start with --- and +++")

async def run_fixer(state: AgentState) -> Dict[str, Any]:
    """
    ForgeFixer: Synthesizes unified diff using diagnostic report and retrieved code. Uses Qwen for coding.
    """
    test_results = state.get('test_results', {})
    failure_feedback = ""
    if test_results:
        if test_results.get('status') == 'patch_failed':
            failure_feedback = f"\n[CRITICAL FAILURE] Previous patch rejected by git apply --check:\n{test_results.get('error') or test_results.get('stderr')}\nEnsure file paths and hunk headers match the repository exactly."
        elif not test_results.get('passed', False):
            failure_feedback = f"\n[TEST FAILURE] Previous patch failed test verification:\n{test_results.get('stdout') or test_results.get('stderr')}"

    prompt = (
        f"Diagnosis: {state.get('diagnosis_summary')}\n"
        f"Context: {state.get('retrieved_ast_context')}\n"
        f"Previous test results: {test_results}"
        f"{failure_feedback}\n"
        "Generate a valid git unified diff to fix the issue."
    )
    
    # Optional: adjust temperature based on retry iteration for self-consistency
    temp = 0.0 if state.get('retry_count', 0) == 0 else 0.2
    
    try:
        # Currently Groq has llama3, Mixtral, Gemma. For actual Qwen 2.5 Coder 32B, OpenRouter is generally used, 
        # but here we parameterize the call using Instructor.
        # Fallback to llama3-70b-8192 if Qwen is not available on Groq directly.
        response = await async_llm_client.chat.completions.create(
            model="llama3-70b-8192", 
            response_model=FixerOutput,
            temperature=temp,
            messages=[
                {"role": "system", "content": "You are a master developer. Output ONLY a valid git unified diff inside the candidate_diff field."},
                {"role": "user", "content": prompt}
            ],
            max_retries=3
        )
        diff = response.candidate_diff
    except Exception as e:
        print(f"Error in Fixer LLM: {e}")
        diff = ""
        
    return {
        'candidate_diff': diff,
        'status': 'fixer_completed'
    }
