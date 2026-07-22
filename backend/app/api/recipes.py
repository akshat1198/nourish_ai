"""Recipe detail endpoint — full render of our own stored data.

Public like /recommendations (recipes are shared corpus data, nothing
user-scoped). No Redis / no cache headers: an immutable single-row PK read is
effectively free, and the client caches it (staleTime) — deliberately adds zero
new server cache keys to steer clear of the proven cache-key-drift bug class.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_session
from app.models import Ingredient, Recipe
from app.schemas.recipe import (
    ModifyRequest,
    ModifyResponse,
    RecipeDetail,
    RecipeEnrichment,
    RecipeIngredientLine,
)
from app.services.enrich import enrich_recipe
from app.services.ingredients import normalize
from app.services.modify import modify_recipe

router = APIRouter(prefix="/v1", tags=["recipes"])


def _category_map(recipe: Recipe, session: Session) -> dict[str, str]:
    """normalize(name|alias) -> category for this recipe's canonical ingredients.

    Lets the display list carry an IngredientToken dot without matching running
    on the display copy — categories come from the canonical join, keyed by the
    same normalization `resolve_pantry` uses so display names line up.
    """
    ids = [ri.ingredient_id for ri in recipe.recipe_ingredients]
    if not ids:
        return {}
    cat: dict[str, str] = {}
    for ing in session.execute(
        select(Ingredient).where(Ingredient.id.in_(ids))
    ).scalars():
        cat[normalize(ing.name)] = ing.category
        for alias in ing.aliases or []:
            cat.setdefault(normalize(alias), ing.category)
    return cat


@router.get("/recipes/{recipe_id}", response_model=RecipeDetail)
def get_recipe(
    recipe_id: int, session: Session = Depends(get_session)
) -> RecipeDetail:
    recipe = session.get(
        Recipe, recipe_id, options=[selectinload(Recipe.recipe_ingredients)]
    )
    if recipe is None:
        raise HTTPException(404, "recipe not found")

    cat = _category_map(recipe, session)
    # Prefer the enriched ingredient list (filled measures) once it exists.
    ingredient_items = recipe.ingredients_rich or recipe.ingredients or []
    lines = [
        RecipeIngredientLine(
            name=item.get("name", ""),
            qty=item.get("qty"),
            unit=item.get("unit"),
            essential=item.get("essential", True),
            category=cat.get(normalize(item.get("name", ""))),
        )
        for item in ingredient_items
    ]

    return RecipeDetail(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description or "",
        cuisine=recipe.cuisine,
        region=recipe.region,
        meal_types=recipe.meal_types or [],
        tags=recipe.tags or [],
        diet_labels=recipe.diet_labels or [],
        allergens=recipe.allergens or [],
        time_minutes=recipe.time_minutes,
        servings=recipe.servings,
        nutrition=recipe.nutrition or {},
        nutrition_estimated=recipe.nutrition_estimated,
        ingredients=lines,
        # Prefer the LLM-enriched method when it's been generated.
        steps=recipe.steps_rich or recipe.steps or [],
        steps_enriched=recipe.steps_rich is not None,
        source=recipe.source,
        source_url=recipe.source_url,
        attribution=recipe.attribution,
        image_url=recipe.image_url,
        license_note=recipe.license_note,
    )


@router.post("/recipes/{recipe_id}/enrich", response_model=RecipeEnrichment)
def post_enrich_recipe(
    recipe_id: int, session: Session = Depends(get_session)
) -> RecipeEnrichment:
    """Lazily enrich the method + fill blank measures on first view, then cache
    the result. Idempotent: returns the cache instantly once enriched."""
    return enrich_recipe(session, recipe_id)


@router.post("/recipes/{recipe_id}/modify", response_model=ModifyResponse)
def post_modify_recipe(
    recipe_id: int, req: ModifyRequest, session: Session = Depends(get_session)
) -> ModifyResponse:
    return modify_recipe(session, recipe_id, req)
