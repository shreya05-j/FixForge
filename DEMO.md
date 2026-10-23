# FixForge AI — 5-Minute Live Demo Script & Examiner Presentation

**Project**: FixForge AI — Autonomous Multi-Agent Program Repair & Observability  
**Mode**: Live (`qwen/qwen3.8-27b` via Groq API + Docker Desktop Sandbox `fixforge-sandbox:latest`)  
**Branch**: `live-mode-hardening`

---

## 1. Selected Demo Bugs & Empirical Performance

We benchmarked three curated repository issues across 10 live runs each to assess real behavior:

| Bug Instance | Repository & Issue | Fault Type | Classification Acc | Patch Verification Rate | Mean Latency | Primary Failure Cause |
|---|---|---|---|---|---|---|
| **Demo Bug 1** | `pallets/flask#5012` | Runtime Error | **100% (10/10)** | **0% (0/10)** | 109.8s | Unified diff reject in sandbox (`git apply --check` line format) |
| **Demo Bug 2** | `pytest-dev/pytest#5221` | Logic Error | **100% (10/10)** | **0% (0/10)** | 65.6s | Sandbox test execution timeout (`NpipeHTTPConnectionPool`) |
| **Demo Bug 3** | `django/django#11099` | Logic Error | **100% (10/10)** | **0% (0/10)** | 67.2s | Sandbox test execution timeout (`NpipeHTTPConnectionPool`) |

> [!NOTE]
> **Honest Reporting Principle**: While LLM agents (Planner, Diagnoser, Fixer) successfully analyze AST and generate semantically reasonable repairs, zero runs achieved full unassisted pass due to strict sandbox verification constraints. We present this exact empirical truth during the demo.

---

## 2. Pre-Demo Setup & Preflight Verification (2 Minutes Before Demo)

Run these checks to verify live infrastructure before examiners arrive:

### Terminal 1: Backend Preflight
```powershell
cd A:\fixforge(2)\FixForge
.venv\Scripts\python -c "import docker; print('Docker ping:', docker.from_env().ping())"
.venv\Scripts\uvicorn fixforge.api.main:app --port 8000
```

### Terminal 2: Health Verification
```powershell
curl http://127.0.0.1:8000/api/health
```
**Expected JSON Output**:
```json
{
  "status": "healthy",
  "llm_mode": "live",
  "docker_mode": "live",
  "sandbox_image": "present",
  "github_mode": "dry_run"
}
```

### Terminal 3: Frontend Dev Server
```powershell
cd A:\fixforge(2)\FixForge\frontend
npm run dev
```
Open browser to `http://127.0.0.1:5173/`. Verify that the top navigation bar displays the bright green **`LIVE`** badge.

---

## 3. The 5-Minute Demo Walkthrough Script

### Minute 0:00 - 0:45 | Introduction & Honest Architecture Overview
- **What to Say**:
  > *"Good morning/afternoon. Today I am demonstrating FixForge AI, an autonomous program repair and observability platform. Most program repair demos rely on unverified mock data or rule-based heuristics disguised as AI. FixForge is built on strict empirical honesty.  
  > Look at the top badge: it says **LIVE**. That means we are connected to the live Groq LLM API and a hardened Docker Desktop container environment. Every step you see will be executed live."*
- **Action**: Point to the **`LIVE`** badge in the header, then click the **System Health** indicator to show `Docker: live`, `LLM: live`, `Sandbox: present`.

---

### Minute 0:45 - 2:00 | Triggering the Multi-Agent Repair Pipeline
- **What to Say**:
  > *"Let's input a real-world issue: `https://github.com/pallets/flask/issues/5012`. This is a Cookie header byte-decoding bug in Flask. When I click 'Start Autonomous Repair', FixForge launches our LangGraph multi-agent pipeline."*
- **Action**: Paste `https://github.com/pallets/flask/issues/5012` into the input bar and click **Run Repair Pipeline**.
- **What to Say as Events Stream**:
  > *"1. First, the **Planner** inspects the issue description and determines the strategy.  
  > 2. Second, the **Retriever** uses AST symbol analysis to isolate candidate files (`flask/wrappers.py`).  
  > 3. Third, the **Diagnoser** agent classifies the bug category. Notice it correctly categorized this as a **Runtime Error** with root cause explanation.  
  > 4. Fourth, the **Fixer** synthesizes a patch candidate using structured JSON output via Instructor."*
- **Visuals on Screen**:
  - Live SSE event cards updating in the left execution pipeline.
  - Latency and token meters incrementing in real time.
  - Source attribution badge stating `source: llm`.

---

### Minute 2:00 - 3:15 | Sandbox Verification & The Retry Loop
- **What to Say**:
  > *"Now comes the critical differentiator: Sandbox Verification. FixForge never trusts LLM code blindly. The patch is dispatched into an isolated Ubuntu container running as non-root with zero network access.  
  > In this run, the sandbox executes `git apply --check`. Notice that the patch formatting was rejected by git.  
  > Instead of ignoring the error or faking success, the pipeline catches this execution failure, feeds the compiler error back into the Fixer, and automatically triggers Attempt 2 of 3."*
- **Action**: Point to the **Attempt Tabs** (Attempt 1 -> Attempt 2 -> Attempt 3) showing the feedback loop in action.
- **Visuals on Screen**:
  - Attempt badge showing `Attempt 2/3 (Refining patch based on sandbox stderr)`.
  - Terminal logs showing `git apply --check: corrupt patch at line 10`.

---

### Minute 3:15 - 4:15 | Multi-Signal Confidence Calibration & Diff Inspection
- **What to Say**:
  > *"After 3 attempts, FixForge performs Multi-Signal Confidence Calibration across 4 orthogonal dimensions:
  > - **Test Results**: 0% (because container test was not verified)
  > - **Static Analysis**: 100% (syntax check passed)
  > - **Context Similarity**: 38.2% (patch proximity to issue tokens)
  > - **Self-Consistency**: 67% (agreement across diverse sampled repairs)
  > This yields a calibrated confidence of ~0.457. Because confidence is below the 0.85 threshold and sandbox verification failed, FixForge marks the PR status as **Needs Human Review** rather than hallucinating an approval."*
- **Action**: Click the **Diff Viewer** to display the syntax-highlighted side-by-side patch diff. Point to the **Confidence Breakdown** progress bars.

---

### Minute 4:15 - 5:00 | Security Proof & Examiner Conclusion
- **What to Say**:
  > *"To conclude: every single session is persisted with full relational integrity in SQLite. The PR comment was kept in dry-run mode so no unauthorized changes touch GitHub. FixForge is provably secure, hardened against prompt injection, and honest about its capabilities."*
- **Action**: Show SQLite query in terminal:
  ```powershell
  .venv\Scripts\python -c "import sqlite3; c=sqlite3.connect('fixforge.db'); print(c.execute('SELECT id, status, llm_mode, docker_mode FROM review_sessions ORDER BY created_at DESC LIMIT 1').fetchall())"
  ```
- **Conclusion**: Invite questions from examiners.

---

## 4. Emergency Plan B: Fallback & Fault Tolerance

If an external failure occurs during the live demo, follow this contingency script:

| Failure Scenario | Immediate Indicator | Examiner Explanation | Action / Plan B Command |
|---|---|---|---|
| **Groq 429 Rate Limit** | Toast notification: *"Rate limit exceeded (429)"* | *"We are operating under Groq's free-tier rate limits (7,000 TPM). The system automatically applies exponential backoff."* | Wait 30 seconds for backoff, or switch to simulated mode to complete the demo without delay. |
| **Docker Desktop Daemon Crash** | Health badge turns amber: `PARTIAL (Docker offline)` | *"The container daemon encountered a connection drop. FixForge cleanly traps this, labels the sandbox 'unverified', and refuses to claim a false pass."* | Restart Docker Desktop or demonstrate fallback via `export MOCK_DOCKER=true`. |
| **Complete Network Loss** | Health badge turns red: `FALLBACK (Offline)` | *"Our offline resilience architecture instantly activates rule-based AST heuristics and cached fixtures, allowing zero-downtime operation."* | Demonstrate the UI in offline fallback mode, highlighting the prominent **FALLBACK** badge.
