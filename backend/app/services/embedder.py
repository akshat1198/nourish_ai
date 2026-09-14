"""Text embedding behind a swappable interface.

The `Embedder` Protocol is the seam Risk 1 relies on, and the swap it was built
for has happened: torch + sentence-transformers cost ~337 MB resident to produce
a 384-float vector, which does not fit a 512 MB box alongside the API. The ONNX
runtime loads the same all-MiniLM-L6-v2 weights in ~230 MB, so `fastembed` is
the default and the torch path stays selectable via EMBEDDER_BACKEND.

Both backends emit the same vectors -- test_embedder_parity asserts cosine
>= 0.9999 over fixed strings -- so stored embeddings survive the swap and
RANKING_VERSION does not move. If that test ever fails the corpus needs
re-embedding before the backend can change.

The model is loaded lazily as a process-wide singleton so import stays cheap.
"""
from __future__ import annotations

from typing import List, Protocol

from app.core.config import settings

EMBED_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"
# fastembed addresses the same weights by their full hub id.
FASTEMBED_MODEL_NAME = f"sentence-transformers/{MODEL_NAME}"


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


class FastEmbedEmbedder:
    """ONNX embedder (default). Same weights as the torch path, a third of the RAM."""

    dim = EMBED_DIM

    def __init__(self, model_name: str = FASTEMBED_MODEL_NAME):
        self._model_name = model_name
        self._model = None  # lazy

    def _ensure(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=self._model_name, threads=settings.EMBEDDER_THREADS
            )
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # fastembed normalizes output, matching normalize_embeddings=True above,
        # and yields a generator in input order.
        return [v.tolist() for v in self._ensure().embed(texts)]


_BACKENDS = {
    "fastembed": FastEmbedEmbedder,
    "sentence-transformers": SentenceTransformerEmbedder,
}

_default: Embedder | None = None


def get_embedder() -> Embedder:
    """Process-wide singleton embedder."""
    global _default
    if _default is None:
        try:
            backend = _BACKENDS[settings.EMBEDDER_BACKEND]
        except KeyError:
            raise ValueError(
                f"EMBEDDER_BACKEND must be one of {sorted(_BACKENDS)}, "
                f"got {settings.EMBEDDER_BACKEND!r}"
            )
        _default = backend()
    return _default
