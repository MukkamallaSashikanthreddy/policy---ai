from __future__ import annotations

from functools import lru_cache
from typing import Sequence


from policylens.config import settings


@lru_cache(maxsize=1)
def _load_model():
    # Import torch / sentence-transformers only on first embedding request.
    # This keeps initial Streamlit page rendering lightweight.
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model, device="cpu")


class LocalEmbedder:
    """Local semantic embeddings; model weights download once and are then cached."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = _load_model().encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
