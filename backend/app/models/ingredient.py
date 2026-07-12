from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Ingredient(Base):
    """Canonical ingredient vocabulary — the normalization spine.

    All matching happens against canonical ingredient ids; free-text names
    resolve here via `name` or `aliases` (e.g. "capsicum" -> bell pepper).
    """

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, index=True)
    category: Mapped[str] = mapped_column(Text)  # protein/vegetable/dairy/grain/pantry/...
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
