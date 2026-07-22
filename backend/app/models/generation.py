from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GenerationEvent(Base):
    """One row per agent run — the audit + eval trail."""

    __tablename__ = "generation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    # Final unresolved violations (empty on a clean/repaired-clean run).
    violations: Mapped[list] = mapped_column(JSONB, default=list)
    repaired: Mapped[bool] = mapped_column(Boolean, default=False)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
