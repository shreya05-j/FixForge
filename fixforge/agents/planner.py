from core.state import GraphState

def run_planner(state: GraphState) -> GraphState:
    print(f"Planning fix for issue {state['issue_id']}")
    state['current_step'] = 'planning'
    return state
