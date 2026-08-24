import docker
from core.config import settings

def run_in_sandbox(repo_path: str, test_cmd: str = "pytest"):
    client = docker.from_env()
    try:
        container = client.containers.run(
            "fixforge-sandbox:latest",
            test_cmd,
            volumes={repo_path: {'bind': '/app', 'mode': 'rw'}},
            working_dir="/app",
            network_mode="none",  # Net-isolated
            mem_limit="512m",
            detach=False,
            auto_remove=True
        )
        return True, container.decode('utf-8')
    except docker.errors.ContainerError as e:
        return False, e.stderr.decode('utf-8')
    except Exception as e:
        return False, str(e)
