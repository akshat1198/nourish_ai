"""Text embedding behind a swappable interface (Stage 2.1).

The `Embedder` Protocol is the seam Risk 1 relies on: if the sentence-
transformers + torch stack proves too heavy for the image, swap in a
`FastEmbedEmbedder` (ONNX) without touching any caller. The model is loaded
lazily as a process-wide singleton so import stays cheap and the ~90 MB model
is fetched only when embeddings are first needed.
"""
from __future__ import annotations

from typing import List, Protocol

EMBED_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"


class Embedder(Protocol):
    dim: int

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return one dense vector per input text."""
        ...


class SentenceTransformerEmbedder:
    """Local sentence-transformers embedder (default implementation)."""

    dim = EMBED_DIM

    def __init__(self, model_name: str = MODEL_NAME):
        self._model_name = model_name
        self._model = None  # lazy

    def _ensure(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._ensure()
        vectors = model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return [v.tolist() for v in vectors]


_default: Embedder | None = None


def get_embedder() -> Embedder:
    """Process-wide singleton embedder."""
    global _default
    if _default is None:
        _default = SentenceTransformerEmbedder()
    return _default
