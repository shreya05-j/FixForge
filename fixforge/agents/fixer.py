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
    prompt = f"Diagnosis: {state.get('diagnosis_summary')}\nContext: {state.get('retrieved_ast_context')}\nPrevious test results: {state.get('test_results')}\nGenerate a unified diff to fix the issue."
    
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
