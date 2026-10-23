# FixForge AI — Live Evaluation & Empirical Results

**Environment Specifications**:
- **Date**: 2026-10-23
- **Branch**: `live-mode-hardening`
- **LLM Model**: `qwen/qwen3.8-27b` (via Groq Cloud API, structured JSON outputs via Instructor)
- **Docker Daemon**: Docker Desktop 29.5.3 (build d1c06ef), WSL2 Linux kernel 6.18.33.1
- **Sandbox Container**: `fixforge-sandbox:latest` (Ubuntu 22.04, non-root user `nonroot`, `network_mode=none`, read-only source mount)
- **Host OS**: Windows 11 (PowerShell)
- **Python**: 3.12.10 (`.venv`)
- **Database**: SQLite with `aiosqlite` (`sqlite+aiosqlite:///./fixforge.db`)

---

## 1. Curated Benchmark Evaluation Results (100 Runs Total)

> [!CAUTION]
> **Honest Accounting Rule**: `Resolution = docker_status == 'passed' AND test_passed == True AND all agent_sources == 'llm'`.
> Any run where the sandbox is unverified, an agent fell back to heuristics, or git patch was rejected is counted in its own distinct column and **never** credited as resolved.

### Performance Summary Table

| Configuration | Total Runs | Resolved | Unverified | Fallback | Patch Failed | Failed | Resolution Rate (%) | MTTF (s) | Classification Acc (%) |
|---|---|---|---|---|---|---|---|---|---|
| **Single-Shot LLM Baseline** | 20 | 0 | 0 | 1 | 0 | 19 | **0.0%** | 11.45s | 0.0% |
| **Static-Analysis-Only Baseline** | 20 | 0 | 0 | 0 | 0 | 0 | **0.0%** | 0.16s | 100.0% |
| **Full FixForge Pipeline** | 60 | 0 | 60 | 0 | 0 | 0 | **0.0%** | 440.85s | 30.0% |

- **Multi-Agent vs Baseline Delta**: `+0.0%` verified resolution improvement.
- **Agent Execution Purity**: **60/60** FixForge pipeline runs executed with `llm,llm,llm` live agent sources (Planner, Diagnoser, Fixer, and 2x Consistency Samplers). Zero fallback heuristics invoked across the multi-agent runs.
- **Sandbox Outcome**: All 60 FixForge benchmark runs resulted in `unverified` status due to Windows named pipe read timeouts (`NpipeHTTPConnectionPool: Read timed out`) during the containerized test suite execution. Under strict honest accounting, zero unverified runs are claimed as resolved.

---

## 2. End-to-End Live Smoke Test (10 Runs)

**Target**: `https://github.com/pallets/flask/issues/5012`  
**Execution Command**: `.venv\Scripts\python scripts/e2e_smoke.py --runs 10`

| Run | Mode (LLM / Docker) | Status | Confidence | Attempts | Diagnosis Row | Metrics Row | Time (s) |
|---|---|---|---|---|---|---|---|
| **1** | `live/live` | failed | 0.4572 | 3 | YES | YES | 91.93s |
| **2** | `live/live` | failed | 0.4572 | 3 | YES | YES | 111.56s |
| **3** | `live/live` | failed | 0.4553 | 3 | YES | YES | 111.54s |
| **4** | `live/live` | failed | 0.4572 | 3 | YES | YES | 113.86s |
| **5** | `live/live` | failed | 0.4572 | 3 | YES | YES | 122.80s |
| **6** | `live/live` | failed | 0.4572 | 3 | YES | YES | 111.91s |
| **7** | `live/live` | failed | 0.4572 | 3 | YES | YES | 113.38s |
| **8** | `live/live` | failed | 0.1847 | 3 | YES | YES | 113.95s |
| **9** | `live/live` | failed | 0.4081 | 3 | YES | YES | 111.86s |
| **10** | `live/live` | failed | 0.4566 | 3 | YES | YES | 110.73s |

**Smoke Test Findings**:
- **Live Infrastructure**: 100% of runs connected to live Groq API and live Docker daemon (`Mode=live/live`).
- **Retry Loop**: In all 10 runs, the candidate patch was rejected by `git apply --check` inside the Docker sandbox (`error: corrupt patch at line 10/11`), properly driving all 3 retries with execution failure feedback.
- **Confidence Scoring**: Dynamic multi-signal calculation executed on every run (Test Results 0%, Static Analysis 100%, Context Similarity 38.2%, Consistency 67–100%).
- **Database Persistence**: 10/10 sessions created complete relational records (`ReviewSession`, `AgentAttempt`, `DiagnosisRecord`, `ConfidenceMetric`) with `status=failed`.

---

## 3. Unit & Gate Test Suite

**Execution Command**: `.venv\Scripts\pytest fixforge/tests -q`  
**Result**: `32 passed, 52 warnings in 213.10s (0:03:33)`

- `test_confidence_stage3.py`: 5/5 passed (signal weighting, calibration bands, score sensitivity)
- `test_e2e_repair.py`: 1/1 passed (end-to-end workflow)
- `test_evaluation.py`: 9/9 passed (FRR metric, delta metric, strict resolution enforcement unit tests)
- `test_persistence_stage4.py`: 2/2 passed (foreign keys, cascading deletes, readable error persistence)
- `test_pipeline.py`: 2/2 passed (AST extraction, retry loop)
- `test_retriever_stage1.py`: 3/3 passed (real file scanning, AST parsing, checkout failure handling)
- `test_sandbox_stage2.py`: 6/6 passed (good patch passed, malformed patch failed, Docker down unverified, retry history, DB session unverified)
- `test_webhooks_stage5.py`: 4/4 passed (HMAC SHA-256 validation, ping events, SSE streaming, e2e webhook repair)

---

## 4. Frontend Status

**Execution Commands**: `npm run build` && `npm run test`  
- **Vite Build**: Compiled in 237ms (TypeScript strict mode, zero errors).
- **Vitest Suite**: 7/7 tests passed in 1.25s (`useFixForgeStream.test.ts`, `DiffViewer.test.tsx`).
- **Visual Design**: Stitch design tokens active (`#15121b` background, `#e7e0ed` on-surface, `#d0bcff` primary, `#5de6ff` secondary, WCAG AA compliant contrast > 11:1).
