"""Deterministic plan validator.

Fail-closed safety net: re-checks the agent's plan against the DATABASE, never
against the model's claims (a model that says "dairy-free" is exactly the failure
mode this guards). Pure Python, no LLM — an LLM validator would reintroduce the
error it's meant to catch. Returns a list of violation dicts (JSON-serializable,
logged to generation_events); empty means the plan is clean.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Recipe
from app.schemas.agent import AgentRequest, MealPlanResponse
from app.services.ingredients import normalize


def validate_plan(
    session: Session, plan: MealPlanResponse, request: AgentRequest
) -> list[dict]:
    violations: list[dict] = []

    if not plan.recipes:
        return [{"type": "empty_plan", "detail": "no recipes recommended"}]

    exclude = set(request.exclude_allergens)
    disliked = {normalize(d) for d in request.disliked_ingredients}
    for item in plan.recipes:
        recipe = session.get(Recipe, item.recipe_id)
        if recipe is None:
            violations.append(
                {"recipe_id": item.recipe_id, "type": "unknown_recipe",
                 "detail": "recipe_id does not exist"}
            )
            continue
        bad = sorted(exclude & set(recipe.allergens))
        if bad:
            violations.append(
                {"recipe_id": item.recipe_id, "type": "allergen",
                 "detail": f"contains excluded allergen(s): {', '.join(bad)}"}
            )
        if request.diet and request.diet not in recipe.diet_labels:
            violations.append(
                {"recipe_id": item.recipe_id, "type": "diet",
                 "detail": f"not {request.diet} (labels: {recipe.diet_labels})"}
            )
        if (
            request.max_time_minutes is not None
            and recipe.time_minutes > request.max_time_minutes
        ):
            violations.append(
                {"recipe_id": item.recipe_id, "type": "time",
                 "detail": f"{recipe.time_minutes} min > {request.max_time_minutes} min"}
            )
        if disliked:
            recipe_names = {normalize(i["name"]) for i in (recipe.ingredients or [])}
            hit = sorted(disliked & recipe_names)
            if hit:
                violations.append(
                    {"recipe_id": item.recipe_id, "type": "disliked",
                     "detail": f"contains disliked ingredient(s): {', '.join(hit)}"}
                )
    return violations
