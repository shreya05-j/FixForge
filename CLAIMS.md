# FixForge AI — Technical Claims & Viva Guidance

This document defines the exact boundary of what can be proven with real evidence versus claims that must never be made.

---

## 1. Verified Claims You CAN Make (With Supporting Evidence)

| # | Technical Claim | Primary Evidence File / Command | Verification Details |
|---|---|---|---|
| **1** | **Multi-Agent LangGraph Architecture**: Implements 7 specialized agent nodes with conditional retry edges and state management. | `fixforge/graph/workflow.py`<br>`pytest fixforge/tests/test_pipeline.py` | StateGraph routes through Planner -> Retriever -> Diagnoser -> Fixer -> Verifier -> Confidence -> Reporter, looping up to 3 times on test failure. |
| **2** | **Isolated Docker Sandbox**: Enforces non-root execution (`uid=10001`), read-only repo mounts, disabled network (`network_mode='none'`), memory caps (`512MB`), and disposable containers. | `fixforge/sandbox/Dockerfile.sandbox`<br>`fixforge/sandbox/runner.py`<br>`python scripts/verify_stage1_sandbox.py` | Verified with live commands proving write denial to `/app_src`, ping failure to `8.8.8.8`, and non-root id inside container. |
| **3** | **Multi-Signal Confidence Scoring**: Dynamic heuristic combining 4 distinct signals with explicit weight renormalization when signals are unavailable. | `fixforge/agents/confidence.py`<br>`pytest fixforge/tests/test_confidence_stage3.py` | Test execution (45%), Pyflakes static analysis (25%), ChromaDB AST cosine similarity (15%), and LLM consistency sampling (15%). |
| **4** | **Honest Accounting Rules**: Evaluator strictly enforces that resolution requires both a passing test in Docker AND live LLM generation across all agents. | `fixforge/evaluation/metrics.py`<br>`pytest fixforge/tests/test_evaluation.py` | 4 unit tests prove `unverified`, `fallback`, and `patch_failed` can never count as resolved. |
| **5** | **Structured Output Token Recovery**: Robust JSON parsing recovers valid unified diffs even when models truncate at max token ceilings. | `fixforge/core/llm_caller.py`<br>`scripts/run_live_evaluation.py` | Partial unified diffs extracted from `json_validate_failed` responses without degrading to rule-based fallback. |
| **6** | **Security & Human-in-the-Loop Safeguards**: Webhook HMAC-SHA256 signature verification, safe comment dry-run by default, and zero auto-merge/push capability. | `fixforge/api/routes/webhooks.py`<br>`fixforge/api/routes/sessions.py:663`<br>`git grep "git push" fixforge/` | Grep confirms 0 occurrences of `git push` or `git merge`; human approval only updates DB session status. |
| **7** | **Relational Persistence & Real-Time Telemetry**: Stores attempt-by-attempt telemetry, diagnosis categories, and confidence breakdowns with SSE streaming. | `fixforge/db/models.py`<br>`fixforge/api/routes/streams.py`<br>`pytest fixforge/tests/test_persistence_stage4.py` | SQLite DB tracks `ReviewSession`, `AgentAttempt`, `DiagnosisRecord`, and `ConfidenceMetric` with cascade deletes. |

---

## 2. Disallowed Claims You Must NOT Make

> [!CAUTION]
> Making any of the following claims during your viva or in a resume will lead to immediate failure under questioning.

1. ❌ **DO NOT CLAIM**: *"FixForge achieves 83.33% resolution on SWE-bench."*
   - **Why**: The 83.33% figure was an unverified heuristic run with Docker offline. The official SWE-bench Lite benchmark requires dedicated per-repo conda environments that take 15–30 minutes per instance to build.
   - **Correct Statement**: *"FixForge was evaluated on a 20-instance curated benchmark of real open-source bugs using a rigorous 3-pass test protocol."*

2. ❌ **DO NOT CLAIM**: *"The confidence score guarantees that a patch is correct."*
   - **Why**: The score aggregates four empirical indicators. A patch can be syntactically valid and pass unit tests while introducing subtle regressions.
   - **Correct Statement**: *"The confidence score estimates signal agreement across 4 dimensions to triage patches for human reviewers, not to guarantee semantic correctness."*

3. ❌ **DO NOT CLAIM**: *"FixForge autonomously merges pull requests into production repositories."*
   - **Why**: FixForge has no push or merge permissions. The `approve_pr` action only updates the session status in the database to `'approved'`.
   - **Correct Statement**: *"FixForge assists human maintainers by generating verified patches and review summaries; actual merging requires explicit maintainer action."*

4. ❌ **DO NOT CLAIM**: *"The platform runs on enterprise PostgreSQL."*
   - **Why**: FixForge uses SQLite (`sqlite+aiosqlite:///./fixforge.db`) to enable zero-configuration execution on Windows development environments.
   - **Correct Statement**: *"The system utilizes an asynchronous SQLAlchemy abstraction running SQLite locally, which can be configured for PostgreSQL via DATABASE_URL."*
