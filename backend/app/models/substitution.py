from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Substitution(Base):
    """Directed ingredient swap: `ingredient` can be replaced by `substitute`."""

    __tablename__ = "substitutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), index=True
    )
    substitute_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    ratio: Mapped[str] = mapped_column(Text, default="1:1")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    # Diet goals this swap enables, e.g. ["vegan", "dairy_free"]
    diet_ok: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
