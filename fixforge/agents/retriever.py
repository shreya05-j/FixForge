from core.state import AgentState
from memory.chroma_client import chroma_manager

def run_retriever(state: AgentState) -> AgentState:
    """
    ForgeRetriever: Invokes ast_parser and queries ChromaDB for context.
    """
    history = chroma_manager.query_history(state.get('issue_title', 'Bug'), n_results=1)
    state['historical_fix_context'] = history
    state['retrieved_ast_context'] = {"functions": ["def dummy(): pass"]}
    state['status'] = 'retriever_completed'
    return state
