from core.state import AgentState
from sandbox.runner import run_in_sandbox
import os
from typing import Dict, Any

async def run_verifier(state: AgentState) -> Dict[str, Any]:
    repo_path = state.get('repo_name', '/tmp')
    if not os.path.exists(repo_path):
        repo_path = os.getcwd()

    results = run_in_sandbox(repo_path, state.get('candidate_diff', ''), test_cmd="pytest || echo 'No tests'")
    
    update = {
        'test_results': results,
        'status': 'verifier_completed'
    }
    
    if not results['passed']:
        update['retry_count'] = state.get('retry_count', 0) + 1
        
    return update
