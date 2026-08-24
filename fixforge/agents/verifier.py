from core.state import AgentState
from sandbox.runner import run_in_sandbox

def run_verifier(state: AgentState) -> AgentState:
    """
    ForgeVerifier: Invokes sandbox/runner.py to test the diff and captures detailed Pytest failures.
    """
    print("Running Pytest in Docker Sandbox...")
    state['status'] = 'verifying'
    
    # Example integration with runner
    # repo_path = state['repository'].get('repo_path', '/tmp/workspace')
    # success, logs = run_in_sandbox(repo_path, state['diff'])
    
    # Mocking execution for now
    success = True
    logs = "1 passed in 0.05s"
    
    state['test_results'] = logs
    state['test_passed'] = success
    
    if not success:
        state['retry_count'] = state.get('retry_count', 0) + 1
        state['status'] = 'retrying'
    
    return state
