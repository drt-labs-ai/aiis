#!/usr/bin/env python3
"""Index the knowledge base into ChromaDB."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.indexer import index_knowledge_base
from src.observability.logger import configure_logging


def main():
    configure_logging("INFO")
    kb_dir = os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge-base")
    print(f"Indexing knowledge base from: {kb_dir}")
    counts = index_knowledge_base(kb_dir)
    for domain, count in counts.items():
        print(f"  {domain}: {count} chunks indexed")
    print("Done.")


if __name__ == "__main__":
    main()
