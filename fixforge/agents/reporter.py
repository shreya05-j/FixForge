from core.state import AgentState
from memory.chroma_client import chroma_manager
from api.services.github import post_pr_review_comment
import uuid

from typing import Dict, Any

async def run_reporter(state: AgentState) -> Dict[str, Any]:
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
    
    test_results = state.get('test_results', {})
    is_unverified = test_results.get('status') == 'unverified'
    test_passed_str = "UNVERIFIED (Sandbox Unavailable)" if is_unverified else ("YES" if test_results.get('passed') else "NO")
    reason_note = f"\n> [!WARNING]\n> **Sandbox Verification Skipped**: {test_results.get('error', 'Docker daemon unreachable')}\n" if is_unverified else ""

    report = f"""# FixForge Autonomous Repair Report{" [UNVERIFIED]" if is_unverified else ""}
{reason_note}
## 🔍 Diagnosis
**Category**: {state.get('failure_category')} | **Severity**: {state.get('severity')}
{state.get('diagnosis_summary')}

## 🔬 Execution & Verification
- **Verification Status**: `{test_passed_str}`
- **Retries Used**: `{state.get('retry_count', 0)}/3`

<details><summary><b>Execution Output</b></summary>

```
{test_results.get('stdout') or test_results.get('stderr') or test_results.get('error', 'No output')}
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

    return {
        'status': 'reporter_completed'
    }
