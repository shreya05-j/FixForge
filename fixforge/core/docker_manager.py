"""Docker daemon and FixForge sandbox image readiness helpers."""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import docker
import docker.errors

from core.config import settings

logger = logging.getLogger(__name__)

FIXFORGE_ROOT = Path(__file__).resolve().parents[1]


def _docker_client() -> Any:
    client = docker.from_env(timeout=max(settings.CONTAINER_TIMEOUT_SEC + 60, 120))
    client.ping()
    return client


def _start_docker_desktop() -> str | None:
    docker_command = shutil.which("docker")
    if docker_command:
        try:
            result = subprocess.run(
                [docker_command, "desktop", "start"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                return "Docker Desktop start command accepted"
            logger.info("Docker Desktop start command returned %s: %s", result.returncode, result.stderr.strip())
        except (OSError, subprocess.SubprocessError) as exc:
            logger.info("Docker Desktop CLI start was unavailable: %s", exc)

    if os.name == "nt":
        desktop_paths = (
            Path(os.environ.get("ProgramFiles", "")) / "Docker" / "Docker" / "Docker Desktop.exe",
            Path(os.environ.get("ProgramW6432", "")) / "Docker" / "Docker" / "Docker Desktop.exe",
        )
        for desktop_path in desktop_paths:
            if desktop_path.is_file():
                try:
                    subprocess.Popen([str(desktop_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return f"Started {desktop_path.name}"
                except OSError as exc:
                    logger.info("Could not start Docker Desktop at %s: %s", desktop_path, exc)
    return None


def _wait_for_daemon() -> Any:
    deadline = time.monotonic() + settings.DOCKER_START_TIMEOUT_SEC
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _docker_client()
        except (docker.errors.DockerException, OSError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Docker daemon did not become ready: {last_error}")


def ensure_docker_ready() -> dict[str, Any]:
    """Start Docker when needed and ensure the sandbox image is available."""
    try:
        client = _docker_client()
    except (docker.errors.DockerException, OSError):
        if not settings.DOCKER_AUTO_START:
            return {"mode": "unavailable", "detail": "Docker auto-start is disabled"}
        start_message = _start_docker_desktop()
        if not start_message:
            return {"mode": "unavailable", "detail": "Docker Desktop could not be started"}
        try:
            client = _wait_for_daemon()
        except RuntimeError as exc:
            return {"mode": "unavailable", "detail": str(exc)}

    try:
        client.images.get(settings.DOCKER_SANDBOX_IMAGE)
    except docker.errors.ImageNotFound:
        if not settings.DOCKER_BUILD_SANDBOX_ON_START:
            return {"mode": "live", "image": "missing", "detail": "Sandbox image build is disabled"}
        try:
            logger.info("Building missing sandbox image %s", settings.DOCKER_SANDBOX_IMAGE)
            client.images.build(
                path=str(FIXFORGE_ROOT),
                dockerfile="sandbox/Dockerfile.sandbox",
                tag=settings.DOCKER_SANDBOX_IMAGE,
                rm=True,
            )
        except (docker.errors.DockerException, OSError) as exc:
            logger.exception("Sandbox image build failed")
            return {"mode": "live", "image": "missing", "detail": f"Sandbox image build failed: {exc}"}
    except docker.errors.DockerException as exc:
        logger.exception("Could not inspect the Docker sandbox image")
        return {"mode": "unavailable", "detail": f"Docker image inspection failed: {exc}"}

    return {"mode": "live", "image": "present"}
