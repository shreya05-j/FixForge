from core.state import GraphState

def run_diagnoser(state: GraphState) -> GraphState:
    print("Diagnosing root cause using LLM")
    state['diagnosis'] = "Null pointer exception in faulty_function."
    state['severity'] = 8
    state['current_step'] = 'diagnosis'
    return state
