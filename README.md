# FixForge AI

FixForge is an explainable, self-verifying software-repair platform. It accepts a GitHub issue or pull-request event, sends the problem through a seven-stage agent workflow, proposes a unified diff, verifies the patch in a restricted Docker container, calculates a confidence score, and prepares a GitHub review comment.

This README describes the repository as it currently exists, including incomplete integrations and known blockers. It is an implementation guide, not a claim that every production feature is finished.

## Current Status At A Glance

| Area | Status | What is currently true |
| --- | --- | --- |
| Frontend dashboard | Working | React/Vite dashboard builds and opens at `http://localhost:5173/`. It includes offline demo scenarios and a live SSE client. |
| LangGraph workflow | Implemented | Planner -> Retriever -> Diagnoser -> Fixer -> Verifier -> Confidence -> Reporter, with verifier retry routing. |
| FastAPI health endpoint | Working | `GET /` returns the orchestrator health response. |
| GitHub webhook receiver | Implemented, needs integration testing | Signature validation and background workflow triggering are present. |
| SSE execution stream | Partially working | A mock stream is available; the live stream adapter exposes graph events but still uses placeholder completion data. |
| LLM calls | Implemented with fallback | Planner, Diagnoser, and Fixer use the configured client and fall back when calls fail. |
| AST retrieval | Partial | Tree-sitter parsing exists, but the current Retriever returns placeholder AST data instead of parsing the target repository. |
| ChromaDB memory | Implemented | Historical fixes can be queried and successful fixes can be stored. |
| Database persistence | Partial | SQLAlchemy models and startup table creation exist, but the main workflow does not yet persist all session, attempt, diagnosis, or metric records. |
| Docker verification | Implemented, needs environment | The runner applies a patch in a network-disabled container and runs pytest. Docker and the sandbox image are required. |
| New run API | Missing | The frontend calls `POST /api/sessions/start`, but the current sessions router does not define that route; the UI falls back to a demo scenario when it fails. |
| Backend tests | Not currently green | Test collection fails without a compatible `PYTHONPATH`/package layout. End-to-end tests also require mocked LLMs and a usable Docker setup. |

### Practical completion estimate

- **Demo/UI milestone:** approximately 80% complete. The dashboard, demo playback, workflow structure, and major backend modules are present.
- **Production-ready platform:** approximately 55-65% complete. The remaining work is concentrated in repository ingestion, real session creation/persistence, reliable live streaming, GitHub integration testing, sandbox hardening, and deployment/observability.

These percentages are engineering estimates based on the current source, not measured project-management metrics.

## What The Project Does

The intended product flow is:

1. A GitHub webhook reports an issue or pull-request event.
2. FixForge creates an initial repair state containing repository, issue, and retry information.
3. The Planner identifies a repair strategy and likely target files.
4. The Retriever searches historical fixes and gathers code context.
5. The Diagnoser classifies the failure and estimates severity.
6. The Fixer generates a unified diff.
7. The Verifier applies the diff in a Docker sandbox and runs pytest.
8. A failed verification returns to the Fixer until `MAX_RETRIES` is reached.
9. The Confidence Engine combines test, semantic, context, and consistency signals.
10. The Reporter formats the diagnosis, test output, confidence score, and patch, then attempts to post a GitHub review comment.
11. The frontend displays agent progress, logs, diagnosis, diff, confidence, and human actions such as approve, retry, or dismiss.

## Repository Layout

```text
FixForge/
|-- README.md                         This project guide
|-- fixforge/
|   |-- run_backend.py                 Backend launcher
|   |-- requirements.txt               Python dependencies
|   |-- agents/                        Seven workflow agent implementations
|   |-- api/
|   |   |-- main.py                    FastAPI application and CORS
|   |   |-- routes/webhooks.py         GitHub webhook intake
|   |   |-- routes/sessions.py         Session reads and human actions
|   |   |-- routes/streams.py           Server-Sent Events stream
|   |   `-- services/github.py         GitHub API integration
|   |-- core/
|   |   |-- config.py                  Environment-backed settings
|   |   |-- llm.py                     LLM client configuration
|   |   `-- state.py                    Shared AgentState contract
|   |-- db/                            SQLAlchemy models and async session
|   |-- graph/                         LangGraph nodes and workflow
|   |-- memory/                        Tree-sitter and ChromaDB helpers
|   |-- sandbox/                       Docker image and runner
|   |-- evaluation/                    Benchmark, baseline, and metric code
|   |-- scripts/                       Backend verification/evaluation scripts
|   `-- tests/                         Pipeline, evaluation, and E2E tests
|-- frontend/
|   |-- package.json                   Vite scripts and JS dependencies
|   `-- src/
|       |-- App.tsx                   FixForge dashboard UI
|       |-- hooks/useFixForgeStream.ts Live SSE/demo state hook
|       |-- data/mockScenarios.ts     Offline demo data
|       `-- utils/demoPlayback.ts     Demo event playback
`-- fixforge_dashboard/                Design references and HTML prototypes
```

## Technology Used And Where

### Backend

- **Python 3.10+**: backend language.
- **FastAPI and Uvicorn**: HTTP API and local server in `fixforge/api/` and `fixforge/run_backend.py`.
- **LangGraph**: state-machine orchestration in `fixforge/graph/workflow.py`.
- **Pydantic and pydantic-settings**: structured agent outputs and `.env` configuration.
- **LangChain-compatible LLM client, Instructor, Groq/OpenAI-compatible APIs**: LLM calls in `fixforge/core/llm.py` and the agent modules.
- **SQLAlchemy async, SQLite/aiosqlite**: session models and database initialization in `fixforge/db/`.
- **Tree-sitter**: Python function/class extraction in `fixforge/memory/ast_parser.py`.
- **ChromaDB**: persistent historical-fix and code-memory collections in `fixforge/memory/chroma_client.py`.
- **Docker SDK**: isolated test execution in `fixforge/sandbox/runner.py`.
- **SSE Starlette**: server-sent execution events in `fixforge/api/routes/streams.py`.
- **pytest and pytest-asyncio**: unit, workflow, evaluation, and E2E tests.

### Frontend

- **React 19 and TypeScript**: dashboard implementation in `frontend/src/`.
- **Vite**: development server and production bundling.
- **Tailwind CSS Vite integration**: utility styling and the dark operational dashboard theme.
- **Lucide React, Framer Motion, Sonner**: UI icons, animation support, and notifications.
- **EventSource/SSE**: live pipeline updates from the backend.
- **Demo playback engine**: lets the dashboard be inspected without API keys or a running backend.

## Configuration

The backend reads a `.env` file from the backend working directory. Start by copying `fixforge/.env.example` to `fixforge/.env` and set the values appropriate for your environment.

```env
GROQ_API_KEY=""
OPENROUTER_API_KEY=""
GITHUB_TOKEN=""
GITHUB_WEBHOOK_SECRET=""
CHROMA_PERSIST_DIR="./chroma_data"
DATABASE_URL="sqlite+aiosqlite:///./fixforge.db"
DOCKER_SANDBOX_IMAGE="fixforge-sandbox:latest"
MAX_RETRIES=3
CONTAINER_TIMEOUT_SEC=60
MAX_CONTAINER_MEMORY="512m"
PORT=8000
```

The LLM keys and GitHub token are not required for the frontend demo. They are required for the corresponding live backend integrations.

## Execute The Project Step By Step

### 1. Clone and enter the repository

```powershell
git clone https://github.com/shreya05-j/FixForge.git
Set-Location .\FixForge
```

### 2. Create the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\fixforge\requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate` and use the equivalent path to `fixforge/requirements.txt`.

### 3. Configure backend settings

```powershell
Copy-Item .\fixforge\.env.example .\fixforge\.env
```

Edit `.env` and add API keys before using live LLM, GitHub, ChromaDB, or sandbox features.

### 4. Build the sandbox image

Docker Desktop must be running.

```powershell
Set-Location .\fixforge
docker build -t fixforge-sandbox:latest -f .\sandbox\Dockerfile.sandbox .
```

The runner mounts the repository read-only, copies it to a scratch directory, applies the candidate diff, disables network access, limits memory, and runs pytest.

### 5. Start the backend

Keep the working directory at `fixforge/` because the current backend imports packages such as `api`, `agents`, and `core` as top-level modules.

```powershell
Set-Location .\fixforge
python .\run_backend.py
```

The API is available at `http://localhost:8000`. A quick health check is:

```powershell
Invoke-RestMethod http://localhost:8000/
```

Expected response:

```json
{"status":"healthy","service":"FixForge Orchestrator"}
```

### 6. Install and start the frontend

Open a second terminal from the repository root:

```powershell
Set-Location .\frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173/`. The page title should be **FixForge AI Frontend**, not DevMeet. If another Vite project already owns port 5173, stop it or use another port with `npm run dev -- --port 5174`.

### 7. Use the dashboard in demo mode

The dashboard works without a backend by selecting a demo scenario from the session selector. Current examples include `demo-flask` and `demo-requests`. Demo playback shows agent transitions, logs, retry behavior, diffs, confidence, and report content.

### 8. Use the live SSE path

Enter a real session ID in the dashboard. The frontend connects to:

```text
GET http://localhost:8000/api/sessions/{session_id}/stream
```

The stream emits `node_start`, `node_progress`, `node_complete`, `retry_loop`, `pipeline_complete`, and `error` events. The current backend can produce a mock stream and has a LangGraph adapter, but live end-to-end session creation still needs to be completed.

### 9. Build the frontend for production

```powershell
Set-Location .\frontend
npm run build
```

The verified output is written to `frontend/dist/`.

## API Endpoints Currently Present

| Method | Path | Purpose | Status |
| --- | --- | --- | --- |
| `GET` | `/` | Backend health check | Working |
| `POST` | `/api/webhooks/github` | Validate and accept GitHub events | Implemented; integration testing needed |
| `GET` | `/api/sessions` | List persisted review sessions | Implemented; depends on populated database |
| `GET` | `/api/sessions/{session_id}` | Read one session, diagnosis, metrics, attempts | Implemented; depends on populated database |
| `POST` | `/api/sessions/{session_id}/action` | Approve, retry, or dismiss a session | Implemented |
| `GET` | `/api/sessions/{session_id}/stream` | Stream workflow events over SSE | Partially implemented |
| `POST` | `/api/sessions/start` | Start a run from the frontend | Missing and must be added |

## What Is Working Now

1. The frontend compiles with TypeScript and Vite.
2. The FixForge dashboard renders locally and includes an offline demo path.
3. The seven-node LangGraph workflow is wired, including retry routing after verification failure.
4. Planner, Diagnoser, and Fixer have structured Pydantic outputs and graceful error fallbacks.
5. Tree-sitter and ChromaDB adapters are present.
6. The Docker runner has network isolation, read-only source mounting, memory limits, timeout handling, and container cleanup.
7. The Reporter creates a Markdown repair report and attempts GitHub publication.
8. Human actions are represented by the session action endpoint and frontend controls.

## What Is Not Complete Or Needs Fixing

### High priority

1. Add `POST /api/sessions/start`, persist a new `ReviewSession`, launch the workflow, and return the UUID expected by the frontend.
2. Replace the in-memory `sessions` dictionary in `webhooks.py` with database-backed state and a session lookup strategy.
3. Make SSE events read from the actual workflow/session and send the final diff, confidence, and GitHub report instead of placeholder values.
4. Implement real repository checkout/file loading for the Retriever. The current AST context contains `def dummy(): pass`.
5. Make the sandbox patch application reliable. The current runner writes the diff through a shell string and ignores `git apply` failure.
6. Add integration tests for webhook signature validation, session creation, SSE, database persistence, Docker verification, and GitHub calls.

### Medium priority

1. Persist agent attempts, diagnoses, metrics, logs, and final reports using the existing SQLAlchemy models.
2. Align package/import structure so tests can run from the repository root without manually setting `PYTHONPATH`.
3. Validate that the configured LLM provider, model names, and structured-output client are compatible in a real environment.
4. Add authentication and authorization before exposing GitHub actions or approval endpoints publicly.
5. Add production logging, request IDs, metrics, error tracking, and secret-management guidance.
6. Add frontend loading, backend-offline, empty-state, and reconnect tests, plus responsive-browser checks.

### Lower priority

1. Finish evaluation and benchmark documentation with reproducible datasets and baseline numbers.
2. Add migrations instead of relying only on `Base.metadata.create_all`.
3. Add deployment configuration for the API, worker, database, Chroma persistence, and frontend hosting.
4. Harden diff handling against malformed patches, path traversal, oversized input, and shell injection.

## Verification Performed

The current repository was checked on 2026-09-21:

- `frontend/npm run build`: **passed**.
- Frontend browser check at `http://localhost:5173/`: **passed**; the page title is `FixForge AI Frontend` and the dashboard renders.
- `fixforge/pytest -q`: **not passed**; test collection stopped with `ModuleNotFoundError` for `core` and `fixforge`, showing that the current test import layout needs correction.

The failed test collection is a repository setup issue, not evidence that every test assertion fails. Run the tests again after standardizing package imports and test configuration.

## Recommended Completion Order

1. Add and test the missing session-start endpoint.
2. Introduce one durable session lifecycle shared by webhook, API, workflow, and SSE.
3. Replace Retriever placeholders with repository checkout and AST extraction.
4. Connect real workflow events and final state to SSE.
5. Persist attempts, diagnoses, metrics, and logs.
6. Make Docker patching and sandbox tests deterministic and secure.
7. Add integration tests and fix package imports.
8. Test GitHub PR comments and human approval actions against a test repository.
9. Add deployment, authentication, observability, and frontend regression coverage.

## Important Development Notes

- Run backend commands from `FixForge/fixforge/` until the package layout is normalized.
- Run frontend commands from `FixForge/frontend/`.
- Do not commit `.env`, API keys, GitHub tokens, database files, Chroma data, or Docker credentials.
- The dashboard demo is the safest way to inspect the UI without external services.
- A successful frontend build does not mean the live repair pipeline is complete; the missing session-start and persistence path still block a full product workflow.
