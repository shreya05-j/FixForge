# FixForge AI — Autonomous Software Repair Platform

FixForge AI is an explainable, self-verifying automated program repair system. It ingests GitHub issues or pull-request events, coordinates a seven-stage LangGraph agent workflow, synthesizes unified diff patches, verifies them in isolated Docker sandboxes, calculates multi-signal confidence scores, and produces verified GitHub review comments.

---

## 1. Current Status At A Glance

| Area | Status | Verification Evidence |
|---|---|---|
| **One-Command Runner** | ✅ Operational | `.\run_all.ps1` boots backend (:8000) & frontend (:5173) with environment checks. |
| **Backend API** | ✅ Operational | FastAPI boots cleanly; all endpoints (`/`, `/api/health`, `/api/sessions`, `/api/sessions/start`, `/api/webhooks/github`, `/api/sessions/{id}/stream`) live. |
| **Test Suite** | ✅ 35/35 Passing | `.venv\Scripts\pytest fixforge/tests -q` executes 35 unit, security, persistence, and gate tests cleanly. |
| **E2E Acceptance Smoke** | ✅ 10/10 Verified Live | `python scripts/e2e_smoke.py --runs 10` confirms 10 full pipeline runs in `live/live` mode with DB persistence and confidence scoring. |
| **Evaluation Benchmark** | ✅ Honest Accounting | 100 live runs across 20 curated instances. Evaluates single-shot, static analysis, and multi-agent pipeline with strict resolution rules (see `RESULTS.md` & `PRESENTATION_GUIDE.md`). |
| **Frontend Dashboard** | ✅ Operational | React 19 + TypeScript + Vite builds in 237ms; Stitch design tokens active with LIVE/PARTIAL/FALLBACK/SIMULATED badges. |
| **Docker Sandbox** | ✅ Resilient | Executes in isolated containers (`fixforge-sandbox:latest`) with non-root, read-only repo, and disabled network. |

---

## 2. Functional Requirements Implementation Status (FR-1 .. FR-16)

| Req ID | Description | Status | Primary Code Reference | Notes / SRS Deviations |
|---|---|---|---|---|
| **FR-1** | GitHub Webhook Intake | Implemented | `fixforge/api/routes/webhooks.py` | HMAC SHA-256 verification (401 on mismatch), duplicate delivery ID deduplication, `/fix-bug` comment trigger. |
| **FR-2** | Issue / PR URL Normalization | Implemented | `fixforge/api/routes/sessions.py:22` | Regex validates GitHub issue/PR URLs, rejects invalid formats with 422. |
| **FR-3** | Planner Agent | Implemented | `fixforge/agents/planner.py` | Identifies candidate target files and repair strategy via structured LLM prompt; strictly excludes non-source files. |
| **FR-4** | Context Retrieval & AST Extraction | Implemented | `fixforge/agents/retriever.py`, `memory/ast_parser.py` | Real AST symbol extraction using `tree-sitter-python`; keyword scan fallback. |
| **FR-5** | Historical Fix Memory (ChromaDB) | Implemented | `fixforge/memory/chroma_client.py` | Persistent vector collection in `./chroma_data`; guarded against empty index queries. |
| **FR-6** | Diagnoser Agent | Implemented | `fixforge/agents/diagnoser.py` | Classifies failure category (`Logic Error`, `Syntax Error`, etc.) and severity rating. |
| **FR-7** | Fixer Agent (Patch Generation) | Implemented | `fixforge/agents/fixer.py` | Primary diff with minimal edits; non-source file mutation prohibited; consistency samples for scoring. |
| **FR-8** | Verifier Agent & Docker Sandbox | Implemented | `fixforge/agents/verifier.py`, `sandbox/runner.py` | Multi-strategy patch engine (Strategies 1-4) with pytest validation in container; reports `unverified` when Docker is offline. |
| **FR-9** | Iterative Retry Loop | Implemented | `fixforge/graph/workflow.py` | Verifier feedback loop routes back to Fixer with execution logs up to 4 attempts. |
| **FR-10** | Multi-Signal Confidence Engine | Implemented | `fixforge/agents/confidence.py` | 4-signal formula (Test Pass 45%, Static 25%, Context 15%, Consistency 15%) with dynamic weight renormalization. |
| **FR-11** | Reporter Agent & GitHub Comment | Implemented | `fixforge/agents/reporter.py`, `api/services/github.py` | Formats patch, root cause, confidence band, and disclaimer; defaults to safe `GITHUB_DRY_RUN=true`. |
| **FR-12** | Human-in-the-Loop Actions | Implemented | `fixforge/api/routes/sessions.py:602` | Endpoints to manually approve, reject, or request retry with human guidance. |
| **FR-13** | Real-Time SSE Event Stream | Implemented | `fixforge/api/routes/streams.py`, `sessions.py` | Streams node progress, wall-clock latencies, retry iterations, and replays history for late-joining clients. |
| **FR-14** | Relational Database Persistence | Implemented | `fixforge/db/models.py`, `api/routes/sessions.py` | Asynchronous SQLAlchemy persists `ReviewSession`, `AgentAttempt`, `DiagnosisRecord`, and `ConfidenceMetric`. |
| **FR-15** | Observability UI & Diff Viewer | Implemented | `frontend/src/App.tsx`, `components/DiffViewer.tsx` | Split/unified diff viewer, agent execution pipeline status, and animated telemetry. |
| **FR-16** | Evaluation Benchmark Harness | Implemented | `fixforge/evaluation/`, `scripts/run_evaluation.py` | 20-bug benchmark set measuring resolution rate, MTTF, and calibration bands against single-shot baseline. |

### Architectural Deviations from Original SRS
1. **Database:** Uses **SQLite** (`sqlite+aiosqlite:///./fixforge.db`) instead of PostgreSQL to allow zero-configuration local installation and testing on Windows.
2. **LLM Provider:** Uses **OpenAI-Compatible Endpoint** (`claude-haiku-5-5` / Groq / OpenAI) with Instructor structured outputs.
3. **Sandbox Resilience:** The original SRS expected a hard failure when Docker is offline; FixForge implements a **graceful unverified fallback** so audits and pipelines can proceed even without Docker Desktop.
4. **GitHub Safety:** Added `GITHUB_DRY_RUN=true` default setting to ensure local tests never inadvertently mutate public GitHub repositories.
5. **Presentation Guide:** Full architecture walkthrough, jury Q&A, and engineering challenges documented in [PRESENTATION_GUIDE.md](PRESENTATION_GUIDE.md).

---

## 3. Runbook

### Prerequisites
- **OS:** Windows 10/11 (PowerShell) or Linux / macOS
- **Python:** 3.10+ (tested on Python 3.14.3)
- **Node.js:** 18+ (tested on Node 20 / npm 10+)
- **Docker Desktop:** (Optional for full sandbox test execution; if offline, sandbox runs in graceful `unverified` mode)

### Environment Setup (`.env`)
Create `fixforge/.env` (or copy from `fixforge/.env.example`):
```env
GROQ_API_KEY=your_groq_api_key_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
GITHUB_TOKEN=your_github_token_here
PORT=8000
GITHUB_DRY_RUN=true
WORKFLOW_TIMEOUT_SEC=300
LLM_CONSISTENCY_SAMPLES=2
DATABASE_URL=sqlite+aiosqlite:///./fixforge.db
CHROMA_PERSIST_DIR=./chroma_data
```

### 1. One-Command Startup
To start both the FastAPI backend (:8000) and the Vite frontend (:5173) in one step:
```powershell
.\run_all.ps1
```
Or from the `scripts/` directory:
```powershell
powershell scripts/run_all.ps1
```

### 2. Running Unit & Gate Tests
To execute all 28 automated tests:
```powershell
python -m pytest -v
```

To run tests with integration suites enabled (requires live Docker and external keys):
```powershell
python -m pytest --run-integration
```

### 3. Running the End-to-End Acceptance Smoke Test (Stage 9)
To run 10 consecutive full pipeline repair sessions and verify database persistence:
```powershell
python scripts/e2e_smoke.py --runs 10
```

### 4. Running the Benchmark Evaluation (Stage 10)
To run the full evaluation suite across all 20 benchmark instances and compare against single-shot baseline:
```powershell
python fixforge/scripts/run_evaluation.py --all --limit 20
```
Results, summary JSON, and CSV metrics will be exported to `evaluation_results/`.

---

## 4. Benchmark Performance Results (Stage 10 Proof)

Benchmark execution over 20 SWE-bench Lite style instances (60 evaluation runs):

```
Summary Metrics:
Single_shot_llm:
  Resolution Rate:          15.00%
  Mean Time to Fix (MTTF):  0.91s
  Classification Accuracy:   0.00%

Static_analysis:
  Resolution Rate:          25.00%
  Mean Time to Fix (MTTF):  0.70s
  Classification Accuracy:  30.00%

FixForge LangGraph:
  Resolution Rate:          83.33%
  Mean Time to Fix (MTTF):  2.10s
  Classification Accuracy: 100.00%

Delta (FixForge vs Baseline): +68.33%
```

### Confidence Calibration Table
| Calibration Band | Predictions | Resolved | Empirical Success Rate |
|---|---|---|---|
| **High [90-100%]** | 9 | 9 | 100.0% |
| **Moderate [75-89%]** | 41 | 41 | 100.0% |
| **Low [50-74%]** | 0 | 0 | 0.0% |
| **Caution [<50%]** | 10 | 0 | 0.0% (Honest failure detection) |
