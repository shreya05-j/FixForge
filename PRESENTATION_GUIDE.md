# FixForge AI: Master Defense & Presentation Guide

---

## 1. Executive Summary & Project Purpose

### What is FixForge AI?
**FixForge AI** is an industrial-grade **Autonomous Program Repair (APR) Multi-Agent System**. It automatically ingests GitHub bug reports or pull request issues, localizes the responsible source code, diagnoses the root cause, synthesizes a minimal and precise code patch, rigorously verifies the patch inside an isolated Docker container sandbox, and computes a multi-signal confidence score before presenting an automated pull request.

### The Problem It Solves
1. **Developer Burnout & Maintenance Overhead**: Developers spend upwards of 50% of their engineering time triaging, diagnosing, and repairing regression bugs.
2. **Flaws in Naive Single-Prompt LLM Repair**: Directly asking an LLM (like ChatGPT) to "fix this bug" suffers from:
   - **Hallucinations**: Modifying unrelated code or documentation.
   - **Context Mismatches**: Generating diffs that fail `git apply` due to slight whitespace or line numbering errors.
   - **Lack of Empirical Verification**: Proposing fixes that sound plausible in text but break the project's test suite or fail compilation.
3. **The FixForge Solution**: A closed-loop, verifiable 7-stage multi-agent pipeline governed by **LangGraph**, where no patch is ever accepted unless it passes real unit tests inside an isolated Docker sandbox.

---

## 2. Technical Stack & Architecture

### Backend Core
- **Language**: Python 3.12 (Virtualenv)
- **API Framework**: FastAPI with Uvicorn (Asynchronous REST API + Server-Sent Events / SSE streaming)
- **Agent Orchestrator**: LangGraph (Stateful, cyclical multi-agent graph with retry and human-in-the-loop loops)
- **Structured LLM Output**: Instructor (`instructor.from_openai(..., mode=Mode.JSON)`) enforcing Pydantic models for 100% schema compliance.
- **LLM Engine**: KodeKloud OpenAI-compatible endpoint hosting `claude-haiku-5-5` (low latency, high reasoning fidelity).
- **ORM & Database**: SQLAlchemy 2.0 (Async) + `aiosqlite` with SQLite (`fixforge.db`).
- **Vector Database**: ChromaDB (stores past issue embeddings using `sentence-transformers/all-MiniLM-L6-v2` for historical retrieval-augmented generation).

### Sandbox & Execution Engine
- **Runtime**: Docker SDK for Python interacting with Docker Desktop (WSL2 engine).
- **Sandbox Image**: `fixforge-sandbox:latest` (Ubuntu 22.04 base, Python 3.10, non-root user `nonroot`).
- **Security Isolation**:
  - `network_mode="none"` (zero egress/ingress during patch execution, preventing data leaks or malicious remote code execution).
  - Read-only source mounting with an ephemeral copy at `/app_scratch`.
  - Hard resource constraints: 2GB RAM limit, 2 CPU cores, 60s hard execution timeout.

### Frontend Studio
- **Framework**: React 19 + TypeScript built with Vite 8.
- **Styling**: TailwindCSS with custom design system tokens (Dark modern palette: `#15121b` background, `#d0bcff` primary accents, `#5de6ff` secondary highlights, glassmorphic surfaces).
- **State & Streaming**: Custom React hook (`useFixForgeStream.ts`) consuming real-time Server-Sent Events (SSE) from FastAPI.
- **Components**: DiffViewer (Split and Unified diff rendering), Live Terminal with auto-scroll, Telemetry charts, ChromaDB explorer.

---

## 3. The 7-Stage Multi-Agent Pipeline

The repair loop is executed via a deterministic LangGraph state machine:

```
[Start Session]
      │
      ▼
01. PLANNER  ──────►  02. RETRIEVER  ──────►  03. DIAGNOSER  ──────►  04. FIXER
                                                                           │
                                                                           ▼
                                                                     05. VERIFIER
                                                                           │
                                  ┌────────────────────────────────────────┴────────┐
                                  │                                                 │
                             [Tests Passed]                                   [Tests Failed / Code 42]
                                  │                                                 │
                                  ▼                                                 ▼
                        06. CONFIDENCE ENGINE                             (Retry Loop: Max 4 Attempts)
                                  │                                                 │
                                  ▼                                                 └─► Back to Fixer with Error Logs
                            07. REPORTER
                                  │
                                  ▼
                         [Pull Request Ready]
```

### Stage 01: Planner (Scope Definition & Target Localization)
- **Role**: Ingests the issue description, bug report, or GitHub PR title. Analyzes the symptom and formulates an investigation plan.
- **Key Protection**: Filters out all non-code files. Explicitly instructs the pipeline to only target executable source code (`.py`).

### Stage 02: Retriever (AST Context & Memory RAG)
- **Role**: 
  1. Inspects the repository checkout root.
  2. Extracts targeted Python files and parses Abstract Syntax Trees (AST) using Python's `ast` module to index class names, method signatures, and function bodies.
  3. Queries ChromaDB for the top-3 historically similar bug resolutions to provide few-shot exemplars to the model.

### Stage 03: Diagnoser (Root Cause Analysis - RCA)
- **Role**: Evaluates the symptom against the AST context and test failures.
- **Output**: 
  - Classifies the bug category (e.g., Logic Error, Off-by-one, Configuration, Runtime Error).
  - Outlines the exact failure mechanism.
  - Generates a step-by-step resolution strategy.

### Stage 04: Fixer (Minimal Patch Synthesis)
- **Role**: Synthesizes a unified diff (`.patch`).
- **Strict Guardrails**:
  - Prohibits touching documentation, markdown, or non-source files.
  - Focuses strictly on minimal line modifications (avoiding rewriting entire functions).
  - Incorporates previous attempt failure feedback if running in a retry iteration.

### Stage 05: Verifier (Isolated Docker Container Sandbox)
- **Role**: The ultimate gatekeeper. Applies the patch and runs the real project test suite.
- **Multi-Strategy Patch Engine**:
  - *Strategy 1*: Standard `git apply --reject`.
  - *Strategy 2*: GNU `patch -p1 --batch`.
  - *Strategy 3 (FixForge Innovation)*: **Selective Deleted-Lines Matching**. Isolates deleted lines (`-`), matches them in the source code using context scoring and line proximity tiebreaking, adapts indentation, and replaces them with added lines (`+`). Completely eliminates hunk rejection due to LLM context hallucinations.
  - *Strategy 4*: Context-anchored pure insertion.
- **Verification Gate**:
  - If tests pass: Transitions to Stage 06.
  - If tests fail: Captures full `pytest` stdout/stderr, feeds it back into `AgentState`, and increments `retry_count`.

### Stage 06: Confidence Engine (Multi-Signal Scoring)
Computes a mathematically weighted confidence score between 0.0 and 1.0 (0% - 100%):
- **Test Results (45%)**: 1.0 if all tests pass; 0.0 if failed.
- **Static Analysis (25%)**: AST parsing and syntax tree compilation verification.
- **Context Similarity (15%)**: Cosine similarity to verified historical fixes from ChromaDB.
- **LLM Consistency (15%)**: Entropy/agreement scoring across sampled reasoning traces.

### Stage 07: Reporter (Provenance & GitHub PR Formatting)
- **Role**: Synthesizes the final engineering report, documenting root cause, proposed changes, test pass verification, and metadata before opening the PR.

---

## 4. UI Walkthrough: Every Button, View & Interaction

When presenting the frontend (`http://localhost:5173`), here is what every component does:

### A. Navigation & Top Header
1. **FixForge AI Logo & Status Pill (`● LIVE`)**:
   - Shows system connectivity. Green `LIVE` confirms the backend, Claude Haiku LLM, and Docker daemon are fully operational.
2. **Session Selector Dropdown**:
   - Allows switching between past repair traces and active sessions in real time.
3. **Header Nav Tabs**:
   - **Dashboard**: The main operational mission control.
   - **Workstation**: An IDE-style interface for source files, AST symbol inspection, and terminal commands.
   - **Telemetry**: Real-time observability dashboard (latencies, token consumption, system health).
   - **ChromaDB**: Visualizer for vector memory and embedding cosine similarity.
4. **"Run FixForge" Button**:
   - Opens the **Trigger New Analysis** modal.

### B. "Run FixForge" Modal
- **Target Input Field**: Allows typing any GitHub repository URL or issue (e.g., `owner/repo#123`).
- **Preset Buttons**:
  - **`QuixBugs (BFS)`**: Loads `https://github.com/jkoppel/QuixBugs#breadth_first_search` (algorithm queue bug).
  - **`QuixBugs (bitcount)`**: Loads `https://github.com/jkoppel/QuixBugs#bitcount` (bitwise AND vs XOR bug).
  - **`pallets/flask#5012`**: Real-world Flask cookie decoding bug.
- **"Execute Run" Button**: Initiates the live repair session via `/api/sessions/start`.

### C. Dashboard View
1. **Execution Pipeline Stepper (01 to 07)**:
   - Visual nodes that pulse yellow while running and turn green with a checkmark upon completion. Displays real-time agent latency (e.g., `1.8s`).
2. **Tabbed Inspection Panes**:
   - **Patch Diff Tab**: Displays the syntax-highlighted diff (green for additions, red for deletions). Includes **Unified / Split** toggle, **Copy** button, and **.patch Download** button.
   - **RCA Diagnosis Tab**: Displays the Diagnoser's Failure Mechanism, Root Cause, Investigation Plan, and Scoped Source Files.
   - **Sandbox Logs Tab**: Live terminal emulator streaming raw `pytest` output directly from the Docker container. Includes **Auto-scroll** toggle and **Copy Logs** button.
   - **Iteration History Tab**: Allows viewing past attempts (Attempt #1, Attempt #2, etc.) to show how the agent adapted when a patch initially failed.
3. **Overall Confidence Dial**:
   - Renders the computed confidence percentage (e.g., `91.85%`) alongside breakdown bars.
4. **"Approve & Create Pull Request" Button**:
   - In live mode with a GitHub token, creates the remote PR. In dry-run mode, logs the complete Markdown PR payload to the console and marks the session as `approved`.

### D. Workstation View
- **File Explorer (Left)**: Lists scanned repository files.
- **AST Symbol Explorer**: Shows classes, methods, and functions parsed from Python AST.
- **Interactive Terminal**: Allows running test commands like `pytest`, `ast-scan`, and `git diff` against the active session.

---

## 5. Major Engineering Challenges & How We Solved Them

*This section is your secret weapon for the jury. It proves you solved real-world engineering hurdles.*

| Challenge | Root Cause | FixForge Solution |
| :--- | :--- | :--- |
| **1. LLM Context Hallucination** | LLMs hallucinate surrounding context lines (` ` lines), causing `git apply` to fail with "corrupt patch at line X". | Built **Strategy 3 (Selective Deleted-Lines Matching)** in `runner.py`: extracts `-` and `+` lines, finds target locations using fuzzy context scoring and line proximity tiebreaking, and directly replaces the code. |
| **2. Non-Source File Pollution** | Models often attempt to patch `README.md` or docs instead of fixing code when repos have complex layouts. | Implemented a **4-layer guardrail**: instant rejection in `runner.py` with exit code `42`, strict prompt rules and path filtering in `planner.py`, Python-only scanning in `retriever.py`, and diff discarding in `fixer.py`. |
| **3. Windows MAX_PATH Filename Limit** | Deeply nested repository paths (e.g. Vitest snapshot filenames > 260 chars) crashed `git clone` with exit code 128. | Enforced `-c core.longpaths=true` on all Git clone and checkout commands in `repo_checkout.py` and enabled it globally. |
| **4. Docker Named Pipe Timeouts on Windows** | Large repos or long test suites timed out Windows Docker named pipes (`NpipeHTTPConnectionPool`). | Implemented ephemeral `/app_scratch` container volumes, streaming execution logs, and configurable timeout limits. |
| **5. Strict Schema Enforcement** | Standard LLMs output conversational text or malformed JSON, crashing downstream agents. | Integrated **Instructor** with Pydantic schemas in `Mode.JSON` over `AsyncOpenAI`, guaranteeing deterministic data structures. |

---

## 6. Empirical Benchmark Results

We verified FixForge against standard benchmarks in full live mode (`claude-haiku-5-5` + Docker sandbox):

| Metric | QuixBugs (`breadth_first_search`) | QuixBugs (`bitcount`) |
| :--- | :--- | :--- |
| **Execution Time** | **24 seconds** | **21 seconds** |
| **Attempts Needed** | **1 (First-pass resolution)** | **1 (First-pass resolution)** |
| **Patch Accuracy** | Fixed `while True:` to `while queue:` | Fixed `n ^= n - 1` to `n &= n - 1` |
| **Sandbox Tests** | **5 / 5 Passed (100%)** | **9 / 9 Passed (100%)** |
| **Overall Confidence** | **91.85%** | **91.45%** |
| **Full Test Suite** | **35 / 35 Passed** | **35 / 35 Passed** |
| **Static Type Check** | **0 errors, 0 warnings** | **0 errors, 0 warnings** |

---

## 7. Jury Defense & Q&A Cheat Sheet

### Q1: "Why did you build a multi-agent system instead of just calling an LLM with a single prompt?"
> **Answer**: *"A single prompt lacks verification, self-correction, and grounding. If an LLM hallucinates a patch, a single prompt has no way to know it failed. FixForge separates concerns into specialized roles: the Planner localizes files, the Retriever parses AST syntax trees and memory, the Diagnoser isolates root cause, the Fixer writes minimal diffs, and the Verifier tests them in Docker. If the tests fail, the Verifier feeds the exact compiler error back to the Fixer in an automated retry loop. This closed-loop verification is what guarantees correctness."*

### Q2: "How do you guarantee security when running arbitrary code from GitHub?"
> **Answer**: *"Every verification happens inside an isolated Docker container (`fixforge-sandbox:latest`). We enforce `network_mode=none` so the container has zero internet access, preventing any data exfiltration or reverse shells. The repository source is mounted as read-only, tests execute under a non-root user (`nonroot`), and we enforce strict memory (2GB) and CPU limits with a 60-second kill switch."*

### Q3: "How is your confidence score calculated?"
> **Answer**: *"Rather than guessing, we use a 4-signal weighted mathematical model: 45% weight on Docker test pass results, 25% on AST compilation and syntax validation, 15% on semantic context similarity to ChromaDB historical fixes, and 15% on LLM reasoning consistency across multiple samples."*

### Q4: "What happens if the LLM generates a patch with wrong line numbers?"
> **Answer**: *"Standard tools like `git apply` reject the patch. To solve this, we engineered an intelligent multi-strategy patch engine in `runner.py`. If standard patch tools fail, Strategy 3 extracts the deleted lines, searches the AST target for the closest semantic match, adapts the indentation, and replaces the block. This allows FixForge to successfully apply valid fixes even when the LLM hallucinates surrounding context line numbers."*

### Q5: "What are the current limitations and future scope?"
> **Answer**: *"FixForge currently specializes in Python repositories using `pytest`. In the future, we plan to extend the sandbox container matrix to support multi-language environments (TypeScript/Node.js, Go, Rust), and integrate static analysis linters like Ruff and Pyright into the pre-verification loop."*

---
*FixForge AI — Autonomous Program Repair System*
