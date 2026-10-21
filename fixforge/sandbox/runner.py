import docker
import os
import shutil
import tempfile
from typing import Dict, Any
from core.config import settings

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
            "error": git_err or "git apply --check rejected candidate patch"
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
    - Writes the patch to a file (never echoed through bash).
    - Runs `git apply --check` first; if it fails, returns status="patch_failed" with git error.
    - If Docker is unavailable, returns status="unverified" (NEVER passed).
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
        client = docker.from_env(timeout=5)
        client.ping()
    except (docker.errors.DockerException, Exception) as e:
        return {
            "status": "unverified",
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Docker daemon unavailable: {e}",
            "error": f"Docker daemon unavailable: {e}"
        }

    container = None
    patch_tmpdir = None

    try:
        # 2. Write candidate patch to a dedicated temporary file (LF line endings)
        patch_tmpdir = tempfile.mkdtemp(prefix="fixforge_patch_")
        patch_file_path = os.path.join(patch_tmpdir, "patch.diff")
        clean_patch = (diff_patch or "").replace("\r\n", "\n")
        with open(patch_file_path, "w", encoding="utf-8", newline="\n") as pf:
            pf.write(clean_patch)

        entrypoint_script = f"""#!/bin/bash
set -e
cp -r /app_src/* /app_scratch/
cd /app_scratch

if [ -s /app_patch/patch.diff ]; then
    echo "=== FIXFORGE_CHECKING_PATCH ==="
    if ! git apply --check /app_patch/patch.diff 2>&1; then
        echo "=== FIXFORGE_PATCH_FAILED ==="
        exit 42
    fi
    git apply /app_patch/patch.diff
fi

echo "=== FIXFORGE_RUNNING_TESTS ==="
{test_cmd}
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

    except (docker.errors.DockerException, Exception) as e:
        return {
            "status": "unverified",
            "passed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "error": str(e)
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
