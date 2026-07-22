from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Event(Base):
    """Online analytics event. Append-only; `variant` populated once
    a session is A/B-bucketed; `recipe_id` null for non-recipe
    events (e.g. results_shown)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text)
    recipe_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=True
    )
    variant: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    props: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
