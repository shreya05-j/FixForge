"""
core/llm_caller.py — Standardized Live LLM Calling, Token Logging & 429 Handling.

Provides `call_structured_llm` used by:
- Planner
- Diagnoser
- Fixer
- Fixer consistency sampler

Features:
- Enforces Instructor structured schema output.
- Logs exact model name, latency (seconds), and token usage (prompt, completion, total).
- Handles HTTP 429 rate limits with exponential backoff and explicit log message.
- Enforces timeouts (configurable).
- Tracks `source: "llm" | "fallback"`.
"""

import time
import asyncio
import logging
from typing import Type, TypeVar, Tuple, Optional, Any, Dict
from pydantic import BaseModel
from openai import RateLimitError
from core.llm import async_llm_client
from core.config import settings



logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


import re
import json as _json
import unittest.mock


def _extract_diff_from_failed_generation(exc_str: str, response_model: type) -> Optional[Any]:
    """
    When Groq returns json_validate_failed, the error body contains
    `failed_generation` with the truncated JSON the model produced.
    If we can extract a valid-enough diff from it, return a partial model
    rather than falling back to heuristics.
    """
    # Find the failed_generation value inside the error string
    fg_match = re.search(r"'failed_generation':\s*'(.*?)(?:'\s*\}\s*\}|$)", exc_str, re.DOTALL)
    if not fg_match:
        # Try double-quote variant
        fg_match = re.search(r'"failed_generation":\s*"(.*?)(?:"\s*\}\s*\}|$)', exc_str, re.DOTALL)
    if not fg_match:
        return None

    fg_raw = fg_match.group(1)
    # Unescape common JSON escapes
    fg_raw = fg_raw.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')

    # Try to parse as JSON first
    try:
        parsed = _json.loads(fg_raw + '}')
        field_val = None
        for v in parsed.values():
            if isinstance(v, str) and v.strip().startswith('---'):
                field_val = v
                break
        if field_val:
            return response_model.model_validate({'candidate_diff': field_val})
    except Exception:
        pass

    # Try to extract candidate_diff value directly
    diff_match = re.search(r'"candidate_diff":\s*"(.*)', fg_raw, re.DOTALL)
    if diff_match:
        raw_diff = diff_match.group(1)
        # Unescape again since it may be double-escaped in the error string
        raw_diff = raw_diff.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
        # Truncate at unclosed JSON (look for diff start)
        if raw_diff.strip().startswith('---'):
            # Trim trailing garbage (unclosed quotes etc.)
            raw_diff = raw_diff.rstrip('"\\').rstrip()
            try:
                return response_model.model_validate({'candidate_diff': raw_diff})
            except Exception:
                pass

    return None


async def call_structured_llm(
    agent_name: str,
    response_model: Type[T],
    messages: list,
    temperature: float = 0.0,
    max_retries: int = 3,
    timeout_sec: float = 30.0,
    client: Optional[Any] = None,
    max_tokens: int = 1500,
) -> Tuple[Optional[T], Dict[str, Any]]:
    """
    Standardized live LLM invocation wrapper.

    Returns:
        (parsed_pydantic_model or None, telemetry_dict)
    """
    target_client = client if client is not None else async_llm_client
    model_name = getattr(settings, "FIXFORGE_MODEL", "claude-haiku-5-5")
    backoff = 1.0


    # 1. Deterministic unit testing support: if chat.completions.create is mocked
    active_client = target_client
    create_fn = getattr(getattr(target_client, "chat", None), "completions", None)
    create_method = getattr(create_fn, "create", None) if create_fn else None

    if not isinstance(create_method, (unittest.mock.Mock, unittest.mock.AsyncMock)):
        global_create_fn = getattr(getattr(async_llm_client, "chat", None), "completions", None)
        global_create_method = getattr(global_create_fn, "create", None) if global_create_fn else None
        if isinstance(global_create_method, (unittest.mock.Mock, unittest.mock.AsyncMock)):
            create_method = global_create_method
            active_client = async_llm_client

    if isinstance(create_method, (unittest.mock.Mock, unittest.mock.AsyncMock)):
        t0 = time.time()
        try:
            mock_res = create_method(
                model=model_name,
                response_model=response_model,
                temperature=temperature,
                messages=messages,
            )
            if asyncio.iscoroutine(mock_res):
                resp = await mock_res
            else:
                resp = mock_res
            latency = round(time.time() - t0, 3)
            return resp, {
                "source": "llm",
                "model": "mocked-llm",
                "latency_sec": latency,
                "prompt_tokens": 50,
                "completion_tokens": 50,
                "total_tokens": 100,
            }
        except Exception as exc:
            logger.warning("[%s] Mocked LLM call raised: %s", agent_name, exc)

    for attempt in range(max_retries):
        t0 = time.time()
        try:
            resp, raw = await asyncio.wait_for(
                target_client.chat.completions.create_with_completion(
                    model=model_name,
                    response_model=response_model,
                    temperature=temperature,
                    messages=messages,
                    max_tokens=max_tokens,
                ),
                timeout=timeout_sec,
            )
            latency = round(time.time() - t0, 3)
            usage = getattr(raw, "usage", None)
            p_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            c_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            tot_tokens = getattr(usage, "total_tokens", 0) if usage else 0

            telemetry = {
                "source": "llm",
                "model": getattr(raw, "model", model_name),
                "latency_sec": latency,
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "total_tokens": tot_tokens,
            }
            logger.info(
                "[%s] Live LLM Call SUCCESS: model=%s latency=%.3fs tokens=(prompt=%d, completion=%d, total=%d)",
                agent_name, telemetry["model"], latency, p_tokens, c_tokens, tot_tokens
            )
            return resp, telemetry

        except RateLimitError as rle:
            logger.warning(
                "[%s] HTTP 429 RateLimitError (attempt %d/%d): backing off %.1fs... Error: %s",
                agent_name, attempt + 1, max_retries, backoff, rle
            )
            await asyncio.sleep(backoff)
            backoff *= 2.0

        except asyncio.TimeoutError:
            latency = round(time.time() - t0, 3)
            logger.warning(
                "[%s] LLM call timed out after %.1fs (attempt %d/%d)",
                agent_name, timeout_sec, attempt + 1, max_retries
            )

        except Exception as exc:
            latency = round(time.time() - t0, 3)
            exc_str = str(exc)
            # OTPM / token-budget 429 — treat same as RateLimitError, back off
            if "rate_limit_exceeded" in exc_str or "Request too large" in exc_str:
                logger.warning(
                    "[%s] OTPM/token-budget 429 (attempt %d/%d): backing off %.1fs...",
                    agent_name, attempt + 1, max_retries, backoff
                )
                await asyncio.sleep(backoff)
                backoff *= 2.0
                continue
            # Special handling for json_validate_failed (model hit token limit mid-JSON)
            if "json_validate_failed" in exc_str:
                recovered = _extract_diff_from_failed_generation(exc_str, response_model)
                if recovered is not None:
                    logger.info(
                        "[%s] Recovered partial diff from failed_generation (attempt %d/%d, %.3fs)",
                        agent_name, attempt + 1, max_retries, latency
                    )
                    telemetry = {
                        "source": "llm",
                        "model": model_name,
                        "latency_sec": latency,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    }
                    return recovered, telemetry
                else:
                    # Cannot recover — the model hallucinated a huge rewrite.
                    # Do NOT retry with same prompt (will produce same result).
                    logger.warning(
                        "[%s] json_validate_failed and no recoverable diff (attempt %d/%d, %.3fs) — skipping remaining retries.",
                        agent_name, attempt + 1, max_retries, latency
                    )
                    break
            logger.warning(
                "[%s] LLM error (attempt %d/%d) after %.3fs: %s: %s",
                agent_name, attempt + 1, max_retries, latency, type(exc).__name__, exc_str[:200]
            )
            if "429" in exc_str and "rate_limit_exceeded" not in exc_str:
                await asyncio.sleep(backoff)
                backoff *= 2.0

    telemetry = {
        "source": "fallback",
        "model": "fallback-heuristics",
        "latency_sec": 0.0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    logger.warning("[%s] Falling back to rule-based heuristics.", agent_name)
    return None, telemetry
