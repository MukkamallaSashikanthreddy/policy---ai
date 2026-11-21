from __future__ import annotations

from typing import Any

from policylens.config import settings
from policylens.vector_store import ChromaVectorStore


class PolicyRetriever:
    def __init__(self, vector_store: ChromaVectorStore | None = None) -> None:
        self.vector_store = vector_store or ChromaVectorStore()

    def retrieve(
        self, query: str, policy_group: str, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        return self.vector_store.query(
            query,
            policy_group=policy_group,
            top_k=top_k or settings.retrieval_top_k,
        )

    def retrieve_many(
        self, queries: list[str], policy_group: str, per_query: int = 3
    ) -> list[dict[str, Any]]:
        """Retrieve for several clause types, then deduplicate while preserving rank order."""
        ordered: dict[str, dict[str, Any]] = {}
        for query in queries:
            for item in self.retrieve(query, policy_group, top_k=per_query):
                chunk_id = item["chunk_id"]
                if chunk_id not in ordered:
                    ordered[chunk_id] = item
        return list(ordered.values())
