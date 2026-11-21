import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

# Ensure fixforge directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from api.main import app


@pytest.mark.asyncio
async def test_chatbot_problem_query():
    """Verify that chatbot correctly answers what problem was in the previous code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/chat",
            json={
                "message": "What was the problem in the previous code?",
                "demo_context": {
                    "repository": "pallets/flask",
                    "bug": "AssertionError: Request context was not preserved",
                    "taxonomy": "Runtime / Concurrency Issue",
                    "severity": "Critical",
                    "confidence": 0.94,
                    "patch_diff": "- ctx.close()\n+ await ctx.close()",
                    "attempts": [
                        {
                            "attempt_number": 0,
                            "status": "failed",
                            "reason": "Failed to await async context closure",
                            "test_logs": "FAILED tests/test_async.py::test_async_ctx_teardown\nAssertionError",
                        }
                    ]
                }
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert len(data["reply"]) > 20
        # The reply should explain the problem or error
        assert any(k in data["reply"].lower() for k in ["problem", "error", "assertion", "flask", "concurrency", "runtime"])


@pytest.mark.asyncio
async def test_chatbot_solution_query():
    """Verify that chatbot explains how FixForge solved the problem."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/chat",
            json={
                "message": "How did FixForge solve the problem and fix the code?",
                "demo_context": {
                    "repository": "pallets/flask",
                    "bug": "AssertionError: Request context was not preserved",
                    "taxonomy": "Runtime / Concurrency Issue",
                    "severity": "Critical",
                    "confidence": 0.94,
                    "patch_diff": "- ctx.close()\n+ await ctx.close()",
                }
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert len(data["reply"]) > 20
        # The reply should discuss the solution/patch/fix
        assert any(k in data["reply"].lower() for k in ["solution", "solve", "patch", "diff", "fix", "ctx.close"])


@pytest.mark.asyncio
async def test_chatbot_before_after_comparison():
    """Verify that chatbot generates a Before vs After breakdown."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/chat",
            json={
                "message": "Show me a Before vs After comparison of the fix",
                "demo_context": {
                    "repository": "expressjs/router",
                    "bug": "TypeError: Cannot read properties of undefined (reading 'handle')",
                    "taxonomy": "Logic Error",
                    "severity": "High",
                    "confidence": 0.88,
                    "patch_diff": "- layer.handle(req, res, next);\n+ if (layer && layer.handle) layer.handle(req, res, next);",
                }
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        # Response should contain Before and After sections or comparison
        reply_lower = data["reply"].lower()
        assert "before" in reply_lower or "problem" in reply_lower or "after" in reply_lower or "fix" in reply_lower
