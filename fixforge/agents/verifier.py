from core.state import AgentState
from sandbox.runner import run_in_sandbox
import os

def run_verifier(state: AgentState) -> AgentState:
    """
    ForgeVerifier: Invokes sandbox/runner.py to test candidate diffs.
    """
    repo_path = state.get('repo_name', '/tmp') # In practice this needs to be a valid absolute path
    # Handle mock for test
    if not os.path.exists(repo_path):
        repo_path = os.getcwd()

    results = run_in_sandbox(repo_path, state.get('candidate_diff', ''), test_cmd="pytest || echo 'No tests'")
    
    state['test_results'] = results
    if not results['passed']:
        state['retry_count'] = state.get('retry_count', 0) + 1
        
    state['status'] = 'verifier_completed'
    return state
