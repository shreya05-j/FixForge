from core.state import AgentState
from memory.chroma_client import chroma_manager
from typing import Dict, Any

async def run_retriever(state: AgentState) -> Dict[str, Any]:
    history = chroma_manager.query_history(state.get('issue_title', 'Bug'), n_results=1)
    return {
        'historical_fix_context': history,
        'retrieved_ast_context': {"functions": ["def dummy(): pass"]},
        'status': 'retriever_completed'
    }
