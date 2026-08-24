import docker
from core.config import settings

def run_in_sandbox(repo_path: str, diff_patch: str, test_cmd: str = "pytest") -> tuple[bool, str]:
    """
    Secure Docker Execution Sandbox
    Spins up ephemeral containers with strict network, CPU, and memory limits.
    """
    client = docker.from_env()
    container = None
    
    try:
        # We start a container using our lightweight, unprivileged image
        # In a real scenario, we copy the repository to a tmp scratchpad to avoid modifying read-only host mount
        entrypoint_cmd = f"""
        cp -r /app_src/* /app_scratch/ && \
        cd /app_scratch && \
        echo "{diff_patch}" > patch.diff && \
        git apply patch.diff && \
        {test_cmd}
        """

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
