import os
from pathlib import Path

BASE_DIR = Path("fixforge")

FILES = {
    ".env.example": """GROQ_API_KEY=""
OPENROUTER_API_KEY=""
GITHUB_TOKEN=""
GITHUB_WEBHOOK_SECRET="mock_secret"
CHROMA_PERSIST_DIR="./chroma_data"
DATABASE_URL="sqlite:///./fixforge.db"
DOCKER_SANDBOX_IMAGE="fixforge-sandbox:latest"
PORT="8000"
""",
    ".env": """GROQ_API_KEY=""
OPENROUTER_API_KEY=""
GITHUB_TOKEN=""
GITHUB_WEBHOOK_SECRET="mock_secret"
CHROMA_PERSIST_DIR="./chroma_data"
DATABASE_URL="sqlite:///./fixforge.db"
DOCKER_SANDBOX_IMAGE="fixforge-sandbox:latest"
PORT="8000"
""",
    "run_backend.py": """import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting FixForge Backend on port {port}...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
""",
    "scripts/build_sandbox.bat": """@echo off
echo Building FixForge Docker Sandbox Image...
docker build -t fixforge-sandbox:latest -f sandbox/Dockerfile.sandbox .
echo Build Complete!
""",
    "scripts/build_sandbox.sh": """#!/bin/bash
echo "Building FixForge Docker Sandbox Image..."
docker build -t fixforge-sandbox:latest -f sandbox/Dockerfile.sandbox .
echo "Build Complete!"
""",
    "scripts/verify_backend.py": """import httpx
import docker
import chromadb
import os
import json
import asyncio
import hmac
import hashlib
import sys

# Add parent directory to path so we can import core.config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings

async def verify():
    print("1. Checking FastAPI Health Endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/")
            resp.raise_for_status()
            print("   ✅ Server is live:", resp.json())
    except Exception as e:
        print("   ❌ Server unreachable:", type(e).__name__)

    print("2. Checking Docker Connectivity...")
    try:
        client = docker.from_env()
        client.ping()
        print("   ✅ Docker is running and reachable.")
    except Exception as e:
        print("   ❌ Docker error:", type(e).__name__)

    print("3. Checking ChromaDB Persistence...")
    try:
        chroma_client = chromadb.PersistentClient(path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_data"))
        print("   ✅ ChromaDB is accessible.")
    except Exception as e:
        print("   ❌ ChromaDB error:", type(e).__name__)

    print("4. Checking LLM API Keys...")
    if settings.GROQ_API_KEY:
        print("   ✅ GROQ_API_KEY is configured.")
    else:
        print("   ⚠️ GROQ_API_KEY is NOT configured. Agent LLM calls may fail.")

    print("5. Triggering Mock Webhook Payload...")
    payload = {
        "action": "opened",
        "issue": {
            "number": 999,
            "title": "Mock Integration Bug",
            "body": "This is a mock payload to verify LangGraph workflow."
        },
        "repository": {
            "full_name": "test/repo",
            "clone_url": "https://github.com/test/repo.git"
        }
    }
    try:
        secret = settings.GITHUB_WEBHOOK_SECRET.encode() if settings.GITHUB_WEBHOOK_SECRET else b""
        payload_bytes = json.dumps(payload).encode()
        mac = hmac.new(secret, msg=payload_bytes, digestmod=hashlib.sha256)
        signature = "sha256=" + mac.hexdigest()
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://127.0.0.1:8000/api/webhooks/github", 
                json=payload,
                headers={"X-Hub-Signature-256": signature}
            )
            print("   ✅ Webhook Response:", resp.json())
    except Exception as e:
        print("   ❌ Webhook failed:", type(e).__name__)

if __name__ == "__main__":
    asyncio.run(verify())
"""
}

def scaffold():
    print(f"Generating Phase 6 Scripts in {BASE_DIR}...")
    for file_path, content in FILES.items():
        full_path = BASE_DIR / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        # Make scripts executable on Unix-like systems
        if file_path.endswith('.sh'):
            try:
                os.chmod(full_path, 0o755)
            except Exception:
                pass
        print(f"Created: {full_path}")
    print("Phase 6 fully implemented.")

if __name__ == "__main__":
    scaffold()
