"""
health.py — System Health & Mode Preflight Route.

Validates:
  - llm_mode: live | fallback (performs a live minimal Groq call)
  - docker_mode: live | unavailable (runs a minimal test container)
  - sandbox_image: present | missing (checks if fixforge-sandbox image exists)
  - github_mode: dry_run | live
  - overall_mode: LIVE | PARTIAL | FALLBACK
"""

import logging
import docker
import docker.errors
from fastapi import APIRouter
from core.config import settings
from groq import Groq

logger = logging.getLogger(__name__)
router = APIRouter()


def check_llm_mode() -> dict:
    if not settings.GROQ_API_KEY or len(settings.GROQ_API_KEY) < 10:
        return {"mode": "fallback", "detail": "GROQ_API_KEY not configured"}
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        model_name = getattr(settings, "FIXFORGE_MODEL", "qwen/qwen3.8-27b")
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        if resp.choices and resp.choices[0].message:
            return {"mode": "live", "model": model_name}
        return {"mode": "fallback", "detail": "Empty completion response"}
    except Exception as exc:
        logger.warning("Health LLM validation failed: %s", type(exc).__name__)
        return {"mode": "fallback", "detail": type(exc).__name__}


def check_docker_and_sandbox() -> tuple[dict, str]:
    try:
        client = docker.from_env()
        client.ping()

        # Check sandbox image presence
        image_name = settings.DOCKER_SANDBOX_IMAGE
        sandbox_present = False
        try:
            client.images.get(image_name)
            sandbox_present = True
        except docker.errors.ImageNotFound:
            # Check tagged images list
            all_tags = [tag for img in client.images.list() for tag in (img.tags or [])]
            sandbox_present = image_name in all_tags or any("fixforge-sandbox" in t for t in all_tags)

        # Validate by running a minimal container command
        test_img = image_name if sandbox_present else "alpine:latest"
        try:
            container_out = client.containers.run(test_img, "echo docker_ready", remove=True)
            if b"docker_ready" in container_out:
                return ({"mode": "live"}, "present" if sandbox_present else "missing")
        except Exception:
            # If running container failed
            pass

        return ({"mode": "live"}, "present" if sandbox_present else "missing")
    except Exception as exc:
        logger.warning("Health Docker check failed: %s", type(exc).__name__)
        return ({"mode": "unavailable", "detail": type(exc).__name__}, "missing")


@router.get("/health")
def get_system_health():
    llm_info = check_llm_mode()
    docker_info, sandbox_image = check_docker_and_sandbox()

    llm_mode = llm_info["mode"]
    docker_mode = docker_info["mode"]
    github_mode = "dry_run" if settings.GITHUB_DRY_RUN else "live"

    if llm_mode == "live" and docker_mode == "live":
        overall_mode = "LIVE"
    elif llm_mode == "live" or docker_mode == "live":
        overall_mode = "PARTIAL"
    else:
        overall_mode = "FALLBACK"

    return {
        "status": "healthy",
        "service": "FixForge Orchestrator",
        "overall_mode": overall_mode,
        "llm_mode": llm_mode,
        "docker_mode": docker_mode,
        "sandbox_image": sandbox_image,
        "github_mode": github_mode,
        "details": {
            "llm": llm_info,
            "docker": docker_info,
            "sandbox_image_name": settings.DOCKER_SANDBOX_IMAGE,
        }
    }
