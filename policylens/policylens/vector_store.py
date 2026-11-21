from __future__ import annotations

from pathlib import Path
from typing import Any


from policylens.config import settings
from policylens.embeddings import LocalEmbedder


class ChromaVectorStore:
    """Persistent Chroma collection with explicit locally generated embeddings."""

    def __init__(self, path: str | Path | None = None, collection_name: str = "policylens_chunks") -> None:
        self.path = Path(path or settings.chroma_dir)
        self.path.mkdir(parents=True, exist_ok=True)
        import chromadb  # defer Chroma import until the backend is first requested
        self.client = chromadb.PersistentClient(path=str(self.path))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "description": "PolicyLens PDF text chunks"},
        )
        self.embedder = LocalEmbedder()

    def add_chunks(self, chunks: list[Any], batch_size: int = 128) -> None:
        if not chunks:
            return
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = self.embedder.embed_documents([item.text for item in batch])
            self.collection.upsert(
                ids=[item.chunk_id for item in batch],
                documents=[item.text for item in batch],
                metadatas=[item.metadata for item in batch],
                embeddings=vectors,
            )

    def query(
        self,
        query_text: str,
        *,
        policy_group: str,
        top_k: int = 6,
    ) -> list[dict[str, Any]]:
        total = self.collection.count()
        if total == 0:
            return []
        vector = self.embedder.embed_query(query_text)
        result = self.collection.query(
            query_embeddings=[vector],
            n_results=min(max(1, top_k), total),
            where={"policy_group": policy_group},
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        records: list[dict[str, Any]] = []
        for chunk_id, doc, metadata, distance in zip(ids, docs, metas, distances):
            records.append(
                {
                    "chunk_id": chunk_id,
                    "text": doc or "",
                    "metadata": metadata or {},
                    "distance": float(distance) if distance is not None else None,
                    "similarity": 1.0 - float(distance) if distance is not None else None,
                }
            )
        return records

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine", "description": "PolicyLens PDF text chunks"},
        )
