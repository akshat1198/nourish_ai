"""Embedder contract test.

Loading the model takes ~20s, so this is gated behind RUN_EMBEDDER_TESTS=1
to keep the default suite fast. The embedder is also exercised live by
scripts/embed_recipes.py and the hybrid eval.
"""
import os

import pytest

runs_embedder = pytest.mark.skipif(
    os.getenv("RUN_EMBEDDER_TESTS") != "1",
    reason="set RUN_EMBEDDER_TESTS=1 to run (loads the model, ~20s)",
)


def test_embedder_dim_constant():
    from app.services.embedder import EMBED_DIM, get_embedder

    assert get_embedder().dim == EMBED_DIM == 384


def test_embed_empty_is_noop():
    from app.services.embedder import get_embedder

    assert get_embedder().embed([]) == []


@runs_embedder
def test_embed_returns_normalized_384d_vectors():
    import math

    from app.services.embedder import get_embedder

    vecs = get_embedder().embed(["chicken and rice", "tomato pasta"])
    assert len(vecs) == 2
    for v in vecs:
        assert len(v) == 384
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-3  # normalize_embeddings=True


def test_unknown_backend_is_rejected(monkeypatch):
    """A typo in EMBEDDER_BACKEND must fail loudly, not silently pick a default.

    Choosing the wrong backend would embed queries with a model the stored
    corpus vectors did not come from, which degrades ranking without erroring.
    """
    from app.core.config import settings
    from app.services import embedder

    monkeypatch.setattr(settings, "EMBEDDER_BACKEND", "nope", raising=False)
    monkeypatch.setattr(embedder, "_default", None)
    with pytest.raises(ValueError, match="EMBEDDER_BACKEND"):
        embedder.get_embedder()


@runs_embedder
def test_embedder_parity_onnx_matches_torch():
    """The ONNX and torch backends must agree, or the stored corpus is stale.

    7,533 recipe vectors were written by the torch path. fastembed is the
    default now purely to fit the deployed memory budget, so it has to be a
    drop-in: if this drifts, the corpus needs re-embedding and RANKING_VERSION
    needs a bump before the backend can change.
    """
    import math

    from app.services.embedder import FastEmbedEmbedder, SentenceTransformerEmbedder

    texts = [
        "chicken spinach garlic",
        "paneer butter masala with cream and tomato",
        "quick vegan thai green curry",
        "25g rolled oats",
    ]
    onnx = FastEmbedEmbedder().embed(texts)
    torch_vecs = SentenceTransformerEmbedder().embed(texts)

    assert len(onnx) == len(torch_vecs) == len(texts)
    for text, a, b in zip(texts, onnx, torch_vecs):
        dot = sum(x * y for x, y in zip(a, b))
        norms = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
        assert dot / norms >= 0.9999, f"backends diverged on {text!r}"
