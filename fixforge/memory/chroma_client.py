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
        try:
            count = self.history_kb.count()
            if count == 0:
                return []
            actual_n = min(n_results, count)
            results = self.history_kb.query(
                query_texts=[query_text],
                n_results=actual_n
            )
            # Flatten results
            docs_list = results.get('documents')
            if not docs_list or not docs_list[0]:
                return []
            docs = docs_list[0]
            out = []
            distances_list = results.get('distances')
            distances = distances_list[0] if (distances_list is not None and len(distances_list) > 0 and distances_list[0] is not None) else []
            metadatas_list = results.get('metadatas')
            metadatas = metadatas_list[0] if (metadatas_list is not None and len(metadatas_list) > 0 and metadatas_list[0] is not None) else []
            for i, (doc, meta) in enumerate(zip(docs, metadatas)):
                dist = distances[i] if i < len(distances) else None
                out.append({"document": doc, "metadata": meta, "distance": dist})
            return out
        except Exception:
            return []

chroma_manager = ChromaManager()
