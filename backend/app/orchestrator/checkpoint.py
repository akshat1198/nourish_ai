"""Graph checkpointer (Stage 4.3, AGENT-04).

Keyed by thread_id (= session_id), a checkpointer persists PlanState between
graph invocations, so a refinement turn continues the thread without resending
the pantry. MemorySaver is the default (process-local, survives across requests
in the running uvicorn process). PostgresSaver adds restart-survival when
CHECKPOINT_BACKEND=postgres and it initializes cleanly; per Risk 3 we fall back
to MemorySaver rather than fight it.
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings

logger = logging.getLogger(__name__)

_checkpointer = None


def _postgres_saver():
    """Best-effort PostgresSaver over a thread-safe connection pool; None on failure."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        # langgraph-checkpoint-postgres uses psycopg(3); strip the +psycopg2 driver.
        conn = settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
        # A pool (not a single connection) so concurrent FastAPI threads are safe.
        pool = ConnectionPool(conn, max_size=8, open=True, kwargs={"autocommit": True})
        saver = PostgresSaver(pool)
        saver.setup()  # create checkpoint tables if absent
        logger.info("using PostgresSaver checkpointer (pool)")
        return saver
    except Exception as e:  # Risk 3: don't fight it
        logger.warning("PostgresSaver unavailable, falling back to MemorySaver: %s", e)
        return None


def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        if settings.CHECKPOINT_BACKEND == "postgres":
            _checkpointer = _postgres_saver()
        if _checkpointer is None:
            _checkpointer = MemorySaver()
            logger.info("using MemorySaver checkpointer")
    return _checkpointer
