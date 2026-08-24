from core.state import AgentState

def run_planner(state: AgentState) -> AgentState:
    """
    ForgePlanner: Evaluates issue to generate prioritized target files and search directives.
    """
    # Mocking LLM Call
    state['plan'] = "Analyze the provided issue, target files related to logic failure."
    state['target_files'] = ["src/main.py"] if not state.get('target_files') else state['target_files']
    state['status'] = 'planner_completed'
    return state
