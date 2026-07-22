"""Deterministic A/B variant assignment (Stage 13.2).

Same (experiment, session_id) always resolves to the same variant — no state
to store. Uses hashlib (stable across processes), NOT Python's built-in
hash() (salted per-process by default, so it would reassign variants on every
restart).
"""
from __future__ import annotations

import hashlib

from app.core.config import settings


def assign_variant(session_id: str, experiment: str) -> str:
    variants = settings.experiment_variants_list
    digest = hashlib.sha256(f"{experiment}:{session_id}".encode()).hexdigest()
    return variants[int(digest, 16) % len(variants)]
