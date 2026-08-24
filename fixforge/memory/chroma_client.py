import chromadb
from core.config import settings
from typing import List, Dict, Any

class ChromaManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.code_chunks = self.client.get_or_create_collection(name="repo_code_chunks")
        self.history_kb = self.client.get_or_create_collection(name="historical_fix_kb")
        
    def add_historical_fix(self, fix_id: str, description: str, metadata: Dict[str, Any]):
        self.history_kb.add(
            documents=[description],
            metadatas=[metadata],
            ids=[fix_id]
        )
        
    def query_history(self, query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        results = self.history_kb.query(
            query_texts=[query_text],
            n_results=n_results
        )
        # Flatten results
        if not results['documents']:
            return []
        out = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            out.append({"document": doc, "metadata": meta})
        return out

chroma_manager = ChromaManager()
