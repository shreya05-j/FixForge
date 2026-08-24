from core.state import AgentState

def run_planner(state: AgentState) -> AgentState:
    """
    ForgePlanner: Analyzes inputs and produces prioritized target files and symbols for investigation.
    """
    print(f"Planning fix for issue {state.get('issue_id')}")
    state['plan'] = "1. Locate target function.\n2. Identify the logical flaw.\n3. Draft patch.\n4. Verify tests."
    state['status'] = 'planning'
    return state
