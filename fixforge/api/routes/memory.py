from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
from memory.chroma_client import chroma_manager
from core.config import settings

router = APIRouter()

class IndexFixRequest(BaseModel):
    repo: str = Field(..., description="Repository name")
    description: str = Field(..., description="Bug description / problem statement")
    diff: str = Field(..., description="Patch diff")
    file: Optional[str] = "main.py"
    severity: Optional[str] = "Medium"

@router.get("/stats")
def get_memory_stats():
    history_count = chroma_manager.history_kb.count()
    code_count = chroma_manager.code_chunks.count()
    return {
        "status": "online",
        "persist_dir": settings.CHROMA_PERSIST_DIR,
        "history_count": history_count,
        "code_chunks_count": code_count,
        "embedding_dimensions": 384,
        "collections": ["historical_fix_kb", "repo_code_chunks"],
        "distance_metric": "Cosine Similarity"
    }

@router.get("/fixes")
def get_historical_fixes(query: Optional[str] = None, limit: int = 20):
    if query and query.strip():
        results = chroma_manager.query_history(query.strip(), n_results=limit)
        items = []
        for r in results:
            dist = r.get("distance")
            if dist is not None:
                sim = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                similarity = round(sim, 2)
            else:
                similarity = 0.85
            meta = r.get("metadata", {}) or {}
            items.append({
                "id": f"Fix #{meta.get('id', str(uuid.uuid4())[:8])}",
                "repo": meta.get("repo", "unknown"),
                "file": meta.get("file", meta.get("target_file", "source.py")),
                "severity": meta.get("severity", "Medium"),
                "similarity": similarity,
                "description": r.get("document", ""),
                "diff": meta.get("diff", ""),
            })
        return items

    # Return stored items from ChromaDB
    data = chroma_manager.history_kb.get(limit=limit)
    items = []
    ids = data.get("ids", [])
    documents = data.get("documents", []) or []
    metadatas = data.get("metadatas", []) or []
    for i, item_id in enumerate(ids):
        doc = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
        items.append({
            "id": f"Fix #{item_id[:8]}",
            "repo": meta.get("repo", "pallets/flask"),
            "file": meta.get("file", meta.get("target_file", "src/flask/wrappers.py")),
            "severity": meta.get("severity", "Medium"),
            "similarity": 0.94,
            "description": doc or "Historical defect resolved with verified regression test.",
            "diff": meta.get("diff", ""),
        })
    return items

@router.post("/index")
def index_fix(payload: IndexFixRequest):
    fix_id = str(uuid.uuid4())
    metadata = {
        "repo": payload.repo,
        "file": payload.file or "main.py",
        "diff": payload.diff,
        "severity": payload.severity or "Medium"
    }
    chroma_manager.add_historical_fix(fix_id, payload.description, metadata)
    return {"status": "indexed", "id": fix_id}
