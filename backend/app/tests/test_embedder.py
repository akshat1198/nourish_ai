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
