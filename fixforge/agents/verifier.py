from core.state import AgentState
from sandbox.runner import run_in_sandbox
import os
from typing import Dict, Any

async def run_verifier(state: AgentState) -> Dict[str, Any]:
    repo_path = state.get('repo_checkout_path') or state.get('repo_name', '/tmp')
    if not os.path.exists(repo_path):
        repo_path = os.getcwd()

    candidate_diff = state.get('candidate_diff', '')
    results = run_in_sandbox(repo_path, candidate_diff, test_cmd="pytest")
    
    current_retry = state.get('retry_count', 0)
    attempts = list(state.get('attempt_history') or [])
    fixer_telem = state.get('fixer_telemetry') or {}
    attempts.append({
        "attempt_number": current_retry + 1,
        "status": results.get("status", "failed"),
        "source": fixer_telem.get("source", "llm"),
        "model_name": fixer_telem.get("model", "qwen/qwen3.8-27b"),
        "tokens_used": fixer_telem.get("total_tokens", 0),
        "latency_sec": fixer_telem.get("latency_sec", 0.0),
        "patch_diff": candidate_diff,
        "test_logs": results.get("stdout") or results.get("stderr") or results.get("error", "")
    })

    update: Dict[str, Any] = {
        'test_results': results,
        'attempt_history': attempts,
    }

    if results.get('status') == 'unverified':
        update['status'] = 'unverified'
    else:
        update['status'] = 'verifier_completed'
        if not results.get('passed', False):
            # Both patch_failed and test failure count as failed attempt triggering retry
            update['retry_count'] = current_retry + 1

    return update
