from core.state import GraphState

def calculate_confidence(state: GraphState) -> GraphState:
    print("Calculating confidence score based on test results and patch size")
    score = 0.95 if state['verification_success'] else 0.2
    state['confidence_score'] = score
    state['current_step'] = 'scoring'
    return state
