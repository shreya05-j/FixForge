import os
from pathlib import Path

BASE_DIR = Path("fixforge")

FILES = {
    "requirements.txt": """fastapi==0.104.1
uvicorn==0.24.0.post1
langgraph==0.0.26
langchain==0.1.0
pydantic==2.5.2
pydantic-settings==2.1.0
sqlalchemy==2.0.23
chromadb==0.4.22
tree-sitter==0.20.4
tree-sitter-python==0.20.4
docker==6.1.3
semgrep==1.51.0
pytest==7.4.3
pytest-asyncio==0.21.1
requests==2.31.0
httpx==0.27.0
groq==0.4.1
openai==1.14.3
instructor==1.2.6
""",
    "core/config.py": """from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    DOCKER_SANDBOX_IMAGE: str = "fixforge-sandbox:latest"
    MAX_RETRIES: int = 3
    CONTAINER_TIMEOUT_SEC: int = 60
    MAX_CONTAINER_MEMORY: str = "512m"
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
""",
    "api/services/github.py": """import httpx
from core.config import settings

async def post_pr_review_comment(repo_name: str, issue_number: str, markdown_body: str):
    \"\"\"
    Posts a structured Markdown review comment to a GitHub PR or Issue.
    \"\"\"
    if not settings.GITHUB_TOKEN:
        print("No GITHUB_TOKEN configured, skipping PR comment posting.")
        return
        
    url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"body": markdown_body})
        response.raise_for_status()
        return response.json()
""",
    "agents/reporter.py": """from core.state import AgentState
from memory.chroma_client import chroma_manager
from api.services.github import post_pr_review_comment
import uuid

async def run_reporter(state: AgentState) -> AgentState:
    \"\"\"
    ForgeReporter: Formats markdown review comment and saves verified resolution.
    Posts the report natively back to GitHub via REST API.
    \"\"\"
    if state.get('test_results', {}).get('passed'):
        chroma_manager.add_historical_fix(
            fix_id=str(uuid.uuid4()),
            description=state.get('diagnosis_summary', ''),
            metadata={"severity": state.get('severity', ''), "diff": state.get('candidate_diff', '')}
        )
    
    report = f\"\"\"# FixForge Autonomous Repair Report

## 🔍 Diagnosis
**Category**: {state.get('failure_category')} | **Severity**: {state.get('severity')}
{state.get('diagnosis_summary')}

## 🔬 Execution & Verification
- **Test Passed**: `{"YES" if state.get('test_results', {}).get('passed') else "NO"}`
- **Retries Used**: `{state.get('retry_count', 0)}/3`

<details><summary><b>Pytest Output</b></summary>

```
{state.get('test_results', {}).get('stdout', '')}
```
</details>

## 📊 Confidence Score: {state.get('confidence_score', 0.0) * 100:.1f}%

## 💻 Proposed Patch
```diff
{state.get('candidate_diff')}
```
\"\"\"

    try:
        await post_pr_review_comment(state.get('repo_name', ''), state.get('issue_id', ''), report)
    except Exception as e:
        print(f"Failed to post GitHub PR comment: {e}")

    state['status'] = 'reporter_completed'
    return state
""",
    "api/routes/webhooks.py": """from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
import hmac
import hashlib
from graph.workflow import build_workflow
from core.config import settings

router = APIRouter()
workflow = build_workflow()

sessions = {}

def verify_signature(payload: bytes, signature: str) -> bool:
    if not settings.GITHUB_WEBHOOK_SECRET:
        return True # Skip validation if no secret is configured
    
    mac = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@router.post("/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks, x_hub_signature_256: str = Header(None)):
    payload_bytes = await request.body()
    if not verify_signature(payload_bytes, x_hub_signature_256 or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    action = payload.get("action")
    
    # Listen for pull_request and issues events
    if action in ["opened", "synchronize", "reopened", "labeled"]:
        issue_data = payload.get("pull_request") or payload.get("issue")
        if not issue_data:
            return {"status": "ignored"}
            
        issue_id = str(issue_data.get("number", "1"))
        state = {
            "repo_name": payload.get("repository", {}).get("full_name", "unknown/repo"),
            "issue_id": issue_id,
            "issue_title": issue_data.get("title", ""),
            "issue_body": issue_data.get("body", ""),
            "retry_count": 0,
            "status": "pending_orchestration"
        }
        
        async def run_graph(initial_state):
            # Asynchronously trigger the LangGraph cyclic workflow
            async for output in workflow.astream(initial_state):
                sessions[issue_id] = output
                
        background_tasks.add_task(run_graph, state)
        return {"status": "accepted", "issue_id": issue_id}
        
    return {"status": "ignored"}
""",
    "api/main.py": """from fastapi import FastAPI
from api.routes import webhooks, sessions
from db.session import init_db

app = FastAPI(title="FixForge API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "FixForge Orchestrator"}
""",
    "tests/test_e2e_repair.py": """import pytest
from unittest.mock import patch, AsyncMock
from core.state import AgentState
from graph.workflow import build_workflow
from agents.planner import PlannerOutput
from agents.diagnoser import DiagnoserOutput
from agents.fixer import FixerOutput

@pytest.mark.asyncio
async def test_end_to_end_repair():
    \"\"\"
    End-to-End Seeded Test Harness
    Validates webhook payload ingestion mimicking, multi-agent LLM logic wrapping,
    Docker test sandbox loop termination, and confidence score generation.
    \"\"\"
    workflow = build_workflow()
    
    # 1. Seeded initial state mimicking a Webhook Payload for a subtle KeyError
    initial_state: AgentState = {
        "repo_name": "test/repo",
        "issue_id": "1",
        "issue_title": "Fix KeyError in config loader",
        "issue_body": "There is a KeyError when config is missing 'host'.",
        "retry_count": 0,
        "test_results": {},
        "target_files": [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "diagnosis_summary": "",
        "failure_category": "Runtime Error",
        "severity": "Medium",
        "candidate_diff": "",
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": ""
    }
    
    # 2. Patch out the LLM calls and Docker executions to mimic a realistic pass
    with patch("agents.planner.async_llm_client.chat.completions.create", new_callable=AsyncMock) as mock_planner, \\
         patch("agents.diagnoser.async_llm_client.chat.completions.create", new_callable=AsyncMock) as mock_diagnoser, \\
         patch("agents.fixer.async_llm_client.chat.completions.create", new_callable=AsyncMock) as mock_fixer, \\
         patch("agents.verifier.run_in_sandbox", return_value={"passed": True, "exit_code": 0, "stdout": "1 passed in 0.1s", "stderr": ""}), \\
         patch("agents.reporter.post_pr_review_comment", new_callable=AsyncMock) as mock_post_comment:
        
        # Setup specific LLM structured mock returns
        mock_planner.return_value = PlannerOutput(plan="Find KeyError and patch with .get()", target_files=["config.py"])
        mock_diagnoser.return_value = DiagnoserOutput(diagnosis_summary="KeyError on missing dict key", failure_category="Logic Error", severity="Medium")
        mock_fixer.return_value = FixerOutput(candidate_diff=\"\"\"--- a/config.py
+++ b/config.py
@@ -1,2 +1,2 @@
-def load_host(config): return config['host']
+def load_host(config): return config.get('host', 'localhost')
\"\"\")

        # 3. Execute the workflow asynchronously (End-to-End orchestration)
        final_state = await workflow.ainvoke(initial_state)
        
        # 4. Verify loop terminated cleanly and status is marked complete
        assert final_state["status"] == "reporter_completed", "Pipeline failed to terminate at Reporter."
        assert final_state["test_results"]["passed"] is True, "Test results did not verify as passed."
        assert final_state["retry_count"] == 0, "Pipeline entered unexpected retry loop."
        assert final_state["confidence_score"] > 0.0, "Confidence Engine failed to calculate a positive score."
        
        # 5. Verify GitHub Comment integration was accurately requested
        mock_post_comment.assert_called_once()
        args, kwargs = mock_post_comment.call_args
        assert args[0] == "test/repo"
        assert args[1] == "1"
        assert "FixForge Autonomous Repair Report" in args[2], "Generated report missing expected Markdown title."
"""
}

def scaffold():
    print(f"Generating Phase 5 Webhooks & Testing in {BASE_DIR}...")
    for file_path, content in FILES.items():
        full_path = BASE_DIR / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {full_path}")
    print("Phase 5 fully implemented.")

if __name__ == "__main__":
    scaffold()
