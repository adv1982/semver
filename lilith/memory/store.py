import os
import json
import chromadb
from datetime import datetime
from sentence_transformers import SentenceTransformer
from config import MEMORY_PATH

_client = None
_collection = None
_embedder = None


def init_memory():
    global _client, _collection, _embedder
    os.makedirs(MEMORY_PATH, exist_ok=True)
    _client = chromadb.PersistentClient(path=MEMORY_PATH)
    _collection = _client.get_or_create_collection("lilith_memory")
    _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"[Lilith] Memória carregada: {_collection.count()} registros ✓")


def save(role: str, content: str, metadata: dict = None):
    if _collection is None:
        return
    ts = datetime.utcnow().isoformat()
    doc_id = f"{ts}-{role}"
    meta = {"role": role, "timestamp": ts}
    if metadata:
        meta.update(metadata)
    embedding = _embedder.encode(content).tolist()
    _collection.add(
        documents=[content],
        embeddings=[embedding],
        metadatas=[meta],
        ids=[doc_id],
    )


def recall(query: str, n: int = 8) -> list[dict]:
    if _collection is None or _collection.count() == 0:
        return []
    embedding = _embedder.encode(query).tolist()
    results = _collection.query(query_embeddings=[embedding], n_results=min(n, _collection.count()))
    memories = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        memories.append({"content": doc, "role": meta.get("role", "unknown"), "timestamp": meta.get("timestamp", "")})
    return memories


def build_context(query: str, max_tokens: int = 1200) -> str:
    memories = recall(query)
    if not memories:
        return ""
    lines = ["[Memórias relevantes:]"]
    total = 0
    for m in memories:
        line = f"[{m['timestamp'][:16]} {m['role']}]: {m['content']}"
        total += len(line)
        if total > max_tokens:
            break
        lines.append(line)
    return "\n".join(lines)
