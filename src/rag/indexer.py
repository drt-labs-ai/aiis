"""RAG indexer: loads markdown documents and stores them in ChromaDB."""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_chromadb_available = False
_sentence_transformers_available = False

try:
    import chromadb
    from chromadb.config import Settings
    _chromadb_available = True
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer
    _sentence_transformers_available = True
except ImportError:
    pass


EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")


def _get_embedding_fn():
    if not _sentence_transformers_available or not _chromadb_available:
        return None
    from chromadb import EmbeddingFunction, Documents, Embeddings
    model = SentenceTransformer(EMBED_MODEL_NAME)

    class EmbeddingFn(EmbeddingFunction):
        def __call__(self, input: Documents) -> Embeddings:
            return model.encode(list(input)).tolist()

    return EmbeddingFn()


def _get_chroma_client():
    if not _chromadb_available:
        return None
    return chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )


def index_knowledge_base(knowledge_base_dir: str = "./knowledge-base") -> dict[str, int]:
    """Index all markdown documents from the knowledge base. Returns doc counts per domain."""
    client = _get_chroma_client()
    if client is None:
        logger.warning("ChromaDB not available; skipping indexing")
        return {}

    embed_fn = _get_embedding_fn()
    kb_path = Path(knowledge_base_dir)
    counts: dict[str, int] = {}

    for domain_dir in ["pre-purchase", "post-purchase"]:
        domain_path = kb_path / domain_dir
        if not domain_path.exists():
            continue

        collection_name = domain_dir.replace("-", "_")
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
            metadata={"domain": domain_dir},
        )

        docs: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        doc_id = 0

        for md_file in domain_path.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            chunks = _chunk_text(text, chunk_size=500, overlap=50)
            for chunk in chunks:
                if chunk.strip():
                    docs.append(chunk)
                    ids.append(f"{domain_dir}-{doc_id}")
                    metadatas.append({
                        "source": str(md_file.relative_to(kb_path)),
                        "domain": domain_dir,
                        "filename": md_file.name,
                    })
                    doc_id += 1

        if docs:
            # Upsert in batches of 100
            for i in range(0, len(docs), 100):
                collection.upsert(
                    documents=docs[i:i+100],
                    ids=ids[i:i+100],
                    metadatas=metadatas[i:i+100],
                )

        counts[domain_dir] = len(docs)
        logger.info(f"Indexed {len(docs)} chunks for domain '{domain_dir}'")

    return counts


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start = end - overlap
    return chunks
