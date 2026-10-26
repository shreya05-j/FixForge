"""
retriever.py - ForgeRetriever agent.

Reads real source files from the cloned repository checkout. Calls
ast_parser.extract_functions_and_classes() on each target file named by the
Planner. Falls back to a keyword scan when target_files is empty or when files
are not parseable. Queries ChromaDB for historical fix context.

No placeholder AST data is ever returned in the live path.
"""

import logging
import os
import re
from typing import Dict, Any

from core.state import AgentState
from memory.ast_parser import extract_functions_and_classes
from memory.chroma_client import chroma_manager
from repo_checkout import find_python_files

logger = logging.getLogger(__name__)

# Characters of source code sent to the Fixer per function/class (keeps tokens bounded).
_MAX_SOURCE_CHARS = 3_000
# Max number of functions/classes extracted across all files.
_MAX_SYMBOLS = 40


async def run_retriever(state: AgentState) -> Dict[str, Any]:
    """
    1. Uses repo_checkout_path (set by run_repair_workflow before invoking the
       workflow) to read target files.
    2. Runs ast_parser on each file and accumulates functions/classes.
    3. Falls back to a keyword scan over the whole repo when target_files is
       empty or all named files are missing.
    4. Queries ChromaDB for historical fixes similar to the issue title.
    5. Returns the REAL extracted symbols and historical context.
    """
    checkout_path: str | None = state.get("repo_checkout_path")
    target_files: list = state.get("target_files", [])
    issue_title: str = state.get("issue_title", "Bug")

    # -----------------------------------------------------------------------
    # Step 1: Query ChromaDB for historical fixes (always attempted).
    # -----------------------------------------------------------------------
    try:
        history = chroma_manager.query_history(issue_title, n_results=3)
    except Exception as exc:
        logger.warning(f"ChromaDB query failed: {exc}")
        history = []

    # -----------------------------------------------------------------------
    # Step 2: Resolve the files to parse.
    # -----------------------------------------------------------------------
    fallback_used = False

    if checkout_path is None:
        # Checkout failed upstream. Return a clear error state rather than stub data.
        logger.warning(
            "repo_checkout_path is None - repo checkout failed upstream. "
            "Retrieved AST context will be empty."
        )
        return {
            "retrieved_ast_context": {
                "functions": [],
                "classes": [],
                "source_files_read": [],
                "error": "Repository checkout was not available. AST context is empty.",
            },
            "historical_fix_context": history,
            "retriever_fallback": False,
            "status": "retriever_completed",
        }

    # Check explicit target_file or target_hint from state
    explicit_target = state.get("target_file")
    target_hint = state.get("target_hint")
    if not target_hint and state.get("issue_title"):
        # Check if issue title mentions a specific python module/function
        m_hint = re.search(r'\b([a-zA-Z0-9_]{4,})\b', str(state.get("issue_title", "")))
        if m_hint and m_hint.group(1).lower() not in ("issue", "pull", "repair", "defect", "fail", "fixed", "check"):
            target_hint = m_hint.group(1)

    # Resolve target_files relative to the checkout root.
    resolved_files = []
    
    if explicit_target:
        candidate = explicit_target if os.path.isabs(explicit_target) else os.path.join(checkout_path, explicit_target)
        if os.path.isfile(candidate):
            resolved_files.append(candidate)
        else:
            logger.warning(f"Explicit target_file not found: {explicit_target} -> {candidate}")

    if target_files:
        for tf in target_files:
            candidate = tf if os.path.isabs(tf) else os.path.join(checkout_path, tf)
            if os.path.isfile(candidate) and candidate not in resolved_files:
                resolved_files.append(candidate)
            else:
                logger.warning(f"Planner-specified file not found: {tf} -> {candidate}")

    if not resolved_files:
        # Fallback: scan the whole repo for Python files prioritizing hints and primary dirs.
        logger.info(
            "target_files is empty or none found in checkout. "
            f"Falling back to prioritized scan with hint='{target_hint}'."
        )
        resolved_files = find_python_files(checkout_path, max_files=50, hint=target_hint)
        fallback_used = True


    if not resolved_files:
        logger.warning("No Python files found in checkout. AST context will be empty.")
        return {
            "retrieved_ast_context": {
                "functions": [],
                "classes": [],
                "source_files_read": [],
                "error": "No Python files found in repository checkout.",
            },
            "historical_fix_context": history,
            "retriever_fallback": True,
            "status": "retriever_completed",
        }

    # -----------------------------------------------------------------------
    # Step 3: Parse each resolved file with ast_parser.
    # -----------------------------------------------------------------------
    all_functions = []
    all_classes = []
    files_successfully_read = []

    for filepath in resolved_files:
        if len(all_functions) + len(all_classes) >= _MAX_SYMBOLS:
            break
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            parsed = extract_functions_and_classes(source)
            rel_path = os.path.relpath(filepath, checkout_path)
            # Tag each symbol with its source file for the Fixer.
            for fn in parsed.get("functions", []):
                fn["file"] = rel_path
                fn["code"] = fn["code"][:_MAX_SOURCE_CHARS]  # bound token size
                all_functions.append(fn)
            for cls in parsed.get("classes", []):
                cls["file"] = rel_path
                cls["code"] = cls["code"][:_MAX_SOURCE_CHARS]
                all_classes.append(cls)
            files_successfully_read.append(rel_path)
        except Exception as exc:
            logger.warning(f"Failed to parse {filepath}: {exc}")

    logger.info(
        f"Retriever extracted {len(all_functions)} functions, "
        f"{len(all_classes)} classes from {len(files_successfully_read)} files. "
        f"Fallback used: {fallback_used}"
    )

    retrieved_ast_context = {
        "functions": all_functions[:_MAX_SYMBOLS],
        "classes": all_classes[:_MAX_SYMBOLS],
        "source_files_read": files_successfully_read,
        "fallback_scan": fallback_used,
    }

    return {
        "retrieved_ast_context": retrieved_ast_context,
        "historical_fix_context": history,
        "retriever_fallback": fallback_used,
        "status": "retriever_completed",
    }
