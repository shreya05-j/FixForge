from core.state import GraphState

def generate_report(state: GraphState) -> GraphState:
    print("Generating GitHub PR markdown...")
    report = f"# FixForge Automated Repair\n\n**Diagnosis**: {state['diagnosis']}\n**Confidence**: {state['confidence_score'] * 100}%\n\n## Patch\n```diff\n{state['patch_diff']}\n```"
    state['report_markdown'] = report
    state['current_step'] = 'reporting'
    return state
