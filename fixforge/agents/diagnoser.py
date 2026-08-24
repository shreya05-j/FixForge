from core.state import AgentState

def run_diagnoser(state: AgentState) -> AgentState:
    """
    ForgeDiagnoser: Identifies root cause and predicts severity.
    """
    state['diagnosis_summary'] = "Mocked diagnosis: Logic defect in variable handling."
    state['failure_category'] = "Logic Error"
    state['severity'] = "High"
    state['status'] = 'diagnoser_completed'
    return state
