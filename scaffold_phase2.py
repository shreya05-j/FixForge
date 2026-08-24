import os
from pathlib import Path

BASE_DIR = Path("fixforge")

FILES = {
    "core/state.py": """from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    repository: Dict[str, str]
    issue_id: str
    pr_id: Optional[str]
    issue_description: str
    stack_trace: str
    plan: str
    retrieved_context: str
    diagnosis: str
    failure_category: str
    severity: str
    diff: str
    test_results: str
    test_passed: bool
    retry_count: int
    confidence_score: float
    confidence_signals: Dict[str, float]
    status: str
""",
    "agents/planner.py": """from core.state import AgentState

def run_planner(state: AgentState) -> AgentState:
    \"\"\"
    ForgePlanner: Analyzes inputs and produces prioritized target files and symbols for investigation.
    \"\"\"
    print(f"Planning fix for issue {state.get('issue_id')}")
    state['plan'] = "1. Locate target function.\\n2. Identify the logical flaw.\\n3. Draft patch.\\n4. Verify tests."
    state['status'] = 'planning'
    return state
""",
    "agents/retriever.py": """from core.state import AgentState

def run_retriever(state: AgentState) -> AgentState:
    \"\"\"
    ForgeRetriever: Executes Tree-sitter queries to extract symbol boundaries and queries ChromaDB for structurally similar past fixes.
    \"\"\"
    print("Retrieving context from ChromaDB and Tree-sitter")
    state['retrieved_context'] = "def target_function():\\n    # extracted AST code snippet\\n    pass"
    return state
""",
    "agents/diagnoser.py": """from core.state import AgentState

def run_diagnoser(state: AgentState) -> AgentState:
    \"\"\"
    ForgeDiagnoser: Formulates the root cause, maps regression blast radius, tags the defect across the 6-class taxonomy, and predicts severity.
    \"\"\"
    print("Diagnosing root cause using LLM")
    state['diagnosis'] = "Uncaught TypeError in target_function due to NoneType object."
    state['failure_category'] = "Runtime" # Syntax, Logic, Runtime, Dependency, Concurrency, Configuration
    state['severity'] = "High" # Low, Medium, High, Critical
    state['status'] = 'diagnosing'
    return state
""",
    "agents/fixer.py": """from core.state import AgentState

def run_fixer(state: AgentState) -> AgentState:
    \"\"\"
    ForgeFixer: Uses the diagnostic report and test failure logs from previous retries to generate a clean unified diff.
    \"\"\"
    print("Generating patch...")
    state['diff'] = \"\"\"--- a/target.py
+++ b/target.py
@@ -1,2 +1,3 @@
 def target_function(data):
-    return data.get('value')
+    if data is None: return None
+    return data.get('value')
\"\"\"
    state['status'] = 'fixing'
    return state
""",
    "agents/verifier.py": """from core.state import AgentState
from sandbox.runner import run_in_sandbox

def run_verifier(state: AgentState) -> AgentState:
    \"\"\"
    ForgeVerifier: Invokes sandbox/runner.py to test the diff and captures detailed Pytest failures.
    \"\"\"
    print("Running Pytest in Docker Sandbox...")
    state['status'] = 'verifying'
    
    # Example integration with runner
    # repo_path = state['repository'].get('repo_path', '/tmp/workspace')
    # success, logs = run_in_sandbox(repo_path, state['diff'])
    
    # Mocking execution for now
    success = True
    logs = "1 passed in 0.05s"
    
    state['test_results'] = logs
    state['test_passed'] = success
    
    if not success:
        state['retry_count'] = state.get('retry_count', 0) + 1
        state['status'] = 'retrying'
    
    return state
""",
    "agents/confidence.py": """from core.state import AgentState

def calculate_confidence(state: AgentState) -> AgentState:
    \"\"\"
    Confidence Engine: Implements the exact weighted formula.
    Confidence = (0.45 * S_test) + (0.25 * S_static) + (0.15 * S_context) + (0.15 * S_consistency)
    \"\"\"
    print("Calculating confidence score...")
    
    # Heuristic scoring based on test outcome
    s_test = 1.0 if state.get('test_passed') else 0.2
    s_static = 0.9  # Mock Semgrep static analysis score
    s_context = 0.8 # Mock relevance of retrieved AST and Chroma matching
    s_consistency = 0.85 # Mock LLM hallucination check score
    
    confidence = (0.45 * s_test) + (0.25 * s_static) + (0.15 * s_context) + (0.15 * s_consistency)
    
    state['confidence_signals'] = {
        'S_test': s_test,
        'S_static': s_static,
        'S_context': s_context,
        'S_consistency': s_consistency
    }
    state['confidence_score'] = round(confidence, 4)
    
    return state
""",
    "agents/reporter.py": """from core.state import AgentState

def generate_report(state: AgentState) -> AgentState:
    \"\"\"
    ForgeReporter: Formats the final diagnostic explanation, test evidence, diff, and confidence breakdown into a structured GitHub review comment.
    \"\"\"
    print("Generating GitHub PR markdown report...")
    
    report = f\"\"\"# FixForge Autonomous Repair Report

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
\"\"\"
    
    state['status'] = 'completed' if state.get('test_passed') else 'failed'
    # Optional: Log to ChromaDB
    
    return state
""",
    "graph/nodes.py": """from agents.planner import run_planner
from agents.retriever import run_retriever
from agents.diagnoser import run_diagnoser
from agents.fixer import run_fixer
from agents.verifier import run_verifier
from agents.confidence import calculate_confidence
from agents.reporter import generate_report

# Node wrappers for LangGraph
def planner_node(state): return run_planner(state)
def retriever_node(state): return run_retriever(state)
def diagnoser_node(state): return run_diagnoser(state)
def fixer_node(state): return run_fixer(state)
def verifier_node(state): return run_verifier(state)
def confidence_node(state): return calculate_confidence(state)
def reporter_node(state): return generate_report(state)
""",
    "graph/workflow.py": """from langgraph.graph import StateGraph, END
from core.state import AgentState
from graph.nodes import (
    planner_node, retriever_node, diagnoser_node, fixer_node, 
    verifier_node, confidence_node, reporter_node
)

def build_graph():
    \"\"\"
    LangGraph Cyclic Orchestration workflow
    \"\"\"
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("diagnoser", diagnoser_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("confidence", confidence_node)
    workflow.add_node("reporter", reporter_node)
    
    # Define primary linear flow
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "diagnoser")
    workflow.add_edge("diagnoser", "fixer")
    workflow.add_edge("fixer", "verifier")
    
    # Conditional edge after verification
    def should_continue(state: AgentState):
        if state.get("test_passed", False):
            return "confidence"
        elif state.get("retry_count", 0) < 3:
            return "fixer"
        else:
            # Route to Confidence Engine (low confidence band) -> Reporter
            return "confidence"
            
    workflow.add_conditional_edges(
        "verifier",
        should_continue,
        {
            "confidence": "confidence",
            "fixer": "fixer"
        }
    )
    
    # Final reporting
    workflow.add_edge("confidence", "reporter")
    workflow.add_edge("reporter", END)
    
    return workflow.compile()
""",
    "sandbox/runner.py": """import docker
from core.config import settings

def run_in_sandbox(repo_path: str, diff_patch: str, test_cmd: str = "pytest") -> tuple[bool, str]:
    \"\"\"
    Secure Docker Execution Sandbox
    Spins up ephemeral containers with strict network, CPU, and memory limits.
    \"\"\"
    client = docker.from_env()
    container = None
    
    try:
        # We start a container using our lightweight, unprivileged image
        # In a real scenario, we copy the repository to a tmp scratchpad to avoid modifying read-only host mount
        entrypoint_cmd = f\"\"\"
        cp -r /app_src/* /app_scratch/ && \\
        cd /app_scratch && \\
        echo "{diff_patch}" > patch.diff && \\
        git apply patch.diff && \\
        {test_cmd}
        \"\"\"

        container = client.containers.run(
            "fixforge-sandbox:latest",
            command=["/bin/bash", "-c", entrypoint_cmd],
            volumes={repo_path: {'bind': '/app_src', 'mode': 'ro'}},  # Read-only checkout mount
            working_dir="/app_scratch",
            network_mode="none",  # Net-isolated
            mem_limit="512m",     # Hard resource limit
            cpu_quota=50000,
            cpu_period=100000,
            user="sandbox_user",  # Nonroot unprivileged user
            detach=True
        )
        
        # Hard timeout of 60 seconds
        result = container.wait(timeout=60)
        exit_code = result['StatusCode']
        logs = container.logs().decode('utf-8')
        
        return (exit_code == 0, logs)
        
    except docker.errors.ContainerError as e:
        return False, e.stderr.decode('utf-8')
    except Exception as e:
        return False, str(e)
    finally:
        # Mandatory container destruction
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
""",
    "sandbox/Dockerfile.sandbox": """FROM python:3.10-slim

# Create a nonroot unprivileged user
RUN useradd -m -s /bin/bash sandbox_user

WORKDIR /app_scratch

# Install foundational testing and AST dependencies
RUN pip install --no-cache-dir pytest semgrep tree-sitter tree-sitter-python git

# Make sure sandbox_user owns the scratchpad
RUN chown -R sandbox_user:sandbox_user /app_scratch

USER sandbox_user
"""
}

def scaffold():
    print(f"Scaffolding Phase 2 Implementation in {BASE_DIR}...")
    for file_path, content in FILES.items():
        full_path = BASE_DIR / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created/Updated: {full_path}")
    print("Phase 2 scaffolding complete!")

if __name__ == "__main__":
    scaffold()
