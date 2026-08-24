from core.state import GraphState

def run_fixer(state: GraphState) -> GraphState:
    print("Generating patch...")
    state['proposed_patch'] = "def faulty_function():\n    return True"
    state['patch_diff'] = "--- a/file.py\n+++ b/file.py\n@@ -1,2 +1,2 @@\n-def faulty_function():\n-    pass\n+def faulty_function():\n+    return True"
    state['current_step'] = 'fixing'
    return state
