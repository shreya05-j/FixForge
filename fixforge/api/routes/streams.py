import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Set
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)
router = APIRouter()

class SessionStreamManager:
    """
    In-memory Pub/Sub event broadcaster for real-time LangGraph execution streaming.
    Maintains historical event replay for late-connecting clients and live async queues.
    """
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._history: Dict[str, List[dict]] = {}
        self._completed: Dict[str, dict] = {}

    def init_session(self, session_id: str):
        if session_id not in self._history:
            self._history[session_id] = []
        if session_id not in self._subscribers:
            self._subscribers[session_id] = set()

    def publish_event(self, session_id: str, event_type: str, data: dict):
        self.init_session(session_id)
        
        event_payload = {
            "event": event_type,
            "data": json.dumps(data)
        }
        
        self._history[session_id].append(event_payload)
        
        if event_type == "pipeline_complete":
            self._completed[session_id] = data

        subscribers = list(self._subscribers.get(session_id, []))
        for q in subscribers:
            try:
                q.put_nowait(event_payload)
            except Exception as e:
                logger.warning(f"Failed to queue event for subscriber in session {session_id}: {e}")

    def subscribe(self, session_id: str) -> tuple[List[dict], asyncio.Queue]:
        self.init_session(session_id)
        q = asyncio.Queue()
        self._subscribers[session_id].add(q)
        history = list(self._history.get(session_id, []))
        return history, q

    def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        if session_id in self._subscribers and queue in self._subscribers[session_id]:
            self._subscribers[session_id].remove(queue)

stream_manager = SessionStreamManager()

async def mock_event_generator(session_id: str) -> AsyncGenerator[dict, None]:
    """Generates mock SSE events for local testing if requested directly."""
    events = [
        {"event": "node_start", "data": {"agent": "planner", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Planning fix strategy..."}},
        {"event": "node_progress", "data": {"chunk": "Analyzing stack trace and repo context... "}},
        {"event": "node_complete", "data": {"agent": "planner", "latency": 0.8, "status": "completed", "output": {"plan": "Synthesize regression test and patch condition."}}},
        
        {"event": "node_start", "data": {"agent": "retriever", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Searching AST symbols and ChromaDB fixes..."}},
        {"event": "node_progress", "data": {"log_line": "Found 2 matching historical fix patterns."}},
        {"event": "node_complete", "data": {"agent": "retriever", "latency": 0.6, "status": "completed", "output": {"symbols": ["fix_condition", "validate_input"]}}},
        
        {"event": "node_start", "data": {"agent": "diagnoser", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Classifying bug category and severity..."}},
        {"event": "node_progress", "data": {"log_line": "Failure category identified: Logic Error (Severity: High)"}},
        {"event": "node_complete", "data": {"agent": "diagnoser", "latency": 0.9, "status": "completed", "output": {"category": "Logic Error", "severity": "High"}}},
        
        {"event": "node_start", "data": {"agent": "fixer", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Generating unified patch diff..."}},
        {"event": "node_progress", "data": {"chunk": "--- a/src/app.py\n+++ b/src/app.py\n@@ -10,3 +10,3 @@\n- return False\n+ return True\n"}},
        {"event": "node_complete", "data": {"agent": "fixer", "latency": 1.4, "status": "completed", "output": {"diff_generated": True}}},
        
        {"event": "node_start", "data": {"agent": "verifier", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Running sandbox tests..."}},
        {"event": "node_progress", "data": {"log_line": "[pytest] 1 passed in 0.04s"}},
        {"event": "node_complete", "data": {"agent": "verifier", "latency": 1.1, "status": "completed", "output": {"passed": True}}},
        
        {"event": "node_start", "data": {"agent": "confidence_engine", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Calculating confidence score..."}},
        {"event": "node_complete", "data": {"agent": "confidence_engine", "latency": 0.3, "status": "completed", "output": {"score": 0.92}}},
        
        {"event": "node_start", "data": {"agent": "reporter", "timestamp": datetime.utcnow().isoformat(), "input_summary": "Preparing GitHub review report..."}},
        {"event": "node_complete", "data": {"agent": "reporter", "latency": 0.4, "status": "completed", "output": {"comment_ready": True}}},
        
        {"event": "pipeline_complete", "data": {
            "diff": "--- a/src/app.py\n+++ b/src/app.py\n@@ -10,3 +10,3 @@\n- return False\n+ return True",
            "confidence_score": 0.92,
            "github_comment": "FixForge AI identified a logic error and generated a verified patch with 92% confidence."
        }}
    ]
    
    for evt in events:
        await asyncio.sleep(0.8)
        yield {
            "event": evt["event"],
            "data": json.dumps(evt["data"])
        }

@router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request):
    """Server-Sent Events endpoint for real-time pipeline execution trace."""
    
    async def event_publisher():
        # Handle demo keys
        if session_id.startswith("demo-"):
            async for evt in mock_event_generator(session_id):
                if await request.is_disconnected():
                    break
                yield evt
            return

        history, queue = stream_manager.subscribe(session_id)
        
        try:
            # 1. Replay history for catch-up
            for evt in history:
                if await request.is_disconnected():
                    return
                yield evt
                await asyncio.sleep(0.05) # Tiny yield pause to give UI smooth transitions
            
            # Check if already completed
            if session_id in stream_manager._completed and not history:
                yield {
                    "event": "pipeline_complete",
                    "data": json.dumps(stream_manager._completed[session_id])
                }
                return

            # 2. Stream live incoming events
            while True:
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from session {session_id}")
                    break
                
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield event
                    if event.get("event") in ["pipeline_complete", "error"]:
                        break
                except asyncio.TimeoutError:
                    # Send SSE keep-alive comment
                    yield {"event": "ping", "data": "{}"}
                    
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")
        finally:
            stream_manager.unsubscribe(session_id, queue)

    return EventSourceResponse(event_publisher())
