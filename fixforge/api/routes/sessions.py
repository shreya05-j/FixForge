import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from db.session import get_db
from db.models import ReviewSession

router = APIRouter()

class ActionRequest(BaseModel):
    action: str

@router.get("")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """Fetch all historical review sessions with their status and scores."""
    stmt = select(ReviewSession).options(
        selectinload(ReviewSession.diagnosis),
        selectinload(ReviewSession.metrics)
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    return [{
        "id": str(s.id),
        "status": s.status,
        "repository": s.repo_url,
        "branch": s.branch,
        "failure_classification": s.diagnosis.failure_classification if s.diagnosis else "Unclassified",
        "confidence_score": s.metrics.overall_score if s.metrics else 0.0,
        "created_at": s.created_at
    } for s in sessions]

@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch complete normalized session state including diffs and logs."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    stmt = select(ReviewSession).where(ReviewSession.id == session_uuid).options(
        selectinload(ReviewSession.attempts),
        selectinload(ReviewSession.diagnosis),
        selectinload(ReviewSession.metrics)
    )
    result = await db.execute(stmt)
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "id": str(session.id),
        "status": session.status,
        "repository": session.repo_url,
        "branch": session.branch,
        "diagnosis": {
            "failure_classification": session.diagnosis.failure_classification,
            "severity_rating": session.diagnosis.severity_rating,
            "ast_context": session.diagnosis.ast_context,
            "diff_trees": session.diagnosis.diff_trees,
        } if session.diagnosis else None,
        "metrics": {
            "overall_score": session.metrics.overall_score,
            "compilation_confidence": session.metrics.compilation_confidence,
            "test_pass_confidence": session.metrics.test_pass_confidence,
            "semantic_preservation_score": session.metrics.semantic_preservation_score,
        } if session.metrics else None,
        "attempts": [
            {
                "id": str(attempt.id),
                "attempt_number": attempt.attempt_number,
                "status": attempt.status,
                "patch_diff": attempt.patch_diff,
                "test_logs": attempt.test_logs,
                "created_at": attempt.created_at
            }
            for attempt in sorted(session.attempts, key=lambda a: a.attempt_number)
        ],
        "created_at": session.created_at,
        "updated_at": session.updated_at
    }

@router.post("/{session_id}/action")
async def handle_action(session_id: str, payload: ActionRequest, db: AsyncSession = Depends(get_db)):
    """Handle Human-in-the-Loop actions (approve_pr, request_retry, dismiss)."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    stmt = select(ReviewSession).where(ReviewSession.id == session_uuid)
    result = await db.execute(stmt)
    session = result.scalars().first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if payload.action not in ["approve_pr", "request_retry", "dismiss"]:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    if payload.action == "approve_pr":
        session.status = "approved"
    elif payload.action == "request_retry":
        session.status = "retrying"
    elif payload.action == "dismiss":
        session.status = "dismissed"
        
    await db.commit()
    return {"status": "success", "action": payload.action, "session_id": session_id}
