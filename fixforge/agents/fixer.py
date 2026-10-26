"""
fixer.py — ForgeFixer: synthesizes a unified diff using the diagnosis and retrieved code.

Stage 7 addition: after the primary diff is generated at temperature 0, generates
LLM_CONSISTENCY_SAMPLES additional samples at low temperature (0.15) and stores them
in state["consistency_samples"] for the Confidence Engine's LLM consistency signal.
"""

import logging
from core.state import AgentState
from core.llm import get_async_client
from core.llm_caller import call_structured_llm
from core.config import settings
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Tuple

async_llm_client = get_async_client()

logger = logging.getLogger(__name__)

_FIXER_MODEL = getattr(settings, "FIXFORGE_MODEL", "qwen/qwen3.8-27b")
_SYSTEM_PROMPT = (
    "You are a precise software engineer producing MINIMAL bug fixes.\n"
    "Rules:\n"
    "1. Output ONLY a valid git unified diff in the candidate_diff field.\n"
    "2. The diff MUST start with '--- a/<filepath>' and '+++ b/<filepath>' matching the target file path provided.\n"
    "3. MINIMAL CHANGE ONLY: change the fewest lines possible (typically 1 to 5 lines). "
    "Do NOT refactor, add features, or rewrite unrelated code.\n"
    "4. Copy context lines VERBATIM character-by-character from the provided code snippet including exact indentation.\n"
    "5. Keep hunks minimal: 2-3 lines of unchanged context above and below the change.\n"
    "6. Never output conversational explanations, only the unified diff."
)


class FixerOutput(BaseModel):
    candidate_diff: str = Field(
        description=(
            "Minimal git unified diff fixing ONLY the reported bug. "
            "Must start with '--- a/' and '+++ b/'. Max 25 changed lines."
        ),
        max_length=6000,
    )


def _build_fixer_prompt(state: AgentState) -> str:
    test_results = state.get("test_results", {})
    failure_feedback = ""
    if test_results:
        if test_results.get("status") == "patch_failed":
            failure_feedback = (
                f"\n[CRITICAL FAILURE] Previous patch rejected by git apply:\n"
                f"{test_results.get('error') or test_results.get('stderr')}\n"
                "Ensure file paths and context lines match the provided target code exactly."
            )
        elif not test_results.get("passed", False):
            failure_feedback = (
                f"\n[TEST FAILURE] Previous patch failed test verification:\n"
                f"{test_results.get('stdout') or test_results.get('stderr')}"
            )

    ast_raw = state.get('retrieved_ast_context') or {}
    code_snippets = []
    if isinstance(ast_raw, dict):
        for fn in ast_raw.get("functions", []):
            code_snippets.append(
                f"=== Target File: {fn.get('file', 'unknown')} (Function: {fn.get('name')}) ===\n"
                f"```python\n{fn.get('code', '')}\n```"
            )
        for cls in ast_raw.get("classes", []):
            code_snippets.append(
                f"=== Target File: {cls.get('file', 'unknown')} (Class: {cls.get('name')}) ===\n"
                f"```python\n{cls.get('code', '')}\n```"
            )
    formatted_code = "\n\n".join(code_snippets) if code_snippets else str(ast_raw)[:3000]

    return (
        f"Diagnosis: {state.get('diagnosis_summary')}\n\n"
        f"Source Code Context:\n{formatted_code}\n"
        f"{failure_feedback}\n"
        "Generate a valid git unified diff to fix the issue."
    )



async def _call_fixer_structured(prompt: str, temperature: float, agent_name: str = "Fixer") -> Tuple[str, Dict[str, Any]]:
    """Single LLM call to the Fixer; returns (diff_string, telemetry)."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    resp, telemetry = await call_structured_llm(
        agent_name=agent_name,
        response_model=FixerOutput,
        messages=messages,
        temperature=temperature,
        timeout_sec=60.0,
        client=async_llm_client,
        max_tokens=1500,
    )
    diff = resp.candidate_diff if resp else ""
    return diff, telemetry


async def run_fixer(state: AgentState) -> Dict[str, Any]:
    """
    ForgeFixer: Generates a unified diff patch.

    Primary sample: temperature=0.0 (or 0.2 on retry for diversity).
    Consistency samples: LLM_CONSISTENCY_SAMPLES additional calls at temp=0.15,
    stored in state["consistency_samples"] for the Confidence Engine.
    """
    prompt = _build_fixer_prompt(state)
    retry_count = state.get("retry_count", 0)

    # Primary diff generation
    primary_temp = 0.0 if retry_count == 0 else 0.2
    diff, primary_telemetry = await _call_fixer_structured(prompt, primary_temp, "Fixer")

    if not diff:
        logger.error("Fixer produced empty diff after LLM call.")

    # Consistency samples (low temperature, separate calls)
    n_samples = settings.LLM_CONSISTENCY_SAMPLES
    consistency_samples: List[str] = []
    consistency_telemetry: List[Dict[str, Any]] = []

    if diff and n_samples > 0:
        for i in range(n_samples):
            try:
                sample, sample_telemetry = await _call_fixer_structured(
                    prompt,
                    temperature=0.15,
                    agent_name=f"Fixer-ConsistencySampler-{i+1}"
                )
                consistency_telemetry.append(sample_telemetry)
                if sample:
                    consistency_samples.append(sample)
                    logger.debug("Consistency sample %d/%d generated (%d chars).", i + 1, n_samples, len(sample))
            except Exception as exc:
                logger.warning("Consistency sample %d/%d skipped due to rate limit/error: %s", i + 1, n_samples, exc)
                break

    logger.info(
        "Fixer: primary diff %d chars, %d/%d consistency samples collected.",
        len(diff), len(consistency_samples), n_samples,
    )

    return {
        "candidate_diff": diff,
        "consistency_samples": consistency_samples,
        "fixer_telemetry": primary_telemetry,
        "consistency_telemetry": consistency_telemetry,
        "status": "fixer_completed",
    }
