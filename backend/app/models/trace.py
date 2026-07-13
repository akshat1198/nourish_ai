from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentTrace(Base):
    """One row per node/step of an agent run (AGENT-05).

    The single append-only observability trail written by BOTH engines — the
    Stage-3 single-agent loop (`engine="single"`) and the Stage-4 LangGraph
    orchestrator (`engine="graph"`) — so the traces endpoint and the comparative
    eval read one uniform shape regardless of which engine produced the run.
    """

    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, index=True)
    engine: Mapped[str] = mapped_column(Text)  # single | graph
    seq: Mapped[int] = mapped_column(Integer, default=0)  # order within one run
    node: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)  # node | llm | tool_use | summary | ...
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
