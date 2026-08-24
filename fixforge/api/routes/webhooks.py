from fastapi import APIRouter, Request, BackgroundTasks
from graph.workflow import build_graph

router = APIRouter()
graph = build_graph()

@router.post("/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    action = payload.get("action")
    
    if action in ["opened", "reopened"] and "issue" in payload:
        issue = payload["issue"]
        state = {
            "issue_id": str(issue["id"]),
            "github_url": issue["html_url"],
            "issue_description": issue["body"],
            "repo_path": f"/tmp/repos/{issue['id']}",
            "iteration_count": 0
        }
        
        # Trigger background execution
        background_tasks.add_task(graph.invoke, state)
        return {"status": "accepted", "issue_id": state["issue_id"]}
        
    return {"status": "ignored"}
