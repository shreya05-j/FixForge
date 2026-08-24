from core.state import GraphState

def run_retriever(state: GraphState) -> GraphState:
    print("Retrieving context from ChromaDB and Tree-sitter")
    state['retrieved_code'] = "def faulty_function():\n    pass # To be fixed"
    state['current_step'] = 'retrieval'
    return state
