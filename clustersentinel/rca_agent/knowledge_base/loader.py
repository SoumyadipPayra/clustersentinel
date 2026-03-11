"""Loads knowledge base .md documents into ChromaDB for RAG retrieval."""

from __future__ import annotations
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from clustersentinel.config import settings

_DOCS_DIR = Path(__file__).parent / "docs"
_COLLECTION = "hci_knowledge_base"
_CHUNK_SIZE = 800  # characters per chunk
_CHUNK_OVERLAP = 100


def _chunk_text(text: str, source: str) -> list[dict]:
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunk = text[start:end]
        chunks.append({
            "id": f"{source}_{idx}",
            "text": chunk,
            "source": source,
        })
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
        idx += 1
    return chunks


def seed_knowledge_base() -> int:
    """Load all .md files from docs/ into ChromaDB. Returns number of chunks added."""
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    ef = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=_COLLECTION,
        embedding_function=ef,
    )

    all_chunks: list[dict] = []
    for md_file in _DOCS_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        all_chunks.extend(_chunk_text(text, md_file.stem))

    if not all_chunks:
        return 0

    existing_ids = set(collection.get()["ids"])
    new_chunks = [c for c in all_chunks if c["id"] not in existing_ids]

    if new_chunks:
        collection.add(
            ids=[c["id"] for c in new_chunks],
            documents=[c["text"] for c in new_chunks],
            metadatas=[{"source": c["source"]} for c in new_chunks],
        )
    return len(new_chunks)


def retrieve_context(query: str, n_results: int = 4) -> str:
    """Query ChromaDB and return concatenated relevant passages."""
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    ef = embedding_functions.DefaultEmbeddingFunction()
    try:
        collection = client.get_collection(name=_COLLECTION, embedding_function=ef)
    except Exception:
        return ""

    results = collection.query(query_texts=[query], n_results=n_results)
    docs = results.get("documents", [[]])[0]
    return "\n\n---\n\n".join(docs)
