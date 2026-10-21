"""
test_retriever_stage1.py - Stage 1 gate test.

Verifies that the Retriever reads REAL source code from a local git repository
fixture (no network required). Proves:
  1. Functions and classes from the fixture repo appear in retrieved_ast_context.
  2. The fallback scan is triggered when target_files is empty.
  3. When repo_checkout_path is None (checkout failed), retriever returns an
     empty context with an error key - never stub data.
  4. The old placeholder "def dummy(): pass" is never returned.
"""

import os
import subprocess
import tempfile
import pytest
from agents.retriever import run_retriever
from core.state import AgentState


def _create_fixture_repo() -> tempfile.TemporaryDirectory:
    """Creates a minimal git repo with real Python source so we do not need network."""
    tmpdir = tempfile.TemporaryDirectory(prefix="fixforge_test_repo_")
    root = tmpdir.name

    # Write two Python files with real functions/classes.
    src_dir = os.path.join(root, "src")
    os.makedirs(src_dir)

    with open(os.path.join(src_dir, "utils.py"), "w") as fh:
        fh.write("""
def add(a, b):
    \"\"\"Return sum.\"\"\"
    return a + b

def divide(a, b):
    \"\"\"Return a / b. BUG: does not guard against b == 0.\"\"\"
    return a / b

class Calculator:
    def multiply(self, x, y):
        return x * y
""")

    with open(os.path.join(src_dir, "config.py"), "w") as fh:
        fh.write("""
def load_host(config):
    # BUG: KeyError when 'host' is missing
    return config['host']
""")

    with open(os.path.join(root, "test_utils.py"), "w") as fh:
        fh.write("""
def test_add():
    from src.utils import add
    assert add(1, 2) == 3
""")

    # Initialise as a git repo so the sandbox runner can apply patches later.
    subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=root, capture_output=True, check=True)

    return tmpdir


# ---------------------------------------------------------------------------
# Test 1: Fallback scan - empty target_files, scans whole repo
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retriever_fallback_scan_reads_real_code():
    """With target_files=[], retriever should find Python files and return real AST."""
    fixture = _create_fixture_repo()
    try:
        state: AgentState = {
            "repo_name": "test/fixture",
            "issue_id": "1",
            "issue_title": "KeyError in config loader",
            "issue_body": "Missing host key.",
            "stack_trace": None,
            "target_files": [],           # empty -> fallback scan
            "plan": "",
            "retrieved_ast_context": {},
            "historical_fix_context": [],
            "repo_checkout_path": fixture.name,
            "retriever_fallback": False,
            "diagnosis_summary": "",
            "failure_category": "Runtime Error",
            "severity": "Medium",
            "candidate_diff": "",
            "test_results": {},
            "retry_count": 0,
            "confidence_score": 0.0,
            "confidence_breakdown": {},
            "status": ""
        }

        result = await run_retriever(state)
        ctx = result["retrieved_ast_context"]

        # Must have found real functions - not the placeholder.
        fn_names = [f["name"] for f in ctx.get("functions", [])]
        print(f"\n[Stage 1 Gate] Fallback scan found functions: {fn_names}")
        print(f"[Stage 1 Gate] Files read: {ctx.get('source_files_read', [])}")
        print(f"[Stage 1 Gate] Classes: {[c['name'] for c in ctx.get('classes', [])]}")

        assert len(ctx.get("functions", [])) > 0, "Retriever returned no functions"
        assert "add" in fn_names or "load_host" in fn_names, f"Expected real functions, got: {fn_names}"
        assert "dummy" not in fn_names, "Placeholder 'dummy' function must not appear in live path"
        assert ctx.get("fallback_scan") is True, "Fallback flag should be True when target_files was empty"
        assert result["retriever_fallback"] is True

        # All functions must have real code content (not 'pass' only).
        for fn in ctx.get("functions", []):
            assert "file" in fn, f"Function {fn['name']} missing 'file' key"
            assert "code" in fn, f"Function {fn['name']} missing 'code' key"

    finally:
        fixture.cleanup()


# ---------------------------------------------------------------------------
# Test 2: Targeted retrieval - target_files provided
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retriever_reads_target_files():
    """When target_files names real files, retriever should parse exactly those."""
    fixture = _create_fixture_repo()
    try:
        state: AgentState = {
            "repo_name": "test/fixture",
            "issue_id": "2",
            "issue_title": "Divide by zero",
            "issue_body": "divide() has no guard.",
            "stack_trace": None,
            "target_files": ["src/utils.py"],
            "plan": "",
            "retrieved_ast_context": {},
            "historical_fix_context": [],
            "repo_checkout_path": fixture.name,
            "retriever_fallback": False,
            "diagnosis_summary": "",
            "failure_category": "Runtime Error",
            "severity": "High",
            "candidate_diff": "",
            "test_results": {},
            "retry_count": 0,
            "confidence_score": 0.0,
            "confidence_breakdown": {},
            "status": ""
        }

        result = await run_retriever(state)
        ctx = result["retrieved_ast_context"]
        fn_names = [f["name"] for f in ctx.get("functions", [])]
        print(f"\n[Stage 1 Gate] Targeted retrieval found functions: {fn_names}")

        assert "add" in fn_names, "Expected 'add' from src/utils.py"
        assert "divide" in fn_names, "Expected 'divide' from src/utils.py"
        assert result["retriever_fallback"] is False, "Fallback should NOT be used when target_files resolved"

        # Verify code field contains real source
        divide_fn = next(f for f in ctx["functions"] if f["name"] == "divide")
        print(f"[Stage 1 Gate] 'divide' function code:\n{divide_fn['code']}")
        assert "return a / b" in divide_fn["code"], "Real code not present in divide function"
        assert "dummy" not in divide_fn["code"]

    finally:
        fixture.cleanup()


# ---------------------------------------------------------------------------
# Test 3: Checkout failed -> empty context with error key, never stub
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retriever_no_checkout_returns_error_not_stub():
    """When repo_checkout_path is None, retriever must return an empty context
    with an explicit error message, never the old 'def dummy(): pass' stub."""
    state: AgentState = {
        "repo_name": "test/unreachable",
        "issue_id": "3",
        "issue_title": "Some bug",
        "issue_body": "Details.",
        "stack_trace": None,
        "target_files": ["src/main.py"],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "repo_checkout_path": None,    # checkout was not available
        "retriever_fallback": False,
        "diagnosis_summary": "",
        "failure_category": "Logic Error",
        "severity": "Low",
        "candidate_diff": "",
        "test_results": {},
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }

    result = await run_retriever(state)
    ctx = result["retrieved_ast_context"]
    print(f"\n[Stage 1 Gate] No-checkout context: {ctx}")

    assert ctx.get("functions") == [], "Must return empty functions, not stub"
    assert ctx.get("classes") == [], "Must return empty classes, not stub"
    assert "error" in ctx, "Must include an error key describing why context is empty"
    assert "dummy" not in str(ctx), "Placeholder stub must never appear"
