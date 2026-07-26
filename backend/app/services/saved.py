"""Saved-recipe persistence. Per-user bookmarks."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Recipe, SavedRecipe
from app.schemas.saved import RecipeSummary


def recipe_summary(r: Recipe) -> RecipeSummary:
    return RecipeSummary(
        id=r.id,
        title=r.title,
        cuisine=r.cuisine,
        region=r.region,
        image_url=r.image_url,
    )


def list_saved(session: Session, user_key: str) -> list[RecipeSummary]:
    rows = (
        session.execute(
            select(Recipe)
            .join(SavedRecipe, SavedRecipe.recipe_id == Recipe.id)
            .where(SavedRecipe.user_key == user_key)
            .order_by(SavedRecipe.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [recipe_summary(r) for r in rows]


def add_saved(session: Session, user_key: str, recipe_id: int) -> None:
    """Idempotent — re-saving is a no-op (unique on user+recipe)."""
    session.execute(
        pg_insert(SavedRecipe)
        .values(user_key=user_key, recipe_id=recipe_id)
        .on_conflict_do_nothing(constraint="uq_saved_user_recipe")
    )
    session.commit()


def remove_saved(session: Session, user_key: str, recipe_id: int) -> None:
    session.execute(
        delete(SavedRecipe).where(
            SavedRecipe.user_key == user_key, SavedRecipe.recipe_id == recipe_id
        )
    )
    session.commit()
