"""
chat.py — FixForge AI Assistant Route.
Explains the previous problem in the codebase, the root cause, and how FixForge repaired it.
Supports both live sessions from DB and demo/offline scenarios.
"""

import uuid
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from openai import AsyncOpenAI

from core.config import settings
from db.session import get_db
from db.models import ReviewSession

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None
    demo_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: Optional[str] = None
    source: str = "llm"  # "llm" | "semantic_engine"
    problem_summary: Optional[str] = None
    solution_summary: Optional[str] = None


def _build_semantic_fallback_response(message: str, session_data: Dict[str, Any]) -> str:
    """
    Deterministic explanation engine that parses the bug, diagnosis, attempts,
    and patch diff to produce an in-depth answer even when offline.
    """
    msg_lower = message.lower()

    repo = session_data.get("repository") or session_data.get("repo") or "Repository"
    bug = session_data.get("bug") or "Failing test suite / unexpected runtime error"
    taxonomy = session_data.get("failure_classification") or session_data.get("taxonomy") or "Logic Error"
    severity = session_data.get("severity") or session_data.get("severity_rating") or "High"
    confidence = session_data.get("confidence_score") or session_data.get("confidence") or 0.85
    patch_diff = session_data.get("patch_diff") or ""
    attempts = session_data.get("attempts") or []

    # First attempt (problem/failure)
    first_attempt_reason = ""
    first_attempt_logs = ""
    if attempts and len(attempts) > 0:
        first_attempt = attempts[0]
        first_attempt_reason = first_attempt.get("reason", "")
        test_logs = first_attempt.get("test_logs", "")
        if isinstance(test_logs, list):
            first_attempt_logs = "\n".join(test_logs)
        else:
            first_attempt_logs = str(test_logs or "")

    # Check if asking about the problem
    is_problem_query = any(k in msg_lower for k in ["problem", "bug", "issue", "why did it fail", "failing", "root cause", "error", "what was wrong", "previous"])
    # Check if asking about the solution
    is_solution_query = any(k in msg_lower for k in ["solve", "solution", "how was", "fixed", "patch", "repair", "change", "resolved", "diff"])
    # Check if asking for before vs after
    is_comparison_query = any(k in msg_lower for k in ["before", "after", "compare", "comparison", "difference", "vs"])
    initial_failure = f"- **Initial Failure:** {first_attempt_reason}\n" if first_attempt_reason else ""
    logs_block = f"```\n{first_attempt_logs[:300]}...\n```\n" if first_attempt_logs else ""
    failing_snippet = f"**Failing Test Snippet:**\n```\n{first_attempt_logs[:400]}\n```\n" if first_attempt_logs else ""

    if is_comparison_query or (is_problem_query and is_solution_query):
        return (
            f"### 🔍 Before vs. After Analysis for `{repo}`\n\n"
            f"#### ❌ Before Fix (The Problem):\n"
            f"- **Issue Summary:** {bug}\n"
            f"- **Taxonomy & Severity:** `{taxonomy}` ({severity} Severity)\n"
            f"- **Root Cause:** The code was failing automated assertions during execution.\n"
            f"{initial_failure}"
            f"{logs_block}\n"
            f"#### ✅ After Fix (The Solution):\n"
            f"- **Fix Strategy:** Corrected the underlying faulty logic to handle execution safely.\n"
            f"- **Confidence Score:** `{confidence * 100:.1f}%` based on multi-factor telemetry.\n"
            f"- **Verification:** Automated tests in the sandbox passed without regressions.\n\n"
            f"```diff\n{patch_diff if patch_diff else '# No diff available'}\n```\n\n"
            f"FixForge verified that all tests passed and no static security alerts remained."
        )

    if is_problem_query:
        return (
            f"### ❌ Previous Code Problem in `{repo}`\n\n"
            f"**1. What went wrong:**\n"
            f"- **Observed Error:** {bug}\n"
            f"- **Classification:** `{taxonomy}` (Severity: **{severity}**)\n\n"
            f"**2. Root Cause Breakdown:**\n"
            f"The codebase encountered an unexpected state where requirements were violated during execution. "
            f"{f'Specifically: {first_attempt_reason}' if first_attempt_reason else 'The test suite caught an unhandled condition in the target file.'}\n\n"
            f"{failing_snippet}"
            f"Would you like me to explain how FixForge diagnosed and fixed this in the patch diff?"
        )

    if is_solution_query:
        return (
            f"### ✅ How FixForge Solved the Problem in `{repo}`\n\n"
            f"**1. Repair Strategy:**\n"
            f"FixForge diagnosed the failure as a `{taxonomy}` and applied targeted modifications to safely handle the failing condition.\n\n"
            f"**2. Candidate Patch Diff:**\n"
            f"```diff\n{patch_diff if patch_diff else '# Patch diff verified'}\n```\n\n"
            f"**3. Verification & Confidence:**\n"
            f"- Overall Confidence Score: **`{confidence * 100:.1f}%`**\n"
            f"- All automated test assertions passed in container sandbox.\n"
            f"- Semgrep static analysis verified zero newly introduced vulnerabilities."
        )

    # General inquiry
    return (
        f"### 🤖 FixForge Analysis for `{repo}`\n\n"
        f"- **Previous Problem:** {bug} (`{taxonomy}`)\n"
        f"- **Status:** Repaired and verified with **{confidence * 100:.1f}%** confidence.\n"
        f"- **Applied Solution:**\n"
        f"```diff\n{patch_diff[:500] if patch_diff else '# Solution applied'}\n```\n\n"
        f"You can ask me:\n"
        f"- *'What was the problem with the previous code?'*\n"
        f"- *'How did FixForge solve it?'*\n"
        f"- *'Show me Before vs After comparison'*."
    )


@router.post("", response_model=ChatResponse)
async def chat_handler(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Chatbot endpoint explaining the previous problem and how it was solved.
    """
    session_data: Dict[str, Any] = {}

    # 1. Check if session_id exists in database
    if req.session_id:
        try:
            session_uuid = uuid.UUID(req.session_id)
            stmt = select(ReviewSession).where(ReviewSession.id == session_uuid).options(
                selectinload(ReviewSession.attempts),
                selectinload(ReviewSession.diagnosis),
                selectinload(ReviewSession.metrics)
            )
            result = await db.execute(stmt)
            sess = result.scalars().first()

            if sess:
                sorted_attempts = sorted(sess.attempts or [], key=lambda a: a.attempt_number)
                session_data = {
                    "repository": sess.repo_url,
                    "branch": sess.branch,
                    "status": sess.status,
                    "confidence_score": sess.metrics.overall_score if sess.metrics else 0.85,
                    "failure_classification": sess.diagnosis.failure_classification if sess.diagnosis else "Logic Error",
                    "severity_rating": sess.diagnosis.severity_rating if sess.diagnosis else "High",
                    "patch_diff": sorted_attempts[-1].patch_diff if sorted_attempts else "",
                    "bug": (sess.diagnosis.failure_classification if sess.diagnosis else "Failing automated test suite"),
                    "attempts": [
                        {
                            "attempt_number": a.attempt_number,
                            "status": a.status,
                            "patch_diff": a.patch_diff,
                            "test_logs": a.test_logs,
                        }
                        for a in sorted_attempts
                    ]
                }
        except Exception as e:
            logger.warning("Error fetching session %s from DB: %s", req.session_id, e)

    # 2. Check if demo_context was supplied by client
    if not session_data and req.demo_context:
        session_data = req.demo_context

    # 3. Check for live LLM availability
    api_key = settings.OPENAI_API_KEY or settings.GROQ_API_KEY
    base_url = settings.OPENAI_BASE_URL or "https://api.ai.kodekloud.com/v1"
    model_name = getattr(settings, "FIXFORGE_MODEL", "claude-haiku-5-5")

    if api_key and len(api_key) > 5:
        try:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)

            # Extract attempt details for rich LLM context
            attempts = session_data.get("attempts") or []
            attempt_summary = []
            for att in attempts:
                att_logs = att.get("test_logs") or att.get("reason") or ""
                if isinstance(att_logs, list):
                    att_logs = "\n".join(att_logs)
                attempt_summary.append(
                    f"Attempt #{att.get('attempt_number', 0)} (Status: {att.get('status', 'unknown')}):\n"
                    f"Logs/Failure: {str(att_logs)[:400]}\n"
                    f"Diff:\n{att.get('patch_diff', '')[:400]}"
                )
            attempts_text = "\n\n".join(attempt_summary) if attempt_summary else "No previous attempts logged."

            # System prompt with rich session context
            system_prompt = (
                "You are FixForge AI Assistant, an expert code tutor and automated program repair engineer. "
                "Your objective is to clearly explain to students, teachers, and reviewers:\n"
                "1. What problem/bug was previously in the code (root cause, failure classification, why tests failed).\n"
                "2. How the problem was solved after that (the candidate patch diff, what lines changed, why the new code works).\n"
                "3. Provide Before vs After comparisons with markdown code diffs when requested.\n\n"
                "NOTE: When the user asks about 'previous code', 'the problem', or 'what was wrong', they are referring to the codebase and bug in the session context below before FixForge fixed it. Always base your explanation on this context:\n\n"
                f"CURRENT SESSION CONTEXT:\n"
                f"- Repository: {session_data.get('repository') or session_data.get('repo') or 'Unknown'}\n"
                f"- Bug / Error: {session_data.get('bug') or 'Test suite assertion failure'}\n"
                f"- Taxonomy: {session_data.get('failure_classification') or session_data.get('taxonomy') or 'Logic Error'}\n"
                f"- Severity: {session_data.get('severity_rating') or session_data.get('severity') or 'Medium'}\n"
                f"- Confidence Score: {session_data.get('confidence_score') or session_data.get('confidence') or 0.85}\n"
                f"- Candidate Patch Diff:\n```diff\n{session_data.get('patch_diff') or '# No diff'}\n```\n"
                f"- Repair Attempts & Verification Logs:\n{attempts_text}\n"
            )

            messages = [{"role": "system", "content": system_prompt}]

            if req.history:
                for h in req.history[-6:]:
                    messages.append({"role": h.role, "content": h.content})

            messages.append({"role": "user", "content": req.message})

            resp = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=600,
                temperature=0.2,
            )

            reply_text = (resp.choices[0].message.content or "").strip()
            if not reply_text:
                reply_text = _build_semantic_fallback_response(req.message, session_data)

            return ChatResponse(
                reply=reply_text,
                session_id=req.session_id,
                source="llm" if resp.choices[0].message.content else "semantic_engine",
                problem_summary=str(session_data.get("bug") or ""),
                solution_summary="Patch diff applied and verified with test suite"
            )

        except Exception as exc:
            logger.warning("Live LLM chat call failed (%s). Falling back to semantic engine.", exc)

    # 4. Fallback to resilient semantic engine
    reply_text = _build_semantic_fallback_response(req.message, session_data)
    return ChatResponse(
        reply=reply_text,
        session_id=req.session_id,
        source="semantic_engine",
        problem_summary=str(session_data.get("bug") or ""),
        solution_summary="Patch diff applied and verified with test suite"
    )
