"""Knowledge base MCP tools."""
from __future__ import annotations
import logging
from typing import Any
from src.rag.retriever import get_retriever

logger = logging.getLogger(__name__)


async def search_knowledge_base(
    query: str,
    domain: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """Search the RAG knowledge base for relevant documentation."""
    retriever = get_retriever()
    docs = retriever.search(query=query, domain=domain, top_k=top_k)
    return {
        "query": query,
        "domain": domain,
        "total_results": len(docs),
        "results": [
            {
                "content": d.content[:800],
                "source": d.source,
                "filename": d.filename,
                "relevance_score": d.relevance_score,
            }
            for d in docs
        ],
    }


async def retrieve_runbook(runbook_name: str, domain: str) -> dict[str, Any]:
    """Retrieve a specific runbook by name."""
    retriever = get_retriever()
    docs = retriever.search(query=f"runbook {runbook_name}", domain=domain, top_k=3)
    if not docs:
        return {"runbook": runbook_name, "found": False, "content": None}
    best = docs[0]
    return {
        "runbook": runbook_name,
        "found": True,
        "source": best.source,
        "content": best.content,
        "relevance_score": best.relevance_score,
    }


async def retrieve_architecture_docs(component: str, domain: str) -> dict[str, Any]:
    """Retrieve architecture documentation for a component."""
    retriever = get_retriever()
    docs = retriever.search(query=f"architecture {component}", domain=domain, top_k=3)
    return {
        "component": component,
        "domain": domain,
        "documents": [
            {"source": d.source, "content": d.content[:600], "score": d.relevance_score}
            for d in docs
        ],
    }
