from core.state import AgentState

def run_diagnoser(state: AgentState) -> AgentState:
    """
    ForgeDiagnoser: Formulates the root cause, maps regression blast radius, tags the defect across the 6-class taxonomy, and predicts severity.
    """
    print("Diagnosing root cause using LLM")
    state['diagnosis'] = "Uncaught TypeError in target_function due to NoneType object."
    state['failure_category'] = "Runtime" # Syntax, Logic, Runtime, Dependency, Concurrency, Configuration
    state['severity'] = "High" # Low, Medium, High, Critical
    state['status'] = 'diagnosing'
    return state
