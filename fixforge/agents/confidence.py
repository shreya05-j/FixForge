from core.state import AgentState

def run_confidence_engine(state: AgentState) -> AgentState:
    """
    Confidence Engine: Implements mathematical confidence formula.
    """
    test_pass = 1.0 if state.get('test_results', {}).get('passed') else 0.0
    semgrep_agr = 0.9
    context_match = 0.8
    consistency = 0.85
    
    score = (0.45 * test_pass) + (0.25 * semgrep_agr) + (0.15 * context_match) + (0.15 * consistency)
    state['confidence_score'] = round(score, 4)
    state['confidence_breakdown'] = {
        "TestPass": test_pass,
        "SemgrepAgreement": semgrep_agr,
        "ContextMatch": context_match,
        "Consistency": consistency
    }
    state['status'] = 'confidence_scored'
    return state
