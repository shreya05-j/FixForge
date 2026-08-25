from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.session import get_db
from db.models import FixSession

router = APIRouter()

class ActionRequest(BaseModel):
    action: str

@router.get("")
def list_sessions(db: Session = Depends(get_db)):
    """Fetch all historical review sessions with their status and scores."""
    sessions = db.query(FixSession).all()
    return [{
        "id": s.id,
        "status": s.status,
        "repository": getattr(s, "repo_url", "unknown"),
        "branch": getattr(s, "branch", "main"),
        "failure_classification": getattr(s, "failure_classification", "Unclassified"),
        "confidence_score": getattr(s, "confidence_score", 0.0)
    } for s in sessions]

@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Fetch complete normalized session state including diffs and logs."""
    session = db.query(FixSession).filter(FixSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "id": session.id,
        "status": session.status,
        "repository": getattr(session, "repo_url", "unknown"),
        "patch_diff": getattr(session, "patch_diff", ""),
        "test_logs": getattr(session, "test_logs", ""),
        "ast_symbols": getattr(session, "ast_symbols", []),
        "severity_rating": getattr(session, "severity_rating", "medium"),
        "confidence_score": getattr(session, "confidence_score", 0.0),
        "created_at": getattr(session, "created_at", None)
    }

@router.post("/{session_id}/action")
def handle_action(session_id: str, payload: ActionRequest, db: Session = Depends(get_db)):
    """Handle Human-in-the-Loop actions (approve_pr, request_retry, dismiss)."""
    session = db.query(FixSession).filter(FixSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if payload.action not in ["approve_pr", "request_retry", "dismiss"]:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    # Example state update based on action
    if payload.action == "approve_pr":
        session.status = "approved"
    elif payload.action == "request_retry":
        session.status = "retrying"
    elif payload.action == "dismiss":
        session.status = "dismissed"
        
    db.commit()
    return {"status": "success", "action": payload.action, "session_id": session_id}
