from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
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
