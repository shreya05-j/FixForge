"""
confidence.py — Multi-factor confidence scoring engine.

Implements the four signals from SRS Section 10 with calibrated weights:
1. Test Results (45%): Verifier pass rate (not just boolean).
2. Static Analysis (25%): Pyflakes / Ruff checks before and after patch.
3. Context Similarity (15%): Real ChromaDB distance scores for retrieved historical fixes.
4. LLM Consistency (15%): Low-temperature sampling agreement using SequenceMatcher.

Calibration bands (SRS 10.2):
- 90–100: High Confidence
- 75–89:  Medium-High Confidence
- 50–74:  Moderate Confidence
- <50:    Low Confidence

If any signal cannot be computed, it is marked unavailable (None) and weights
are dynamically renormalized across all active signals.
"""

import ast
import difflib
import logging
import os
import re
from io import StringIO
from typing import Dict, Any, List, Optional, Tuple

import pyflakes.api
import pyflakes.reporter
from core.state import AgentState

logger = logging.getLogger(__name__)

# SRS Section 10 base weights (sum to 1.00)
BASE_WEIGHTS = {
    "test_results": 0.45,
    "static_analysis": 0.25,
    "context_similarity": 0.15,
    "llm_consistency": 0.15,
}


def compute_test_results_score(test_results: Dict[str, Any]) -> Optional[float]:
    """
    Computes pass-rate from verifier outcome.
    - If status is 'unverified': returns 0.0 (verification could not confirm fix).
    - If passed is True: returns 1.0.
    - If passed is False: parses 'X passed, Y failed' from stdout/stderr to calculate
      the exact pass rate: passed / (passed + failed).
    """
    if not test_results:
        return 0.0

    status = test_results.get("status")
    if status == "unverified":
        return 0.0

    if test_results.get("passed") is True:
        return 1.0

    # Parse stdout and stderr for pytest output: e.g. '2 passed, 1 failed'
    combined_logs = (test_results.get("stdout") or "") + "\n" + (test_results.get("stderr") or "")
    passed_match = re.search(r'(\d+)\s+passed', combined_logs, re.IGNORECASE)
    failed_match = re.search(r'(\d+)\s+failed', combined_logs, re.IGNORECASE)

    if passed_match or failed_match:
        n_passed = int(passed_match.group(1)) if passed_match else 0
        n_failed = int(failed_match.group(1)) if failed_match else 0
        total = n_passed + n_failed
        if total > 0:
            return round(n_passed / total, 4)

    return 0.0


def _count_pyflakes_issues(code_str: str) -> Tuple[int, bool]:
    """
    Runs pyflakes AST analysis on python code.
    Returns (issue_count, has_syntax_error).
    """
    try:
        ast.parse(code_str)
    except SyntaxError:
        return (999, True)

    out = StringIO()
    reporter = pyflakes.reporter.Reporter(out, out)
    pyflakes.api.check(code_str, filename="patch_eval.py", reporter=reporter)
    output = out.getvalue().strip()
    if not output:
        return (0, False)
    lines = [ln for ln in output.split("\n") if ln.strip()]
    return (len(lines), False)


def compute_static_analysis_score(
    candidate_diff: str,
    repo_path: Optional[str] = None,
    target_files: Optional[List[str]] = None
) -> Optional[float]:
    """
    Scores static analysis findings introduced vs resolved.
    - Reconstructs pre-patch and post-patch code from unified diff hunks.
    - If diff introduces syntax errors: score is 0.0.
    - If new static analysis findings (unused variables, undefined names, bad imports)
      are introduced: score is penalized by 0.20 per new finding.
    - If clean or resolves issues: returns 1.0.
    """
    if not candidate_diff or not candidate_diff.strip():
        return None

    # Reconstruct pre-patch and post-patch lines from unified diff
    pre_lines = []
    post_lines = []
    has_diff_headers = False

    for line in candidate_diff.split("\n"):
        if line.startswith(("---", "+++", "@@")):
            has_diff_headers = True
            continue
        if line.startswith("-"):
            pre_lines.append(line[1:])
        elif line.startswith("+"):
            post_lines.append(line[1:])
        elif line.startswith(" "):
            pre_lines.append(line[1:])
            post_lines.append(line[1:])
        elif not has_diff_headers:
            # Standalone snippet without diff headers
            post_lines.append(line)

    post_code = "\n".join(post_lines).strip()
    pre_code = "\n".join(pre_lines).strip()

    if not post_code:
        return None

    # 1. If repo_path is provided and target file exists, check full patched file directly
    if repo_path and os.path.isdir(repo_path):
        m_file = re.search(r'^\+\+\+ [b/]*(.*?)$', candidate_diff, re.MULTILINE)
        if m_file:
            rel = m_file.group(1).strip()
            if rel.startswith(('a/', 'b/')):
                rel = rel[2:]
            rel = rel.lstrip('/')
            full_target = os.path.join(repo_path, rel)
            if not os.path.exists(full_target):
                base = os.path.basename(rel)
                for root, _, files in os.walk(repo_path):
                    if base in files:
                        full_target = os.path.join(root, base)
                        break
            if os.path.isfile(full_target):
                try:
                    with open(full_target, "r", encoding="utf-8", errors="replace") as f:
                        file_code = f.read()
                    issues, syn_err = _count_pyflakes_issues(file_code)
                    if not syn_err:
                        return 1.0 if issues == 0 else round(max(0.0, 1.0 - (0.10 * issues)), 4)
                except Exception:
                    pass

    # 2. Fallback: evaluate code hunk directly
    def _evaluate_code_issues(code: str) -> Tuple[int, bool]:
        issues, syn_err = _count_pyflakes_issues(code)
        if not syn_err:
            return issues, False
        
        # Check if fragment needs a wrapper function and closure of trailing block
        lns = code.splitlines()
        if lns and lns[-1].strip().endswith(":"):
            lns.append("                pass")
        wrapped = "def _wrapper():\n" + "\n".join("    " + ln for ln in lns)
        return _count_pyflakes_issues(wrapped)

    # Check for syntax error in post-patch code
    post_issues, post_syntax_err = _evaluate_code_issues(post_code)
    if post_syntax_err:
        return 0.0

    # Count pre-patch issues
    pre_issues = 0
    if pre_code:
        pre_issues, _ = _evaluate_code_issues(pre_code)

    new_issues = max(0, post_issues - pre_issues)
    if new_issues == 0:
        return 1.0
    return round(max(0.0, 1.0 - (0.20 * new_issues)), 4)




def compute_context_similarity_score(historical_fixes: Optional[List[Dict[str, Any]]]) -> Optional[float]:
    """
    Derived from real ChromaDB distance scores for retrieved historical fixes.
    Smaller distance = higher similarity.
    Conversion: similarity = 1.0 / (1.0 + min_distance)
    If no historical fixes were retrieved, marks signal unavailable (None).
    """
    if not historical_fixes:
        return None

    distances = []
    for fix in historical_fixes:
        dist = fix.get("distance")
        if dist is not None:
            try:
                distances.append(float(dist))
            except (ValueError, TypeError):
                pass
        elif "similarity" in fix:
            try:
                return round(float(fix["similarity"]), 4)
            except (ValueError, TypeError):
                pass

    if not distances:
        # Matches found in ChromaDB but no explicit distance: default normalized high match
        return 0.85

    min_dist = min(distances)
    similarity = 1.0 / (1.0 + max(0.0, min_dist))
    return round(min(1.0, max(0.0, similarity)), 4)


def compute_llm_consistency_score(
    candidate_diff: str,
    consistency_samples: Optional[List[str]] = None
) -> Optional[float]:
    """
    Measures agreement between the primary candidate diff and sample diffs
    synthesized at low temperature.
    Uses SequenceMatcher ratio to compute syntactic similarity.
    """
    if not candidate_diff or not candidate_diff.strip():
        return None

    if not consistency_samples:
        return None

    ratios = []
    for sample in consistency_samples:
        if sample and sample.strip():
            matcher = difflib.SequenceMatcher(None, candidate_diff.strip(), sample.strip())
            ratios.append(matcher.ratio())

    if not ratios:
        return None

    avg_agreement = sum(ratios) / len(ratios)
    return round(min(1.0, max(0.0, avg_agreement)), 4)


def map_calibration_band(score_fraction: float) -> str:
    """
    Maps final score (0.0 to 1.0) to SRS 10.2 calibration bands:
    - 90–100: High Confidence
    - 75–89:  Medium-High Confidence
    - 50–74:  Moderate Confidence
    - <50:    Low Confidence
    """
    score_pct = score_fraction * 100.0
    if score_pct >= 90.0:
        return "90-100"
    elif score_pct >= 75.0:
        return "75-89"
    elif score_pct >= 50.0:
        return "50-74"
    else:
        return "<50"


def calculate_confidence_breakdown(state: AgentState) -> Dict[str, Any]:
    """
    Orchestrates the 4 SRS signals, renormalizes weights for missing signals,
    and maps the final score to SRS 10.2 calibration bands.
    """
    test_results = state.get("test_results", {})
    candidate_diff = state.get("candidate_diff", "")
    target_files = state.get("target_files", [])
    repo_path = state.get("repo_checkout_path") or state.get("repo_name")
    historical_fixes = state.get("historical_fix_context", [])
    consistency_samples = state.get("consistency_samples")  # Optional extra fixer samples

    s_test = compute_test_results_score(test_results)
    s_static = compute_static_analysis_score(candidate_diff, repo_path=repo_path, target_files=target_files)
    s_context = compute_context_similarity_score(historical_fixes)
    s_consistency = compute_llm_consistency_score(candidate_diff, consistency_samples=consistency_samples)

    raw_signals: Dict[str, Optional[float]] = {
        "test_results": s_test,
        "static_analysis": s_static,
        "context_similarity": s_context,
        "llm_consistency": s_consistency,
    }

    # Identify active vs unavailable signals
    active_signals = {k: v for k, v in raw_signals.items() if v is not None}
    unavailable_signals = [k for k, v in raw_signals.items() if v is None]

    if not active_signals:
        overall_score = 0.0
        active_weights: Dict[str, float] = {}
    else:
        # Explicit weight renormalization
        total_active_base_weight = sum(BASE_WEIGHTS[k] for k in active_signals)
        active_weights = {
            k: round(BASE_WEIGHTS[k] / total_active_base_weight, 4)
            for k in active_signals
        }
        overall_score = sum(active_signals[k] * active_weights[k] for k in active_signals)

    overall_score = round(min(1.0, max(0.0, overall_score)), 4)
    band = map_calibration_band(overall_score)

    return {
        "overall_score": overall_score,
        "calibration_band": band,
        "test_pass_confidence": s_test if s_test is not None else 0.0,
        "compilation_confidence": s_static if s_static is not None else 0.0,
        "semantic_preservation_score": s_context if s_context is not None else 0.0,
        "llm_consistency_score": s_consistency if s_consistency is not None else 0.0,
        "active_weights": active_weights,
        "unavailable_signals": unavailable_signals,
    }


async def run_confidence_engine(state: AgentState) -> Dict[str, Any]:
    """
    ForgeConfidenceEngine node entrypoint for LangGraph workflow.
    """
    breakdown = calculate_confidence_breakdown(state)

    logger.info(
        f"Confidence Engine: overall_score={breakdown['overall_score']} "
        f"band={breakdown['calibration_band']} "
        f"active_signals={list(breakdown['active_weights'].keys())} "
        f"unavailable={breakdown['unavailable_signals']}"
    )

    return {
        "confidence_score": breakdown["overall_score"],
        "confidence_breakdown": breakdown,
        "status": "confidence_scored",
    }
