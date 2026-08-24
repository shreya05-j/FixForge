from core.state import AgentState
from memory.chroma_client import chroma_manager
from api.services.github import post_pr_review_comment
import uuid

async def run_reporter(state: AgentState) -> AgentState:
    """
    ForgeReporter: Formats markdown review comment and saves verified resolution.
    Posts the report natively back to GitHub via REST API.
    """
    if state.get('test_results', {}).get('passed'):
        chroma_manager.add_historical_fix(
            fix_id=str(uuid.uuid4()),
            description=state.get('diagnosis_summary', ''),
            metadata={"severity": state.get('severity', ''), "diff": state.get('candidate_diff', '')}
        )
    
    report = f"""# FixForge Autonomous Repair Report

## 🔍 Diagnosis
**Category**: {state.get('failure_category')} | **Severity**: {state.get('severity')}
{state.get('diagnosis_summary')}

## 🔬 Execution & Verification
- **Test Passed**: `{"YES" if state.get('test_results', {}).get('passed') else "NO"}`
- **Retries Used**: `{state.get('retry_count', 0)}/3`

<details><summary><b>Pytest Output</b></summary>

```
{state.get('test_results', {}).get('stdout', '')}
```
</details>

## 📊 Confidence Score: {state.get('confidence_score', 0.0) * 100:.1f}%

## 💻 Proposed Patch
```diff
{state.get('candidate_diff')}
```
"""

    try:
        await post_pr_review_comment(state.get('repo_name', ''), state.get('issue_id', ''), report)
    except Exception as e:
        print(f"Failed to post GitHub PR comment: {e}")

    state['status'] = 'reporter_completed'
    return state
