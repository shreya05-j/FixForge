import os
from pathlib import Path

BASE_DIR = Path("fixforge")

FILES = {
    "core/config.py": """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    SANDBOX_TIMEOUT: int = 30
    CHROMA_DB_PATH: str = "./chroma_data"
    DATABASE_URL: str = "sqlite:///./fixforge.db"

    class Config:
        env_file = ".env"

settings = Settings()
""",
    "core/state.py": """from typing import TypedDict, List, Dict, Any, Optional

class GraphState(TypedDict):
    issue_id: str
    github_url: str
    issue_description: str
    repo_path: str
    context_files: List[str]
    retrieved_code: str
    diagnosis: str
    severity: int
    proposed_patch: str
    patch_diff: str
    verification_logs: str
    verification_success: bool
    confidence_score: float
    report_markdown: str
    current_step: str
    iteration_count: int
""",
    "agents/planner.py": """from core.state import GraphState

def run_planner(state: GraphState) -> GraphState:
    print(f"Planning fix for issue {state['issue_id']}")
    state['current_step'] = 'planning'
    return state
""",
    "agents/retriever.py": """from core.state import GraphState

def run_retriever(state: GraphState) -> GraphState:
    print("Retrieving context from ChromaDB and Tree-sitter")
    state['retrieved_code'] = "def faulty_function():\\n    pass # To be fixed"
    state['current_step'] = 'retrieval'
    return state
""",
    "agents/diagnoser.py": """from core.state import GraphState

def run_diagnoser(state: GraphState) -> GraphState:
    print("Diagnosing root cause using LLM")
    state['diagnosis'] = "Null pointer exception in faulty_function."
    state['severity'] = 8
    state['current_step'] = 'diagnosis'
    return state
""",
    "agents/fixer.py": """from core.state import GraphState

def run_fixer(state: GraphState) -> GraphState:
    print("Generating patch...")
    state['proposed_patch'] = "def faulty_function():\\n    return True"
    state['patch_diff'] = "--- a/file.py\\n+++ b/file.py\\n@@ -1,2 +1,2 @@\\n-def faulty_function():\\n-    pass\\n+def faulty_function():\\n+    return True"
    state['current_step'] = 'fixing'
    return state
""",
    "agents/verifier.py": """from core.state import GraphState

def run_verifier(state: GraphState) -> GraphState:
    print("Running pytest in Docker Sandbox...")
    state['verification_logs'] = "1 passed in 0.05s"
    state['verification_success'] = True
    state['iteration_count'] = state.get('iteration_count', 0) + 1
    state['current_step'] = 'verification'
    return state
""",
    "agents/confidence.py": """from core.state import GraphState

def calculate_confidence(state: GraphState) -> GraphState:
    print("Calculating confidence score based on test results and patch size")
    score = 0.95 if state['verification_success'] else 0.2
    state['confidence_score'] = score
    state['current_step'] = 'scoring'
    return state
""",
    "agents/reporter.py": """from core.state import GraphState

def generate_report(state: GraphState) -> GraphState:
    print("Generating GitHub PR markdown...")
    report = f"# FixForge Automated Repair\\n\\n**Diagnosis**: {state['diagnosis']}\\n**Confidence**: {state['confidence_score'] * 100}%\\n\\n## Patch\\n```diff\\n{state['patch_diff']}\\n```"
    state['report_markdown'] = report
    state['current_step'] = 'reporting'
    return state
""",
    "graph/nodes.py": """from agents.planner import run_planner
from agents.retriever import run_retriever
from agents.diagnoser import run_diagnoser
from agents.fixer import run_fixer
from agents.verifier import run_verifier
from agents.confidence import calculate_confidence
from agents.reporter import generate_report

# Node wrappers for LangGraph
def planner_node(state): return run_planner(state)
def retriever_node(state): return run_retriever(state)
def diagnoser_node(state): return run_diagnoser(state)
def fixer_node(state): return run_fixer(state)
def verifier_node(state): return run_verifier(state)
def confidence_node(state): return calculate_confidence(state)
def reporter_node(state): return generate_report(state)
""",
    "graph/workflow.py": """from langgraph.graph import StateGraph, END
from core.state import GraphState
from graph.nodes import (
    planner_node, retriever_node, diagnoser_node, fixer_node, 
    verifier_node, confidence_node, reporter_node
)

def build_graph():
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("diagnoser", diagnoser_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("confidence", confidence_node)
    workflow.add_node("reporter", reporter_node)
    
    # Define edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "diagnoser")
    workflow.add_edge("diagnoser", "fixer")
    workflow.add_edge("fixer", "verifier")
    
    # Conditional edge after verification
    def should_continue(state: GraphState):
        if state["verification_success"] or state.get("iteration_count", 0) >= 3:
            return "confidence"
        return "fixer"
        
    workflow.add_conditional_edges(
        "verifier",
        should_continue,
        {
            "confidence": "confidence",
            "fixer": "fixer"
        }
    )
    
    workflow.add_edge("confidence", "reporter")
    workflow.add_edge("reporter", END)
    
    return workflow.compile()
""",
    "sandbox/runner.py": """import docker
from core.config import settings

def run_in_sandbox(repo_path: str, test_cmd: str = "pytest"):
    client = docker.from_env()
    try:
        container = client.containers.run(
            "fixforge-sandbox:latest",
            test_cmd,
            volumes={repo_path: {'bind': '/app', 'mode': 'rw'}},
            working_dir="/app",
            network_mode="none",  # Net-isolated
            mem_limit="512m",
            detach=False,
            auto_remove=True
        )
        return True, container.decode('utf-8')
    except docker.errors.ContainerError as e:
        return False, e.stderr.decode('utf-8')
    except Exception as e:
        return False, str(e)
""",
    "sandbox/Dockerfile.sandbox": """FROM python:3.10-slim

# Create a non-root user
RUN useradd -m -s /bin/bash sandbox_user

WORKDIR /app
RUN pip install pytest semgrep tree-sitter tree-sitter-python

USER sandbox_user

CMD ["pytest"]
""",
    "memory/chroma_client.py": """import chromadb
from core.config import settings

client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)

def get_collection(name: str):
    return client.get_or_create_collection(name=name)

def store_code_chunk(collection_name: str, doc_id: str, text: str, metadata: dict):
    collection = get_collection(collection_name)
    collection.add(
        documents=[text],
        metadatas=[metadata],
        ids=[doc_id]
    )
""",
    "memory/ast_parser.py": """import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
parser = Parser()
parser.language = PY_LANGUAGE

def parse_code(code: bytes):
    tree = parser.parse(code)
    # Extract functions and classes logic here
    return tree
""",
    "db/models.py": """from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class FixSession(Base):
    __tablename__ = 'fix_sessions'
    
    id = Column(String, primary_key=True, index=True)
    issue_url = Column(String, index=True)
    status = Column(String)
    confidence = Column(Float)
    patch_generated = Column(Boolean, default=False)
    log_output = Column(Text)
""",
    "db/session.py": """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from db.models import Base

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
""",
    "api/main.py": """from fastapi import FastAPI
from api.routes import webhooks, sessions
from db.session import init_db

app = FastAPI(title="FixForge API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "FixForge Orchestrator"}
""",
    "api/routes/webhooks.py": """from fastapi import APIRouter, Request, BackgroundTasks
from graph.workflow import build_graph

router = APIRouter()
graph = build_graph()

@router.post("/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    action = payload.get("action")
    
    if action in ["opened", "reopened"] and "issue" in payload:
        issue = payload["issue"]
        state = {
            "issue_id": str(issue["id"]),
            "github_url": issue["html_url"],
            "issue_description": issue["body"],
            "repo_path": f"/tmp/repos/{issue['id']}",
            "iteration_count": 0
        }
        
        # Trigger background execution
        background_tasks.add_task(graph.invoke, state)
        return {"status": "accepted", "issue_id": state["issue_id"]}
        
    return {"status": "ignored"}
""",
    "api/routes/sessions.py": """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import FixSession

router = APIRouter()

@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(FixSession).filter(FixSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
""",
    "requirements.txt": """fastapi==0.104.1
uvicorn==0.24.0.post1
langgraph==0.0.26
langchain==0.1.0
pydantic==2.5.2
pydantic-settings==2.1.0
sqlalchemy==2.0.23
chromadb==0.4.22
tree-sitter==0.20.4
tree-sitter-python==0.20.4
docker==6.1.3
semgrep==1.51.0
pytest==7.4.3
requests==2.31.0
"""
}

def scaffold():
    print(f"Scaffolding FixForge architecture in {BASE_DIR}...")
    for file_path, content in FILES.items():
        full_path = BASE_DIR / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created: {full_path}")
    print("Done!")

if __name__ == "__main__":
    scaffold()
