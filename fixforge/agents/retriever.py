from core.state import AgentState
from memory.chroma_client import chroma_manager

async def run_retriever(state: AgentState) -> AgentState:
    history = chroma_manager.query_history(state.get('issue_title', 'Bug'), n_results=1)
    state['historical_fix_context'] = history
    state['retrieved_ast_context'] = {"functions": ["def dummy(): pass"]}
    state['status'] = 'retriever_completed'
    return state
