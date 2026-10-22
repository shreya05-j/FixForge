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
    "You are a master software engineer. "
    "Output ONLY a valid git unified diff inside the candidate_diff field. "
    "The diff must start with '--- a/' and '+++ b/' headers and include correct @@ hunk headers."
)


class FixerOutput(BaseModel):
    candidate_diff: str = Field(
        description="Clean git unified diff string addressing the issue. Must start with --- and +++"
    )


def _build_fixer_prompt(state: AgentState) -> str:
    test_results = state.get("test_results", {})
    failure_feedback = ""
    if test_results:
        if test_results.get("status") == "patch_failed":
            failure_feedback = (
                f"\n[CRITICAL FAILURE] Previous patch rejected by git apply --check:\n"
                f"{test_results.get('error') or test_results.get('stderr')}\n"
                "Ensure file paths and hunk headers match the repository exactly."
            )
        elif not test_results.get("passed", False):
            failure_feedback = (
                f"\n[TEST FAILURE] Previous patch failed test verification:\n"
                f"{test_results.get('stdout') or test_results.get('stderr')}"
            )

    return (
        f"Diagnosis: {state.get('diagnosis_summary')}\n"
        f"Context: {state.get('retrieved_ast_context')}\n"
        f"Previous test results: {test_results}"
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
        timeout_sec=45.0,
        client=async_llm_client,
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
            sample, sample_telemetry = await _call_fixer_structured(
                prompt,
                temperature=0.15,
                agent_name=f"Fixer-ConsistencySampler-{i+1}"
            )
            consistency_telemetry.append(sample_telemetry)
            if sample:
                consistency_samples.append(sample)
                logger.debug("Consistency sample %d/%d generated (%d chars).", i + 1, n_samples, len(sample))

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
