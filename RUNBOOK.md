# FixForge AI — Operations Runbook

This runbook describes how to boot, configure, evaluate, and test FixForge AI in both live and simulated modes.

---

## 1. System Requirements

- **Operating System**: Windows 10/11, macOS, or Linux
- **Python**: 3.10+ (Tested on Python 3.12.10)
- **Node.js**: 18+ (Tested on Node 24 / npm 11)
- **Docker**: Docker Desktop (Engine 29+, WSL2 on Windows)
- **Groq API Key**: Optional for live LLM mode; system falls back to offline heuristics when absent.

---

## 2. Configuration & Secrets (`.env`)

Create `.env` at the root of `fixforge/`:
```env
# Core API Settings
GROQ_API_KEY=gsk_your_key_here
PORT=8000
GITHUB_DRY_RUN=true
WORKFLOW_TIMEOUT_SEC=300
LLM_CONSISTENCY_SAMPLES=2

# Database Connection (SQLite vs PostgreSQL Deviation)
DATABASE_URL=sqlite+aiosqlite:///./fixforge.db

# Vector Memory & Docker Sandbox
CHROMA_PERSIST_DIR=./chroma_data
DOCKER_SANDBOX_IMAGE=fixforge-sandbox:latest
CONTAINER_TIMEOUT_SEC=60
MAX_CONTAINER_MEMORY=512m
```

### Architectural Deviation: SQLite vs. PostgreSQL
- **SRS Requirement**: Section 5 specified PostgreSQL with async connection pooling.
- **Implemented Reality**: FixForge implements asynchronous SQLAlchemy (`AsyncSessionLocal`) with `sqlite+aiosqlite:///./fixforge.db`.
- **Rationale**: Enables zero-configuration local installation on student workstations without requiring a separate PostgreSQL service daemon. Switching to PostgreSQL requires only updating `DATABASE_URL=postgresql+asyncpg://user:pass@host/db`.

---

## 3. Operational Commands

### A. One-Command Startup
Launches the FastAPI backend on port 8000 and the Vite React frontend on port 5173:
```powershell
.\run_all.ps1
```

### B. Health Preflight Verification
Verify system capabilities (LLM, Docker, Sandbox image, GitHub mode):
```powershell
curl http://localhost:8000/api/health
```
Expected response:
```json
{
  "status": "healthy",
  "overall_mode": "LIVE",
  "llm_mode": "live",
  "docker_mode": "live",
  "sandbox_image": "present",
  "github_mode": "dry_run"
}
```

### C. Automated Test Suite (32 Tests)
Run all unit, integration, persistence, and gate tests:
```powershell
.venv\Scripts\pytest fixforge/tests -v
```

### D. Live Acceptance Smoke Test (10 Runs)
Run 10 sequential live repair workflows with mode logging:
```powershell
.venv\Scripts\python scripts/e2e_smoke.py --runs 10
```

### E. Curated Benchmark Evaluation (100 Runs)
Run the 3-pass comparative benchmark evaluation:
```powershell
.venv\Scripts\python scripts/run_live_evaluation.py
```

### F. Frontend Build & Vitest
Compile TypeScript frontend and run unit tests:
```powershell
cd frontend
npm run build
npm run test
```
