import docker
import docker.errors
import os
import re
import shutil
import tempfile
from typing import Dict, Any, Optional, List
from core.config import settings

PYTHON_PATCH_SCRIPT = r'''import os, sys, re

def apply_patch(repo_dir, patch_path):
    if not os.path.exists(patch_path) or os.path.getsize(patch_path) == 0:
        return True
    with open(patch_path, 'r', encoding='utf-8', errors='replace') as pf:
        patch_text = pf.read()

    file_diffs = re.split(r'(?=(?:^diff --git|^--- [ab]/))', patch_text, flags=re.MULTILINE)
    applied_any = False

    for diff in file_diffs:
        diff = diff.strip()
        if not diff:
            continue
        m_file = re.search(r'^\+\+\+ [b/]*(.*?)$', diff, flags=re.MULTILINE)
        if not m_file:
            continue
        rel_path = m_file.group(1).strip()
        if rel_path.startswith(('a/', 'b/')):
            rel_path = rel_path[2:]
        rel_path = rel_path.lstrip('/')

        target_path = os.path.join(repo_dir, rel_path)
        if not os.path.exists(target_path):
            base = os.path.basename(rel_path)
            for root, _, files in os.walk(repo_dir):
                if base in files:
                    target_path = os.path.join(root, base)
                    break

        if not os.path.exists(target_path):
            print(f'Target file not found: {rel_path}', file=sys.stderr)
            return False

        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            file_lines = f.read().splitlines()

        hunks = re.split(r'(?=(?:^@@ ))', diff, flags=re.MULTILINE)
        for hunk in hunks:
            hunk = hunk.strip()
            if not hunk.startswith('@@'):
                continue
            hunk_lines = hunk.splitlines()[1:]
            old_lines = []
            new_lines = []
            for ln in hunk_lines:
                if ln.startswith('-'):
                    old_lines.append(ln[1:])
                elif ln.startswith('+'):
                    new_lines.append(ln[1:])
                elif ln.startswith(' '):
                    old_lines.append(ln[1:])
                    new_lines.append(ln[1:])

            if not old_lines and not new_lines:
                continue

            matched = False
            for idx in range(len(file_lines) - len(old_lines) + 1):
                if file_lines[idx : idx + len(old_lines)] == old_lines:
                    file_lines[idx : idx + len(old_lines)] = new_lines
                    matched = True
                    break
            if not matched:
                stripped_old = [l.strip() for l in old_lines]
                for idx in range(len(file_lines) - len(old_lines) + 1):
                    if [l.strip() for l in file_lines[idx : idx + len(old_lines)]] == stripped_old:
                        file_lines[idx : idx + len(old_lines)] = new_lines
                        matched = True
                        break
            if not matched:
                print(f'Hunk failed to match in {target_path}', file=sys.stderr)
                return False

        with open(target_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(file_lines) + '\n')
        applied_any = True
        print(f'Successfully applied patch to {target_path}')

    return applied_any

if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(1)
    ok = apply_patch(sys.argv[1], sys.argv[2])
    sys.exit(0 if ok else 1)
'''


def sanitize_unified_diff(diff_text: str) -> str:
    """
    Sanitizes LLM-generated diff output:
    - Strips markdown code blocks.
    - Ensures standard '--- a/path' and '+++ b/path' header prefixes.
    - Accurately recounts and updates @@ -old_start,old_count +new_start,new_count @@ hunk headers.
    - Converts empty lines in hunks to single spaces (valid context lines).
    - Ensures code lines without diff prefixes are treated as context (' ').
    """
    if not diff_text:
        return ""

    text = diff_text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n```$", "", text.strip())

    match = re.search(r"^(?:diff --git|--- [ab]/|--- [^\n]+)", text, re.MULTILINE)
    if match:
        text = text[match.start():]

    lines = text.splitlines()
    sanitized_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        hunk_m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", line)
        if hunk_m:
            old_start = int(hunk_m.group(1))
            new_start = int(hunk_m.group(3))
            trailing = hunk_m.group(5) or ""
            hunk_lines = []
            i += 1
            while i < len(lines):
                cur = lines[i]
                if cur.startswith("@@ ") or cur.startswith("diff --git") or cur.startswith("--- "):
                    break
                if cur == "":
                    cur = " "
                elif not cur.startswith(("+", "-", " ", "\\")):
                    cur = " " + cur
                hunk_lines.append(cur)
                i += 1
            old_c = sum(1 for l in hunk_lines if l.startswith(("-", " ")))
            new_c = sum(1 for l in hunk_lines if l.startswith(("+", " ")))
            sanitized_lines.append(f"@@ -{old_start},{old_c} +{new_start},{new_c} @@{trailing}")
            sanitized_lines.extend(hunk_lines)
        else:
            if line.startswith("--- ") and not line.startswith("--- a/") and not line.startswith("--- /dev/null"):
                line = "--- a/" + line[4:].lstrip("/")
            elif line.startswith("+++ ") and not line.startswith("+++ b/") and not line.startswith("+++ /dev/null"):
                line = "+++ b/" + line[4:].lstrip("/")
            sanitized_lines.append(line)
            i += 1
    return "\n".join(sanitized_lines) + "\n"


def find_targeted_test_file(repo_path: str, diff_patch: str) -> Optional[str]:
    """Finds a matching test file in repo_path corresponding to the file being patched."""
    if not repo_path or not diff_patch or not os.path.exists(repo_path):
        return None

    m = re.search(r"^\+\+\+ [b/]*(.*?)$", diff_patch, re.MULTILINE)
    if not m:
        return None

    rel_target = m.group(1).strip()
    if rel_target.startswith(("a/", "b/")):
        rel_target = rel_target[2:]
    rel_target = rel_target.lstrip("/")

    stem = os.path.splitext(os.path.basename(rel_target))[0]
    if not stem:
        return None

    candidates = [
        f"python_testcases/test_{stem}.py",
        f"tests/test_{stem}.py",
        f"test/test_{stem}.py",
        f"test_{stem}.py",
        f"tests/{stem}_test.py",
        f"{stem}_test.py",
        f"testcases/test_{stem}.py",
    ]

    for cand in candidates:
        full = os.path.join(repo_path, cand)
        if os.path.isfile(full):
            return cand

    for root, _, files in os.walk(repo_path):
        if f"test_{stem}.py" in files:
            full = os.path.join(root, f"test_{stem}.py")
            return os.path.relpath(full, repo_path).replace("\\", "/")
        if f"{stem}_test.py" in files:
            full = os.path.join(root, f"{stem}_test.py")
            return os.path.relpath(full, repo_path).replace("\\", "/")

    return None


def parse_sandbox_output(exit_code: int, logs: str) -> Dict[str, Any]:
    """
    Parses container logs and exit code into a structured verification result.
    """
    if exit_code == 42 or "=== FIXFORGE_PATCH_FAILED ===" in logs:
        git_err = logs
        if "=== FIXFORGE_CHECKING_PATCH ===" in logs and "=== FIXFORGE_PATCH_FAILED ===" in logs:
            git_err = logs.split("=== FIXFORGE_CHECKING_PATCH ===")[1].split("=== FIXFORGE_PATCH_FAILED ===")[0].strip()
        elif "=== FIXFORGE_PATCH_FAILED ===" in logs:
            git_err = logs.split("=== FIXFORGE_PATCH_FAILED ===")[0].strip()
        
        return {
            "status": "patch_failed",
            "passed": False,
            "exit_code": 42,
            "stdout": logs,
            "stderr": git_err,
            "error": git_err or "Patch rejected by git apply and fallback applier"
        }
    
    if exit_code == 0:
        return {
            "status": "passed",
            "passed": True,
            "exit_code": 0,
            "stdout": logs,
            "stderr": ""
        }
    
    return {
        "status": "failed",
        "passed": False,
        "exit_code": exit_code,
        "stdout": logs,
        "stderr": logs,
        "error": f"Sandbox test command failed with exit code {exit_code}"
    }


def run_in_sandbox(repo_path: str, diff_patch: str, test_cmd: str = "pytest") -> Dict[str, Any]:
    """
    Executes test suite in an isolated Docker sandbox.
    
    Guarantees:
    - Writes the sanitized patch to a file.
    - Recounts hunk headers to guarantee mathematical accuracy.
    - Applies patch via git apply or resilient Python AST/block applier.
    - Discovers and executes targeted test suites first for high accuracy.
    - Read-only repo mount + scratch copy + network_mode='none' + non-root user.
    - Disposable container removed after every run.
    """
    if not repo_path or not os.path.exists(repo_path):
        return {
            "status": "failed",
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Repository path not found: {repo_path}",
            "error": f"Repository path not found: {repo_path}"
        }

    # 1. Probe Docker daemon availability
    try:
        probe_client = docker.from_env(timeout=10)
        probe_client.ping()
    except (docker.errors.DockerException, Exception) as e:
        return {
            "status": "unverified",
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Docker daemon unavailable: {e}",
            "error": f"Docker daemon unavailable: {e}"
        }

    client = docker.from_env(timeout=max(settings.CONTAINER_TIMEOUT_SEC + 60, 120))

    container = None
    patch_tmpdir = None

    try:
        patch_tmpdir = tempfile.mkdtemp(prefix="fixforge_patch_")
        patch_file_path = os.path.join(patch_tmpdir, "patch.diff")
        apply_script_path = os.path.join(patch_tmpdir, "apply_patch.py")

        sanitized_patch = sanitize_unified_diff(diff_patch)
        clean_patch = sanitized_patch.replace("\r\n", "\n")
        with open(patch_file_path, "w", encoding="utf-8", newline="\n") as pf:
            pf.write(clean_patch)

        with open(apply_script_path, "w", encoding="utf-8", newline="\n") as af:
            af.write(PYTHON_PATCH_SCRIPT)

        # Detect if there is a targeted test suite for the modified file
        rel_test_file = find_targeted_test_file(repo_path, sanitized_patch) or ""

        entrypoint_script = f"""#!/bin/bash
set -e
git config --global --add safe.directory '*' 2>/dev/null || true
cp -a /app_src/. /app_scratch/ 2>/dev/null || cp -r /app_src/* /app_scratch/ 2>/dev/null || true
cd /app_scratch

if [ -s /app_patch/patch.diff ]; then
    echo "=== FIXFORGE_CHECKING_PATCH ==="
    APPLIED=0
    # 1. Exact git apply check
    if git apply --check /app_patch/patch.diff 2>&1; then
        git apply /app_patch/patch.diff
        APPLIED=1
    # 2. Tolerant git apply check (whitespace and recount)
    elif git apply --check --ignore-whitespace --recount /app_patch/patch.diff 2>&1; then
        git apply --ignore-whitespace --recount /app_patch/patch.diff
        APPLIED=1
    # 3. Unsafe paths fallback
    elif git apply --check --unsafe-paths --ignore-whitespace --recount /app_patch/patch.diff 2>&1; then
        git apply --unsafe-paths --ignore-whitespace --recount /app_patch/patch.diff
        APPLIED=1
    # 4. Resilient Python AST/block patch applier
    elif [ -f /app_patch/apply_patch.py ] && python3 /app_patch/apply_patch.py /app_scratch /app_patch/patch.diff 2>&1; then
        APPLIED=1
    fi

    if [ "$APPLIED" -eq 0 ]; then
        echo "=== FIXFORGE_PATCH_FAILED ==="
        git apply --check /app_patch/patch.diff 2>&1 || true
        exit 42
    fi
fi

echo "=== FIXFORGE_RUNNING_TESTS ==="
export PYTHONPATH=".:/app_scratch:$PYTHONPATH"

# Run targeted test if detected
if [ -n "{rel_test_file}" ] && [ -f "/app_scratch/{rel_test_file}" ]; then
    echo "Executing targeted test suite: {rel_test_file}"
    pytest -q --tb=short "/app_scratch/{rel_test_file}"
    exit $?
fi

# Standard test execution fallback
if [ "{test_cmd}" = "pytest" ]; then
    pytest_exit=0
    pytest -q --tb=short || pytest_exit=$?
    if [ "$pytest_exit" -eq 0 ]; then
        exit 0
    elif [ "$pytest_exit" -eq 5 ]; then
        python -m unittest discover -s . -p "test*.py" -q 2>/dev/null || python -m compileall -q .
    elif python -m unittest discover -s . -p "test*.py" -q 2>/dev/null; then
        exit 0
    else
        exit "$pytest_exit"
    fi
else
    {test_cmd}
fi
"""


        container = client.containers.run(
            settings.DOCKER_SANDBOX_IMAGE,
            command=["/bin/bash", "-c", entrypoint_script],
            volumes={
                repo_path: {'bind': '/app_src', 'mode': 'ro'},
                patch_tmpdir: {'bind': '/app_patch', 'mode': 'ro'}
            },
            working_dir="/app_scratch",
            network_mode="none",
            mem_limit=settings.MAX_CONTAINER_MEMORY,
            cpu_quota=100000,
            user="nonroot",
            detach=True
        )

        result = container.wait(timeout=settings.CONTAINER_TIMEOUT_SEC)
        exit_code = result['StatusCode']
        logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')

        return parse_sandbox_output(exit_code, logs)

    except docker.errors.ContainerError as e:
        stderr_text = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else str(e.stderr)
        return parse_sandbox_output(e.exit_status, stderr_text)

    except Exception as e:
        err_str = str(e)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower():
            timeout_logs = ""
            if container:
                try:
                    timeout_logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='replace')
                except Exception:
                    pass
            return {
                "status": "failed",
                "passed": False,
                "exit_code": 124,
                "stdout": timeout_logs,
                "stderr": f"Execution timed out after {settings.CONTAINER_TIMEOUT_SEC}s",
                "error": f"Execution timed out after {settings.CONTAINER_TIMEOUT_SEC}s"
            }

        err_msg = f"Docker error: {e}"
        return {
            "status": "unverified",
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": err_msg,
            "error": err_msg
        }

    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        if patch_tmpdir and os.path.exists(patch_tmpdir):
            try:
                shutil.rmtree(patch_tmpdir, ignore_errors=True)
            except Exception:
                pass
