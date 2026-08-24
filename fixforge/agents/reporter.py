from core.state import AgentState

def generate_report(state: AgentState) -> AgentState:
    """
    ForgeReporter: Formats the final diagnostic explanation, test evidence, diff, and confidence breakdown into a structured GitHub review comment.
    """
    print("Generating GitHub PR markdown report...")
    
    report = f"""# FixForge Autonomous Repair Report

## 🔍 Diagnosis
**Category**: {state.get('failure_category')} | **Severity**: {state.get('severity')}
{state.get('diagnosis')}

## 🔬 Execution & Verification
- **Test Passed**: `{"YES" if state.get('test_passed') else "NO"}`
- **Retries Used**: `{state.get('retry_count', 0)}/3`

<details><summary><b>Pytest Output</b></summary>

```
{state.get('test_results')}
```
</details>

## 📊 Confidence Score: {state.get('confidence_score', 0) * 100:.1f}%
- Test Execution: `{state.get('confidence_signals', {}).get('S_test')}`
- Static Analysis: `{state.get('confidence_signals', {}).get('S_static')}`
- Context Relevance: `{state.get('confidence_signals', {}).get('S_context')}`
- Consistency: `{state.get('confidence_signals', {}).get('S_consistency')}`

## 💻 Proposed Patch
```diff
{state.get('diff')}
```
"""
    
    state['status'] = 'completed' if state.get('test_passed') else 'failed'
    # Optional: Log to ChromaDB
    
    return state
