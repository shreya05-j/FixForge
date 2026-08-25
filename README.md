# FixForge

FixForge is an explainable, self-verifying multi-agent autonomous software repair platform. It orchestrates a sophisticated pipeline of seven distinct LangGraph agents to automatically localize bugs, synthesize patches, execute secure verification loops, and deliver calibrated confidence scores for the proposed fixes.

## Overview

Modern software development requires rapid and reliable issue resolution. FixForge tackles this by providing an end-to-end autonomous repair system. When an issue is detected (e.g., via a GitHub webhook), FixForge kicks off an asynchronous orchestration process. It uses advanced static analysis, semantic search, and Large Language Models (LLMs) to understand, diagnose, and fix the codebase. 

Crucially, FixForge does not just propose a fix; it securely sandboxes the code and runs verification tests to ensure the patch resolves the issue without introducing regressions.

## Key Features

- **Multi-Agent Orchestration**: Utilizes LangGraph to coordinate a seven-agent workflow including Planner, Retriever, Diagnoser, Fixer, Verifier, Confidence Scorer, and Reporter.
- **Advanced Context Retrieval**: Employs Tree-sitter for Abstract Syntax Tree (AST) parsing and ChromaDB for semantic code search, ensuring the LLM has accurate localized context.
- **Sandboxed Verification**: Automatically tests proposed patches in a secure, network-isolated Docker sandbox using pytest, guaranteeing that fixes are functional and safe before reporting.
- **Automated Reporting**: Generates structured, professional GitHub Pull Request markdown with detailed diagnoses, confidence metrics, and clear patch diffs.
- **Explainable Diagnostics**: Every step of the pipeline is tracked and explainable, providing a clear audit trail of how the system arrived at a specific fix.

## Architecture

The system is designed with a highly modular architecture:

1. **API Layer (FastAPI)**: Handles incoming GitHub webhooks and manages session states.
2. **Orchestration Pipeline (LangGraph)**: The core state machine that drives the agents through the repair lifecycle.
3. **Sandbox Environment (Docker)**: An isolated container execution environment for running verification loops safely.
4. **Memory & Storage**: 
   - SQLite/SQLAlchemy for relational session data.
   - ChromaDB for vector-based semantic search.
   - Tree-sitter for robust structural code understanding.

## Installation and Setup

### Prerequisites

- Python 3.10+
- Docker (for sandboxed verification)
- Valid API Keys (Groq, OpenRouter)
- GitHub Personal Access Token

### Environment Configuration

Create a `.env` file in the root directory and populate it with the required configuration variables:

```env
GROQ_API_KEY="your_groq_api_key"
OPENROUTER_API_KEY="your_openrouter_api_key"
GITHUB_TOKEN="your_github_token"
SANDBOX_TIMEOUT=30
CHROMA_DB_PATH="./chroma_data"
DATABASE_URL="sqlite:///./fixforge.db"
```

### Running the Application

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the API Server**:
   ```bash
   uvicorn api.main:app --reload
   ```

3. **Build the Sandbox Image**:
   Ensure your Docker environment is running and build the sandbox image:
   ```bash
   docker build -t fixforge-sandbox -f sandbox/Dockerfile.sandbox .
   ```

## Workflow Summary

1. **Planning**: Parses the issue and prepares the execution state.
2. **Retrieval**: Gathers relevant code context using AST and semantic search.
3. **Diagnosis**: Analyzes the root cause of the bug using LLMs.
4. **Fixing**: Generates a targeted code patch.
5. **Verification**: Applies the patch and runs tests within the Docker sandbox.
6. **Confidence Scoring**: Evaluates the success of the verification phase to assign a reliability score.
7. **Reporting**: Compiles the findings into a comprehensive markdown report.
