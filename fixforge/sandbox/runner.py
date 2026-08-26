import docker
import tarfile
import tempfile
import os
from pathlib import Path
from core.config import settings
from typing import Dict, Any

def run_in_sandbox(repo_path: str, diff_patch: str, test_cmd: str = "pytest") -> Dict[str, Any]:
    """
    Uses Docker SDK to spin up a disposable container running tests safely.
    """
    client = docker.from_env()
    container = None
    
    # We create a temporary script to run inside the container
    entrypoint_script = f"""#!/bin/bash
set -e
cp -r /app_src/* /app_scratch/
cd /app_scratch
echo "{diff_patch}" > patch.diff
if [ -s patch.diff ] && [ "$(cat patch.diff | grep '---' | wc -l)" -gt 0 ]; then
    git apply patch.diff || true
fi
{test_cmd}
"""
    
    try:
        container = client.containers.run(
            settings.DOCKER_SANDBOX_IMAGE,
            command=["/bin/bash", "-c", entrypoint_script],
            volumes={
                repo_path: {'bind': '/app_src', 'mode': 'ro'}
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
        logs = container.logs(stdout=True, stderr=True).decode('utf-8')
        
        return {
            "passed": (exit_code == 0),
            "exit_code": exit_code,
            "stdout": logs,
            "stderr": "" # Combined in logs for simplicity here
        }
    except docker.errors.ContainerError as e:
        return {"passed": False, "exit_code": e.exit_status, "stdout": "", "stderr": e.stderr.decode('utf-8')}
    except Exception as e:
        return {"passed": False, "exit_code": -1, "stdout": "", "stderr": str(e)}
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
