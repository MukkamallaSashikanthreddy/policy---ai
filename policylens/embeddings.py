from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from policylens.config import settings


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    # CPU keeps the starter project broadly compatible with ordinary Windows laptops.
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
        return np.asarray(vectors, dtype=np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
