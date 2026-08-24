from core.state import AgentState

def calculate_confidence(state: AgentState) -> AgentState:
    """
    Confidence Engine: Implements the exact weighted formula.
    Confidence = (0.45 * S_test) + (0.25 * S_static) + (0.15 * S_context) + (0.15 * S_consistency)
    """
    print("Calculating confidence score...")
    
    # Heuristic scoring based on test outcome
    s_test = 1.0 if state.get('test_passed') else 0.2
    s_static = 0.9  # Mock Semgrep static analysis score
    s_context = 0.8 # Mock relevance of retrieved AST and Chroma matching
    s_consistency = 0.85 # Mock LLM hallucination check score
    
    confidence = (0.45 * s_test) + (0.25 * s_static) + (0.15 * s_context) + (0.15 * s_consistency)
    
    state['confidence_signals'] = {
        'S_test': s_test,
        'S_static': s_static,
        'S_context': s_context,
        'S_consistency': s_consistency
    }
    state['confidence_score'] = round(confidence, 4)
    
    return state
