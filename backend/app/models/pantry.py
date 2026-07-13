from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PantryItem(Base):
    """A user's on-hand ingredient. `user_key` is an opaque client key (no auth yet)."""

    __tablename__ = "pantry_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(Text, index=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    qty: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    unit: Mapped[str] = mapped_column(Text, nullable=True)
    expires_on: Mapped[date] = mapped_column(Date, nullable=True)
