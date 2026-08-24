from core.state import AgentState
from memory.chroma_client import chroma_manager
import uuid

async def run_reporter(state: AgentState) -> AgentState:
    if state.get('test_results', {}).get('passed'):
        chroma_manager.add_historical_fix(
            fix_id=str(uuid.uuid4()),
            description=state['diagnosis_summary'],
            metadata={"severity": state['severity'], "diff": state['candidate_diff']}
        )
    state['status'] = 'reporter_completed'
    return state
