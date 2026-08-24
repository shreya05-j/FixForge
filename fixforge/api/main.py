from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from graph.workflow import build_workflow
import json
import asyncio

app = FastAPI(title="FixForge Orchestrator API")
workflow = build_workflow()

# Basic in-memory store for states (for demo purposes)
sessions = {}

@app.post("/api/webhooks/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    action = payload.get("action")
    if action in ["opened", "synchronize", "reopened"]:
        issue_id = str(payload.get("issue", {}).get("number", "1"))
        state = {
            "repo_name": payload.get("repository", {}).get("full_name", "unknown/repo"),
            "issue_id": issue_id,
            "issue_title": payload.get("issue", {}).get("title", ""),
            "issue_body": payload.get("issue", {}).get("body", ""),
            "retry_count": 0
        }
        
        def run_graph(initial_state):
            for output in workflow.stream(initial_state):
                sessions[issue_id] = output
        
        background_tasks.add_task(run_graph, state)
        return {"status": "accepted", "issue_id": issue_id}
        
    return {"status": "ignored"}

@app.get("/api/session/{issue_id}/trace")
async def stream_trace(issue_id: str):
    async def event_stream():
        while True:
            if issue_id in sessions:
                yield f"data: {json.dumps(sessions[issue_id], default=str)}\n\n"
            await asyncio.sleep(1)
            
    return StreamingResponse(event_stream(), media_type="text/event-stream")
