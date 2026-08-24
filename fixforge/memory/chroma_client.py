import chromadb
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
