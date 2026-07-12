"""Seed the database from backend/seed_data/*.json (idempotent: wipes & reloads).

Run:  python scripts/seed.py   (from backend/)
Regenerate the JSON first with scripts/generate_corpus.py if templates changed.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Ingredient,
    PantryItem,
    Recipe,
    RecipeIngredient,
    Substitution,
)

SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"


def load(name):
    return json.loads((SEED_DIR / f"{name}.json").read_text())


def main():
    ingredients = load("ingredients")
    recipes = load("recipes")
    substitutions = load("substitutions")

    with SessionLocal() as session:
        # Wipe in FK order (recipes cascade to recipe_ingredients)
        session.execute(delete(PantryItem))
        session.execute(delete(Substitution))
        session.execute(delete(RecipeIngredient))
        session.execute(delete(Recipe))
        session.execute(delete(Ingredient))

        ing_ids = {}
        for ing in ingredients:
            row = Ingredient(
                name=ing["name"], category=ing["category"], aliases=ing["aliases"]
            )
            session.add(row)
            session.flush()
            ing_ids[ing["name"]] = row.id

        for r in recipes:
            recipe = Recipe(
                title=r["title"],
                description=r["description"],
                ingredients=r["items"],
                steps=r["steps"],
                tags=r["tags"],
                diet_labels=r["diet_labels"],
                allergens=r["allergens"],
                time_minutes=r["time_minutes"],
                servings=r["servings"],
                nutrition=r["nutrition"],
                search_text=r["search_text"],
            )
            session.add(recipe)
            session.flush()
            for item in r["items"]:
                session.add(
                    RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=ing_ids[item["name"]],
                        qty=item["qty"],
                        unit=item["unit"],
                        essential=item["essential"],
                    )
                )

        for s in substitutions:
            session.add(
                Substitution(
                    ingredient_id=ing_ids[s["ingredient"]],
                    substitute_id=ing_ids[s["substitute"]],
                    ratio=s["ratio"],
                    confidence=s["confidence"],
                    diet_ok=s["diet_ok"],
                )
            )

        session.commit()

    print(
        f"Seeded {len(recipes)} recipes, {len(ingredients)} ingredients, "
        f"{len(substitutions)} substitutions"
    )


if __name__ == "__main__":
    main()
