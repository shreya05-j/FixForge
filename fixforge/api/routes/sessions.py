# pyright: reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportArgumentType=false, reportTypedDictNotRequiredAccess=false, reportIndexIssue=false, reportOperatorIssue=false
import uuid
import os
import re
import time
import asyncio
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, field_validator
from db.session import get_db, AsyncSessionLocal
from db.models import ReviewSession, AgentAttempt, DiagnosisRecord, ConfidenceMetric
from graph.workflow import build_workflow
from core.state import AgentState
from api.routes.streams import stream_manager
from repo_checkout import checkout_repo
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)(?:/(?P<type>issues|pulls?)/(?P<number>\d+))?(?:\.git)?(?:[/?#].*)?$"
)
GITHUB_SHORT_PATTERN = re.compile(
    r"^(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)(?:#(?P<number>\d+))?$"
)


def parse_github_target(raw_url: str) -> Optional[dict]:
    trimmed = raw_url.strip()

    # Extract URL fragment e.g. #breadth_first_search
    fragment = ""
    if "#" in trimmed:
        trimmed, fragment = trimmed.split("#", 1)
        fragment = fragment.strip()

    target_file = None
    target_hint = fragment if fragment else None

    # Check for /blob/<branch>/<filepath> or /tree/<branch>/<filepath>
    blob_match = re.search(r"/(?:blob|tree)/[^/]+/(.+)$", trimmed)
    if blob_match:
        target_file = blob_match.group(1).split("?")[0]
        trimmed = re.sub(r"/(?:blob|tree)/.*$", "", trimmed)
        if not target_hint:
            target_hint = os.path.splitext(os.path.basename(target_file))[0]

    # Check for query parameters e.g. ?target=... or ?file=...
    if "?" in trimmed:
        query_part = trimmed.split("?", 1)[1]
        m_q = re.search(r"(?:target|file|hint)=([^&]+)", query_part)
        if m_q and not target_hint:
            target_hint = m_q.group(1)
        trimmed = trimmed.split("?", 1)[0]

    m = GITHUB_URL_PATTERN.match(trimmed)
    if m:
        owner = m.group("owner")
        repo = m.group("repo").removesuffix(".git")
        itype = m.group("type")
        num = m.group("number")
        is_explicit_issue = bool(itype and num)
        if not itype or not num:
            itype = "issue"
            num = "1"
        else:
            itype = "pull" if "pull" in itype else "issue"
        return {
            "owner": owner,
            "repo": repo,
            "type": itype,
            "number": num,
            "is_explicit_issue": is_explicit_issue,
            "repo_url": f"https://github.com/{owner}/{repo}",
            "canonical_url": f"https://github.com/{owner}/{repo}/{itype}/{num}" if is_explicit_issue else f"https://github.com/{owner}/{repo}",
            "target_hint": target_hint,
            "target_file": target_file,
        }

    m_short = GITHUB_SHORT_PATTERN.match(trimmed)
    if m_short:
        owner = m_short.group("owner")
        repo = m_short.group("repo").removesuffix(".git")
        num = m_short.group("number") or "1"
        return {
            "owner": owner,
            "repo": repo,
            "type": "issue",
            "number": num,
            "is_explicit_issue": bool(m_short.group("number")),
            "repo_url": f"https://github.com/{owner}/{repo}",
            "canonical_url": f"https://github.com/{owner}/{repo}",
            "target_hint": target_hint,
            "target_file": target_file,
        }
    return None


async def fetch_github_issue(owner: str, repo: str, number: str) -> Optional[Dict[str, str]]:
    """Attempts to fetch real issue title and description from public GitHub REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    headers = {
        "User-Agent": "FixForge-AI-Agent",
        "Accept": "application/vnd.github.v3+json"
    }
    if getattr(settings, "GITHUB_TOKEN", None):
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "title": data.get("title") or f"Issue #{number}",
                    "body": data.get("body") or f"Automated repair initiated for #{number}"
                }
    except Exception as exc:
        logger.debug(f"Could not fetch GitHub issue #{number} for {owner}/{repo}: {exc}")
    return None


class StartSessionRequest(BaseModel):
    url: str = Field(..., description="Target GitHub issue, pull request, or repository URL")
    issue_title: Optional[str] = Field(None, description="Optional custom issue title or bug summary")
    issue_body: Optional[str] = Field(None, description="Optional custom issue description or failure logs")
    target_file: Optional[str] = Field(None, description="Optional target file path or bug name")


    @field_validator("url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        trimmed = v.strip()
        parsed = parse_github_target(trimmed)
        if not parsed:
            raise ValueError(
                "Invalid GitHub URL or repository slug. Please provide a valid GitHub issue/PR URL "
                "(e.g. https://github.com/pallets/flask/issues/5012) or repository URL (e.g. https://github.com/pallets/flask)."
            )
        return trimmed

class ActionRequest(BaseModel):
    action: str

async def run_repair_workflow(session_uuid: uuid.UUID, initial_state: AgentState):
    """Executes the LangGraph repair pipeline asynchronously and broadcasts live SSE events.
    
    Checkout lifecycle:
      - This function clones the target repository before invoking LangGraph.
      - repo_checkout_path in the state carries the absolute temp-dir path.
      - The tmpdir is cleaned up in the finally block regardless of outcome.
      - If checkout fails, the state carries repo_checkout_path=None so the
        Retriever can surface a clear error instead of returning stub data.
    """
    session_id_str = str(session_uuid)
    logger.info(f"Initiating background workflow for session {session_id_str}")

    stream_manager.init_session(session_id_str)

    stream_manager.publish_event(session_id_str, "node_start", {
        "agent": "planner",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_summary": f"Planning investigation for {initial_state['repo_name']} #{initial_state['issue_id']}"
    })
    stream_manager.publish_event(session_id_str, "node_progress", {
        "log_line": f"Starting autonomous repair pipeline for {initial_state['repo_name']}..."
    })

    # ------------------------------------------------------------------
    # Clone the repository before the workflow starts so the Retriever
    # gets real source code. The tmpdir is kept alive for the workflow
    # duration and cleaned up in the finally block.
    # ------------------------------------------------------------------
    repo_url = initial_state.get("repo_url", "")
    checkout_tmpdir = None
    if repo_url:
        stream_manager.publish_event(session_id_str, "node_progress", {
            "log_line": f"Cloning repository {repo_url}..."
        })
        checkout_result = checkout_repo(
            repo_url,
            ref=initial_state.get("branch", "HEAD"),
            timeout_sec=settings.GIT_CLONE_TIMEOUT_SEC,
        )
        if checkout_result["status"] == "ok":
            initial_state["repo_checkout_path"] = checkout_result["path"]
            checkout_tmpdir = checkout_result["tmpdir"]
            stream_manager.publish_event(session_id_str, "node_progress", {
                "log_line": f"Repository cloned successfully to temp workspace."
            })
            logger.info(f"Session {session_id_str}: checkout at {checkout_result['path']}")
        else:
            initial_state["repo_checkout_path"] = None
            err_msg = checkout_result["error"]
            stream_manager.publish_event(session_id_str, "node_progress", {
                "log_line": f"[WARNING] Repository checkout failed: {err_msg}. Retriever will have no source context."
            })
            logger.warning(f"Session {session_id_str}: checkout failed: {err_msg}")
    else:
        initial_state["repo_checkout_path"] = None
        stream_manager.publish_event(session_id_str, "node_progress", {
            "log_line": "[WARNING] No repo_url in state. Running without repository checkout."
        })

    merged_state = dict(initial_state)

    try:
        workflow = build_workflow()
        node_order = ["planner", "retriever", "diagnoser", "fixer", "verifier", "confidence_engine", "reporter"]
        step_start_time = time.time()

        async def _run_stream():
            nonlocal step_start_time
            async for output in workflow.astream(initial_state):
                for node_name, node_output in output.items():
                    if isinstance(node_output, dict):
                        merged_state.update(node_output)

                    logger.info(f"Session {session_id_str} completed step: {node_name}")
                    elapsed = round(max(0.01, time.time() - step_start_time), 2)
                    step_start_time = time.time()

                    # Emit completion for current node
                    if node_name == "planner":
                        stream_manager.publish_event(session_id_str, "node_progress", {
                            "log_line": f"Plan formulated: {merged_state.get('plan', 'Investigate fault and apply patch.')[:120]}"
                        })
                        stream_manager.publish_event(session_id_str, "node_complete", {
                            "agent": "planner",
                            "latency": elapsed,
                            "status": "completed",
                            "output": {"plan": merged_state.get('plan', '')}
                        })
                        stream_manager.publish_event(session_id_str, "node_start", {
                            "agent": "retriever",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "input_summary": "Searching AST symbols and ChromaDB memory..."
                        })

                    elif node_name == "retriever":
                        stream_manager.publish_event(session_id_str, "node_progress", {
                            "log_line": "Retrieved AST context & historical fixes from memory."
                        })
                        stream_manager.publish_event(session_id_str, "node_complete", {
                            "agent": "retriever",
                            "latency": elapsed,
                            "status": "completed",
                            "output": {"ast_retrieved": True}
                        })
                        stream_manager.publish_event(session_id_str, "node_start", {
                            "agent": "diagnoser",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "input_summary": "Classifying failure category and severity..."
                        })

                    elif node_name == "diagnoser":
                        category = merged_state.get('failure_category', 'Logic Error')
                        severity = merged_state.get('severity', 'Medium')
                        stream_manager.publish_event(session_id_str, "node_progress", {
                            "log_line": f"Diagnosis: {category} (Severity: {severity})"
                        })
                        stream_manager.publish_event(session_id_str, "node_complete", {
                            "agent": "diagnoser",
                            "latency": elapsed,
                            "status": "completed",
                            "output": {"category": category, "severity": severity}
                        })
                        stream_manager.publish_event(session_id_str, "node_start", {
                            "agent": "fixer",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "input_summary": "Generating candidate unified diff patch..."
                        })
                        diff_preview = merged_state.get('candidate_diff', '')
                        if diff_preview:
                            stream_manager.publish_event(session_id_str, "node_progress", {
                                "chunk": diff_preview
                            })

                    elif node_name == "fixer":
                        diff = merged_state.get('candidate_diff', '')
                        stream_manager.publish_event(session_id_str, "node_complete", {
                            "agent": "fixer",
                            "latency": elapsed,
                            "status": "completed",
                            "output": {"diff_preview": diff[:100]}
                        })
                        stream_manager.publish_event(session_id_str, "node_start", {
                            "agent": "verifier",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "input_summary": "Executing tests in isolated sandbox container..."
                        })
                        stream_manager.publish_event(session_id_str, "node_progress", {
                            "log_line": "[pytest] Running sandbox test suite..."
                        })

                    elif node_name == "verifier":
                        v_results = merged_state.get('test_results', {})
                        v_status = v_results.get('status', 'failed')
                        passed = v_results.get('passed', False)
                        v_err = v_results.get('error') or v_results.get('stderr') or ''

                        if v_status == "unverified":
                            stream_manager.publish_event(session_id_str, "node_progress", {
                                "log_line": f"[WARNING] Docker daemon unreachable ({v_err}). Verification marked as UNVERIFIED."
                            })
                            stream_manager.publish_event(session_id_str, "node_complete", {
                                "agent": "verifier",
                                "latency": elapsed,
                                "status": "unverified",
                                "output": {"passed": False, "status": "unverified", "error": v_err}
                            })
                            stream_manager.publish_event(session_id_str, "node_start", {
                                "agent": "confidence_engine",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "input_summary": "Unverified execution. Calculating confidence score..."
                            })
                        elif v_status == "patch_failed":
                            stream_manager.publish_event(session_id_str, "node_progress", {
                                "log_line": f"[REJECTED] Candidate patch failed git apply --check: {v_err[:120]}"
                            })
                            stream_manager.publish_event(session_id_str, "node_complete", {
                                "agent": "verifier",
                                "latency": elapsed,
                                "status": "failed",
                                "output": {"passed": False, "status": "patch_failed", "error": v_err}
                            })
                            retry_cnt = merged_state.get('retry_count', 1)
                            stream_manager.publish_event(session_id_str, "retry_loop", {
                                "iteration": retry_cnt,
                                "message": f"Attempt {retry_cnt} of 3 triggered due to git apply rejection"
                            })
                            if retry_cnt < 3:
                                stream_manager.publish_event(session_id_str, "node_start", {
                                    "agent": "fixer",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "input_summary": f"Retry {retry_cnt}/3: Re-synthesizing fix with verification feedback..."
                                })
                            else:
                                stream_manager.publish_event(session_id_str, "node_start", {
                                    "agent": "confidence_engine",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "input_summary": "Max retries reached. Calculating confidence score..."
                                })
                        elif not passed:
                            stream_manager.publish_event(session_id_str, "node_progress", {
                                "log_line": "[FAILED] Sandbox test suite execution failed."
                            })
                            stream_manager.publish_event(session_id_str, "node_complete", {
                                "agent": "verifier",
                                "latency": elapsed,
                                "status": "failed",
                                "output": {"passed": False, "status": "failed"}
                            })
                            retry_cnt = merged_state.get('retry_count', 1)
                            stream_manager.publish_event(session_id_str, "retry_loop", {
                                "iteration": retry_cnt,
                                "message": f"Attempt {retry_cnt} of 3 triggered due to test verification failure"
                            })
                            if retry_cnt < 3:
                                stream_manager.publish_event(session_id_str, "node_start", {
                                    "agent": "fixer",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "input_summary": f"Retry {retry_cnt}/3: Re-synthesizing fix with verification failure feedback..."
                                })
                            else:
                                stream_manager.publish_event(session_id_str, "node_start", {
                                    "agent": "confidence_engine",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "input_summary": "Max retries reached. Calculating confidence score..."
                                })
                        else:
                            stream_manager.publish_event(session_id_str, "node_progress", {
                                "log_line": "[PASSED] Test verification succeeded in isolated sandbox."
                            })
                            stream_manager.publish_event(session_id_str, "node_complete", {
                                "agent": "verifier",
                                "latency": elapsed,
                                "status": "completed",
                                "output": {"passed": True, "status": "passed"}
                            })
                            stream_manager.publish_event(session_id_str, "node_start", {
                                "agent": "confidence_engine",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "input_summary": "Calculating confidence score breakdown..."
                            })

                    elif node_name == "confidence_engine":
                        conf_score = float(merged_state.get('confidence_score', 0.0))
                        conf_breakdown = merged_state.get('confidence_breakdown', {})
                        band = conf_breakdown.get('calibration_band', '<50')
                        stream_manager.publish_event(session_id_str, "node_progress", {
                            "log_line": f"Confidence: {int(conf_score * 100)}% (SRS Band: {band})"
                        })
                        stream_manager.publish_event(session_id_str, "node_complete", {
                            "agent": "confidence_engine",
                            "latency": elapsed,
                            "status": "completed",
                            "output": {
                                "score": conf_score,
                                "calibration_band": band,
                                "breakdown": conf_breakdown
                            }
                        })
                        stream_manager.publish_event(session_id_str, "node_start", {
                            "agent": "reporter",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "input_summary": "Generating final GitHub review comment..."
                        })

                    elif node_name == "reporter":
                        stream_manager.publish_event(session_id_str, "node_complete", {
                            "agent": "reporter",
                            "latency": elapsed,
                            "status": "completed",
                            "output": {"comment_ready": True}
                        })

        timeout_sec = float(getattr(settings, "WORKFLOW_TIMEOUT_SEC", 300))
        await asyncio.wait_for(_run_stream(), timeout=timeout_sec)
# Pipeline complete event
        final_diff = merged_state.get("candidate_diff") or ""
        final_score = float(merged_state.get("confidence_score") or 0.0)

        # Log what the Retriever handed to the Fixer (Stage 1 gate evidence).
        ast_ctx = merged_state.get("retrieved_ast_context", {})
        files_read = ast_ctx.get("source_files_read", [])
        n_fns = len(ast_ctx.get("functions", []))
        n_cls = len(ast_ctx.get("classes", []))
        fallback = ast_ctx.get("fallback_scan", False)
        logger.info(
            f"Session {session_id_str} Retriever summary: "
            f"files_read={files_read}, functions={n_fns}, classes={n_cls}, fallback={fallback}"
        )

        v_results = merged_state.get('test_results', {})
        v_status = v_results.get('status', 'failed')
        passed = v_results.get('passed', False)

        final_verdict = "unverified" if v_status == "unverified" else ("passed" if passed else "failed")
        session_db_status = "unverified" if v_status == "unverified" else ("completed" if passed else "failed")

        stream_manager.publish_event(session_id_str, "pipeline_complete", {
            "diff": final_diff,
            "confidence_score": final_score if passed else 0.0,
            "verdict": final_verdict,
            "status": session_db_status,
            "github_comment": (
                "FixForge AI: Verification could not be completed because Docker sandbox is unavailable."
                if v_status == "unverified"
                else (
                    f"FixForge AI successfully verified this patch with {int(final_score * 100)}% confidence."
                    if passed
                    else "FixForge AI was unable to verify this patch within retry limits."
                )
            )
        })

        async with AsyncSessionLocal() as session_db:
            stmt = select(ReviewSession).where(ReviewSession.id == session_uuid).options(
                selectinload(ReviewSession.attempts),
                selectinload(ReviewSession.diagnosis),
                selectinload(ReviewSession.metrics)
            )
            result = await session_db.execute(stmt)
            sess = result.scalars().first()
            if sess:
                sess.status = session_db_status

                # Clean up any existing child records on re-run
                if sess.diagnosis:
                    await session_db.delete(sess.diagnosis)
                if sess.metrics:
                    await session_db.delete(sess.metrics)
                for old_att in list(sess.attempts):
                    await session_db.delete(old_att)

                # 0. Check LLM telemetry across agents to set session llm_mode honestly
                diag_telemetry = merged_state.get("diagnoser_telemetry") or {}
                fixer_telemetry = merged_state.get("fixer_telemetry") or {}
                planner_telemetry = merged_state.get("planner_telemetry") or {}

                sources = [
                    diag_telemetry.get("source", "fallback"),
                    fixer_telemetry.get("source", "fallback"),
                    planner_telemetry.get("source", "fallback"),
                ]
                if all(s == "llm" for s in sources):
                    sess.llm_mode = "live"
                elif any(s == "llm" for s in sources):
                    sess.llm_mode = "partial"
                else:
                    sess.llm_mode = "fallback"

                # 1. Persist AgentAttempt rows
                attempts_data = list(merged_state.get('attempt_history') or [])
                if not attempts_data:
                    attempts_data = [{
                        "attempt_number": 1,
                        "status": v_status,
                        "source": fixer_telemetry.get("source", "llm"),
                        "model_name": fixer_telemetry.get("model", "claude-haiku-5-5"),
                        "tokens_used": fixer_telemetry.get("total_tokens", 0),
                        "latency_sec": fixer_telemetry.get("latency_sec", 0.0),
                        "patch_diff": final_diff,
                        "test_logs": (v_results.get("stdout") or v_results.get("stderr") or v_results.get("error") or "Verification completed.")
                    }]

                for att in attempts_data:
                    attempt_row = AgentAttempt(
                        id=uuid.uuid4(),
                        session_id=session_uuid,
                        attempt_number=att.get("attempt_number", 1),
                        status=att.get("status", "completed"),
                        source=att.get("source", fixer_telemetry.get("source", "llm")),
                        model_name=att.get("model_name", fixer_telemetry.get("model", "claude-haiku-5-5")),
                        tokens_used=att.get("tokens_used", fixer_telemetry.get("total_tokens", 0)),
                        latency_sec=att.get("latency_sec", fixer_telemetry.get("latency_sec", 0.0)),
                        patch_diff=att.get("patch_diff", final_diff),
                        test_logs=att.get("test_logs", "")
                    )
                    session_db.add(attempt_row)

                # 2. Persist DiagnosisRecord
                diagnosis_row = DiagnosisRecord(
                    id=uuid.uuid4(),
                    session_id=session_uuid,
                    failure_classification=merged_state.get("failure_category", "Logic Error"),
                    severity_rating=merged_state.get("severity", "Medium"),
                    source=diag_telemetry.get("source", "llm"),
                    model_name=diag_telemetry.get("model", "claude-haiku-5-5"),
                    tokens_used=diag_telemetry.get("total_tokens", 0),
                    latency_sec=diag_telemetry.get("latency_sec", 0.0),
                    ast_context=merged_state.get("retrieved_ast_context") or {},
                    diff_trees={
                        "root_cause": merged_state.get("diagnosis_summary", "Fault identified in target files"),
                        "plan": merged_state.get("plan", ""),
                        "target_files": merged_state.get("target_files", [])
                    }
                )
                session_db.add(diagnosis_row)

                # 3. Persist ConfidenceMetric
                conf_breakdown = merged_state.get("confidence_breakdown") or {}
                metrics_row = ConfidenceMetric(
                    id=uuid.uuid4(),
                    session_id=session_uuid,
                    overall_score=final_score if passed else float(conf_breakdown.get("overall_score", 0.0)),
                    compilation_confidence=float(conf_breakdown.get("compilation_confidence", 0.0)),
                    test_pass_confidence=float(conf_breakdown.get("test_pass_confidence", 0.0)),
                    semantic_preservation_score=float(conf_breakdown.get("semantic_preservation_score", 0.0))
                )
                session_db.add(metrics_row)

                await session_db.commit()
                logger.info(f"Session {session_id_str} and all child records persisted in DB (status={session_db_status}, llm_mode={sess.llm_mode})")

    except Exception as exc:
        logger.exception(f"Background workflow failed for session {session_id_str}: {exc}")
        stream_manager.publish_event(session_id_str, "error", {
            "detail": f"Workflow failed: {str(exc)}"
        })
        try:
            async with AsyncSessionLocal() as session_db:
                stmt = select(ReviewSession).where(ReviewSession.id == session_uuid).options(
                    selectinload(ReviewSession.attempts),
                    selectinload(ReviewSession.diagnosis),
                    selectinload(ReviewSession.metrics)
                )
                result = await session_db.execute(stmt)
                sess = result.scalars().first()
                if sess:
                    sess.status = "failed"

                    # Clean up existing child rows if any
                    if sess.diagnosis:
                        await session_db.delete(sess.diagnosis)
                    if sess.metrics:
                        await session_db.delete(sess.metrics)
                    for old_att in list(sess.attempts):
                        await session_db.delete(old_att)

                    # Persist readable failure records
                    fail_attempt = AgentAttempt(
                        id=uuid.uuid4(),
                        session_id=session_uuid,
                        attempt_number=1,
                        status="failed",
                        patch_diff="",
                        test_logs=f"Workflow failure: {str(exc)}"
                    )
                    session_db.add(fail_attempt)

                    fail_diagnosis = DiagnosisRecord(
                        id=uuid.uuid4(),
                        session_id=session_uuid,
                        failure_classification="Runtime Error",
                        severity_rating="High",
                        ast_context={},
                        diff_trees={
                            "error": str(exc),
                            "root_cause": f"Pipeline execution failed: {str(exc)}"
                        }
                    )
                    session_db.add(fail_diagnosis)

                    fail_metrics = ConfidenceMetric(
                        id=uuid.uuid4(),
                        session_id=session_uuid,
                        overall_score=0.0,
                        compilation_confidence=0.0,
                        test_pass_confidence=0.0,
                        semantic_preservation_score=0.0
                    )
                    session_db.add(fail_metrics)

                    await session_db.commit()
                    logger.info(f"Session {session_id_str} marked as failed with child error records in DB")
        except Exception as db_err:
            logger.error(f"Failed to record failure status for session {session_id_str}: {db_err}")
    finally:
        # Always clean up the cloned repository temp directory.
        if checkout_tmpdir is not None:
            try:
                checkout_tmpdir.cleanup()
                logger.info(f"Session {session_id_str}: checkout tmpdir cleaned up.")
            except Exception as cleanup_err:
                logger.warning(f"Session {session_id_str}: tmpdir cleanup failed: {cleanup_err}")


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
        "llm_mode": getattr(s, "llm_mode", "fallback"),
        "docker_mode": getattr(s, "docker_mode", "unavailable"),
        "failure_classification": s.diagnosis.failure_classification if s.diagnosis else "Unclassified",
        "confidence_score": s.metrics.overall_score if s.metrics else 0.0,
        "created_at": s.created_at
    } for s in sessions]

@router.post("/start")
async def start_session(
    payload: StartSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Initialize a new repair session for a GitHub issue/PR and launch the background workflow."""
    parsed = parse_github_target(payload.url)
    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="Invalid GitHub URL. Expected format: https://github.com/:owner/:repo/issues/:number or https://github.com/:owner/:repo"
        )
    
    owner = parsed["owner"]
    repo = parsed["repo"]
    issue_type = parsed["type"]
    issue_number = parsed["number"]
    repo_name = f"{owner}/{repo}"
    target_repo_url = parsed["repo_url"]

    session_id = uuid.uuid4()
    
    active_llm = "live" if ((settings.OPENAI_API_KEY and len(settings.OPENAI_API_KEY) > 5) or (settings.GROQ_API_KEY and len(settings.GROQ_API_KEY) > 10)) else "fallback"
    active_docker = "unavailable"

    try:
        import docker
        d_client = docker.from_env()
        d_client.ping()
        active_docker = "live"
    except Exception:
        active_docker = "unavailable"

    try:
        new_session = ReviewSession(
            id=session_id,
            repo_url=target_repo_url,
            branch="main",
            status="running",
            llm_mode=active_llm,
            docker_mode=active_docker
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
    except Exception as db_err:
        await db.rollback()
        logger.exception(f"Database write failed while creating session: {db_err}")
        raise HTTPException(status_code=500, detail="Database write failure while initializing session")

    target_hint = parsed.get("target_hint")
    target_file = payload.target_file or parsed.get("target_file")
    if not target_hint and target_file:
        target_hint = os.path.splitext(os.path.basename(target_file))[0]

    issue_title = payload.issue_title
    issue_body = payload.issue_body

    if not issue_title or not issue_body:
        if parsed.get("is_explicit_issue"):
            fetched = await fetch_github_issue(owner, repo, issue_number)
            if fetched:
                issue_title = issue_title or fetched.get("title")
                issue_body = issue_body or fetched.get("body")
        elif target_hint:
            issue_title = issue_title or f"Repair defect in {target_hint}"
            issue_body = issue_body or f"Analyze and repair defect in {target_hint}. Verify fix with test suite."

    issue_title = issue_title or f"{issue_type.capitalize()} #{issue_number}"
    issue_body = issue_body or f"Automated repair initiated for {payload.url}"

    initial_state: AgentState = {
        "repo_name": repo_name,
        "repo_url": target_repo_url,
        "branch": "main",
        "issue_id": issue_number,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "target_file": target_file,
        "target_hint": target_hint,
        "stack_trace": None,
        "target_files": [target_file] if target_file else [],
        "plan": "",
        "retrieved_ast_context": {},
        "historical_fix_context": [],
        "repo_checkout_path": None,
        "retriever_fallback": False,
        "diagnosis_summary": "",
        "candidate_diff": "",
        "test_results": {},
        "retry_count": 0,
        "confidence_score": 0.0,
        "confidence_breakdown": {},
        "status": "running"
    }

    background_tasks.add_task(run_repair_workflow, session_id, initial_state)

    return {
        "session_id": str(session_id),
        "status": "started",
        "url": payload.url
    }

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
        "llm_mode": getattr(session, "llm_mode", "fallback"),
        "docker_mode": getattr(session, "docker_mode", "unavailable"),
        "confidence_score": session.metrics.overall_score if session.metrics else 0.0,
        "patch_diff": sorted(session.attempts, key=lambda a: a.attempt_number)[-1].patch_diff if session.attempts else None,
        "diagnosis": {
            "failure_classification": session.diagnosis.failure_classification,
            "severity_rating": session.diagnosis.severity_rating,
            "source": getattr(session.diagnosis, "source", "llm"),
            "model_name": getattr(session.diagnosis, "model_name", None),
            "tokens_used": getattr(session.diagnosis, "tokens_used", 0),
            "latency_sec": getattr(session.diagnosis, "latency_sec", 0.0),
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
                "source": getattr(attempt, "source", "llm"),
                "model_name": getattr(attempt, "model_name", None),
                "tokens_used": getattr(attempt, "tokens_used", 0),
                "latency_sec": getattr(attempt, "latency_sec", 0.0),
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
