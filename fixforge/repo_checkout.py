"""
repo_checkout.py - isolated helper for cloning a GitHub repository into a
temporary directory that the caller owns and must clean up.

Errors are returned in a structured dict so callers can surface them through
the pipeline without hiding them:
    {"path": str | None, "status": "ok" | "failed", "error": str}

No external libraries beyond git (on PATH) and standard library.
"""

import logging
import os
import re
import subprocess
import tempfile
from typing import Dict, Any

logger = logging.getLogger(__name__)


def checkout_repo(
    repo_url: str,
    ref: str = "HEAD",
    timeout_sec: int = 60,
) -> Dict[str, Any]:
    """
    Clone *repo_url* into a fresh TemporaryDirectory and check out *ref*.

    The caller is responsible for cleanup (call result["tmpdir"].cleanup()).
    The returned dict always contains:
        "path":   str  - absolute path to the checkout root, or None on failure.
        "tmpdir": TemporaryDirectory instance to be cleaned up by caller.
        "status": "ok" | "failed"
        "error":  "" on success, human-readable message on failure.

    Failure cases handled explicitly:
        - network / DNS errors (clone exits non-zero)
        - invalid / 404 URL
        - clone timeout
        - ref that does not exist
        - anything else (disk full, permission denied)
    """
    tmpdir = tempfile.TemporaryDirectory(prefix="fixforge_checkout_")
    checkout_path = tmpdir.name

    # Strip issue or pull request suffix if an issue/PR URL was passed
    base_repo_url = re.sub(r'/(?:issues|pull)/\d+.*$', '', repo_url.rstrip('/'))

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if github_token and "github.com" in base_repo_url:
        clone_url = base_repo_url.replace(
            "https://github.com/",
            f"https://{github_token}@github.com/",
        )
    else:
        clone_url = base_repo_url

    logger.info(f"Cloning repo {base_repo_url} into {checkout_path} (ref={ref})")

    clone_cmd = [
        "git", "clone",
        "--depth", "1",
        "--no-tags",
        clone_url,
        checkout_path,
    ]
    try:
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        tmpdir.cleanup()
        msg = f"git clone timed out after {timeout_sec}s for {repo_url}"
        logger.error(msg)
        return {"path": None, "tmpdir": None, "status": "failed", "error": msg}
    except FileNotFoundError:
        tmpdir.cleanup()
        msg = "git executable not found on PATH"
        logger.error(msg)
        return {"path": None, "tmpdir": None, "status": "failed", "error": msg}

    if result.returncode != 0:
        tmpdir.cleanup()
        stderr = result.stderr.strip()
        msg = f"git clone failed (exit {result.returncode}): {stderr}"
        logger.error(msg)
        return {"path": None, "tmpdir": None, "status": "failed", "error": msg}

    if ref not in ("HEAD", "", "main", "master"):
        checkout_cmd = ["git", "-C", checkout_path, "checkout", ref]
        try:
            co_result = subprocess.run(
                checkout_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            tmpdir.cleanup()
            msg = f"git checkout of ref '{ref}' timed out"
            logger.error(msg)
            return {"path": None, "tmpdir": None, "status": "failed", "error": msg}

        if co_result.returncode != 0:
            tmpdir.cleanup()
            stderr = co_result.stderr.strip()
            msg = f"git checkout '{ref}' failed (exit {co_result.returncode}): {stderr}"
            logger.error(msg)
            return {"path": None, "tmpdir": None, "status": "failed", "error": msg}

    logger.info(f"Checkout successful: {checkout_path}")
    return {"path": checkout_path, "tmpdir": tmpdir, "status": "ok", "error": ""}


def find_python_files(root: str, max_files: int = 50) -> list:
    """
    Walk *root* and return absolute paths of Python files (up to max_files).
    Used as keyword-search fallback when Planner target_files is empty.
    """
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in (
                "__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build"
            )
        ]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(os.path.join(dirpath, fname))
                if len(py_files) >= max_files:
                    return py_files
    return py_files
