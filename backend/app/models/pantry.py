from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PantryItem(Base):
    """A user's on-hand ingredient. `user_key` is the authed identity."""

    __tablename__ = "pantry_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(Text, index=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    # A staple is "always in my pantry"; regular items are transient.
    is_staple: Mapped[bool] = mapped_column(Boolean, default=False)
    qty: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    unit: Mapped[str] = mapped_column(Text, nullable=True)
    expires_on: Mapped[date] = mapped_column(Date, nullable=True)
