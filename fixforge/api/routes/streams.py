import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

# Try importing the graph build workflow, or create a mock generator
try:
    from fixforge.graph.workflow import build_workflow
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter()

async def mock_event_generator(session_id: str) -> AsyncGenerator[str, None]:
    """Generates mock SSE events for local testing without LangGraph."""
    events = [
        {"event": "node_start", "data": {"agent": "planner", "timestamp": "2026-08-25T12:00:00Z", "input_summary": "Planning fix..."}},
        {"event": "node_progress", "data": {"chunk": "Analyzing stack trace... "}},
        {"event": "node_progress", "data": {"chunk": "Found issue in logic... "}},
        {"event": "node_complete", "data": {"agent": "planner", "latency": 1.2, "status": "success", "output": {"plan": "Fix condition"}}},
        
        {"event": "node_start", "data": {"agent": "fixer", "timestamp": "2026-08-25T12:00:02Z", "input_summary": "Writing patch..."}},
        {"event": "node_progress", "data": {"chunk": "def new_func():\n"}},
        {"event": "node_progress", "data": {"chunk": "    return True\n"}},
        {"event": "node_complete", "data": {"agent": "fixer", "latency": 2.5, "status": "success", "output": {"patch": "+    return True"}}},
        
        {"event": "node_start", "data": {"agent": "verifier", "timestamp": "2026-08-25T12:00:05Z", "input_summary": "Running sandbox tests"}},
        {"event": "node_progress", "data": {"log_line": "[pytest] collect 1 item"}},
        {"event": "node_progress", "data": {"log_line": "[pytest] FAILED test.py"}},
        {"event": "node_complete", "data": {"agent": "verifier", "latency": 3.0, "status": "failed", "output": {"passed": False}}},
        
        {"event": "retry_loop", "data": {"message": "Attempt 2 of 3 triggered due to Pytest failure", "iteration": 2}},
        
        {"event": "pipeline_complete", "data": {
            "diff": "--- a/file.py\n+++ b/file.py\n@@ -1,2 +1,2 @@\n- return False\n+ return True",
            "confidence_score": 0.88,
            "github_comment": "FixForge AI identified a logic error and generated a patch with 88% confidence."
        }}
    ]
    
    for event in events:
        await asyncio.sleep(1.0)
        yield {
            "event": event["event"],
            "data": json.dumps(event["data"])
        }

async def langgraph_event_generator(session_id: str) -> AsyncGenerator[str, None]:
    """Hooks into LangGraph's astream_events to yield SSE events."""
    if not GRAPH_AVAILABLE:
        async for evt in mock_event_generator(session_id):
            yield evt
        return

    # Instantiate the graph
    graph = build_workflow()
    initial_state = {"session_id": session_id}
    
    try:
        # We hook into `astream_events` to yield granular node transitions
        async for event in graph.astream_events(initial_state, version="v1"):
            kind = event["event"]
            
            if kind == "on_chain_start":
                node_name = event.get("name", "unknown")
                if node_name != "LangGraph":
                    yield {
                        "event": "node_start",
                        "data": json.dumps({
                            "agent": node_name,
                            "timestamp": event.get("timestamp", ""),
                            "input_summary": f"Starting {node_name}"
                        })
                    }
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"].content
                yield {
                    "event": "node_progress",
                    "data": json.dumps({"chunk": chunk})
                }
            elif kind == "on_tool_start":
                # Example: for docker sandbox running
                tool_name = event.get("name")
                if tool_name == "run_pytest":
                    yield {
                        "event": "node_progress",
                        "data": json.dumps({"log_line": f"Starting tool {tool_name}..."})
                    }
            elif kind == "on_chain_end":
                node_name = event.get("name", "unknown")
                if node_name != "LangGraph":
                    # Check for retries based on custom output keys (mock logic)
                    state = event.get("data", {}).get("output", {})
                    retry_count = state.get("retry_count", 0)
                    
                    yield {
                        "event": "node_complete",
                        "data": json.dumps({
                            "agent": node_name,
                            "latency": 0.0, # calculate latency if timestamps are tracked
                            "status": "success",
                            "output": {"summary": f"Completed {node_name}"}
                        })
                    }
                    
                    # Emit retry event if applicable
                    if node_name == "verifier" and not state.get("test_results", {}).get("passed", True):
                        yield {
                            "event": "retry_loop",
                            "data": json.dumps({
                                "message": f"Attempt {retry_count + 1} of 3 triggered due to Pytest failure",
                                "iteration": retry_count + 1
                            })
                        }

        # Assuming pipeline complete triggers after stream ends
        # In a real app we'd pull final state from the stream end
        yield {
            "event": "pipeline_complete",
            "data": json.dumps({
                "diff": "--- a/file.py\\n+++ b/file.py",
                "confidence_score": 0.95,
                "github_comment": "FixForge AI has completed execution."
            })
        }
    except Exception as e:
        logger.error(f"Error in graph streaming: {e}")
        yield {
            "event": "error",
            "data": json.dumps({"detail": str(e)})
        }

@router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request):
    """Server-Sent Events endpoint for real-time pipeline execution trace."""
    
    async def event_publisher():
        generator = langgraph_event_generator(session_id)
        try:
            async for event in generator:
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from session {session_id}")
                    break
                yield event
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")

    return EventSourceResponse(event_publisher())
