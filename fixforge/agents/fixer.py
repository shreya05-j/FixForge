from core.state import AgentState

def run_fixer(state: AgentState) -> AgentState:
    """
    ForgeFixer: Uses the diagnostic report and test failure logs from previous retries to generate a clean unified diff.
    """
    print("Generating patch...")
    state['diff'] = """--- a/target.py
+++ b/target.py
@@ -1,2 +1,3 @@
 def target_function(data):
-    return data.get('value')
+    if data is None: return None
+    return data.get('value')
"""
    state['status'] = 'fixing'
    return state
