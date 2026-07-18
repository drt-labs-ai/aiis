"""RAG retriever: semantic search over domain-specific collections."""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass
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


@dataclass
class RetrievedDocument:
    content: str
    source: str
    domain: str
    relevance_score: float
    filename: str


class RAGRetriever:
    def __init__(self) -> None:
        self._client = None
        self._embed_model = None
        self._collections: dict[str, Any] = {}

    def _ensure_init(self) -> bool:
        if not _chromadb_available or not _sentence_transformers_available:
            return False
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=CHROMA_PERSIST_DIR,
                settings=Settings(anonymized_telemetry=False),
            )
            self._embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        return True

    def _get_collection(self, domain: str):
        if not self._ensure_init():
            return None
        collection_name = domain.replace("-", "_")
        if collection_name not in self._collections:
            try:
                self._collections[collection_name] = self._client.get_collection(collection_name)
            except Exception:
                return None
        return self._collections[collection_name]

    def search(
        self,
        query: str,
        domain: str,
        top_k: int = 5,
    ) -> list[RetrievedDocument]:
        collection = self._get_collection(domain)
        if collection is None:
            logger.debug(f"RAG: no collection for domain '{domain}'; using fallback")
            return self._fallback_results(query, domain)

        try:
            embedding = self._embed_model.encode([query]).tolist()
            results = collection.query(
                query_embeddings=embedding,
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )

            docs = []
            for i, (content, meta, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                score = max(0.0, 1.0 - distance)
                docs.append(
                    RetrievedDocument(
                        content=content,
                        source=meta.get("source", "unknown"),
                        domain=meta.get("domain", domain),
                        relevance_score=round(score, 4),
                        filename=meta.get("filename", "unknown"),
                    )
                )
            return docs
        except Exception as exc:
            logger.warning(f"RAG search failed: {exc}")
            return self._fallback_results(query, domain)

    def _fallback_results(self, query: str, domain: str) -> list[RetrievedDocument]:
        """Return mock results when ChromaDB is unavailable."""
        return [
            RetrievedDocument(
                content=f"[Fallback] No ChromaDB available. Query was: {query}",
                source=f"{domain}/fallback",
                domain=domain,
                relevance_score=0.1,
                filename="fallback.md",
            )
        ]


_retriever = RAGRetriever()


def get_retriever() -> RAGRetriever:
    return _retriever
