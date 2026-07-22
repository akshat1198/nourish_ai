"""Deterministic tool registry (LLM-03).

Five typed tools the Stage-3 agent can call. Each is a plain function of
(session, input_dict) returning JSON-serializable output — NO tool calls the
LLM (that would defeat the point). The same registry is:

  * dispatched by the raw agent loop (Stage 3.2),
  * called directly in tests,
  * exposed over MCP (Stage 4.1),

so there is exactly one implementation of each capability. `anthropic_tools()`
renders the registry into the tool-definition list the Messages API expects
(strict + additionalProperties:false so tool inputs validate exactly).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ingredient, Recipe, Substitution
from app.services.embedder import get_embedder
from app.services.ingredients import resolve_pantry
from app.services.pantry import get_pantry
from app.services.plans import add_item, create_plan
from app.services.ranking import annotate
from app.services.retrieval import fetch_hybrid
from app.services.shopping import build_shopping_list as _build_shopping_list


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    fn: Callable[[Session, dict], object]


def _id_to_name(session: Session) -> dict[int, str]:
    return {i.id: i.name for i in session.execute(select(Ingredient)).scalars()}


# --------------------------------------------------------------------------- #
# search_recipes
# --------------------------------------------------------------------------- #
def _search_recipes(session: Session, inp: dict) -> dict:
    pantry = inp.get("pantry", [])
    resolved = resolve_pantry(session, pantry)
    query_str = " ".join(pantry)
    query_vec = get_embedder().embed([query_str])[0] if query_str.strip() else []
    candidates = fetch_hybrid(
        session,
        resolved.ingredient_ids,
        query_vec,
        diet=inp.get("diet"),
        exclude_allergens=inp.get("exclude_allergens", []),
        max_time=inp.get("max_time_minutes"),
        limit=50,
    )
    ranked = annotate(candidates, limit=inp.get("limit", 5))
    # Trim to a compact shape for the model's context.
    results = [
        {
            "id": r.id,
            "title": r.title,
            "time_minutes": r.time_minutes,
            "diet_labels": r.diet_labels,
            "allergens": r.allergens,
            "matched_ingredients": r.matched_ingredients,
            "missing_ingredients": r.missing_ingredients,
            "why": r.why,
        }
        for r in ranked
    ]
    return {"results": results, "unmatched_pantry": resolved.unmatched}


# --------------------------------------------------------------------------- #
# check_allergens
# --------------------------------------------------------------------------- #
def _check_allergens(session: Session, inp: dict) -> dict:
    recipe = session.get(Recipe, inp["recipe_id"])
    if recipe is None:
        return {"recipe_id": inp["recipe_id"], "error": "recipe not found"}
    violations = sorted(set(inp.get("allergens", [])) & set(recipe.allergens))
    return {
        "recipe_id": recipe.id,
        "title": recipe.title,
        "recipe_allergens": recipe.allergens,
        "violations": violations,
        "safe": not violations,
    }


# --------------------------------------------------------------------------- #
# find_substitutions  (also POST /v1/substitutions — API-02)
# --------------------------------------------------------------------------- #
def _find_substitutions(session: Session, inp: dict) -> dict:
    name = inp["ingredient"]
    resolved = resolve_pantry(session, [name])
    if not resolved.ingredient_ids:
        return {"ingredient": name, "substitutes": [], "note": "unknown ingredient"}
    ing_id = resolved.ingredient_ids[0]
    diet = inp.get("diet")
    id_to_name = _id_to_name(session)

    subs = session.execute(
        select(Substitution).where(Substitution.ingredient_id == ing_id)
    ).scalars()
    out = []
    for s in subs:
        if diet and diet not in (s.diet_ok or []):
            continue  # a diet was requested; only keep swaps that enable it
        out.append(
            {
                "use": id_to_name.get(s.substitute_id, "?"),
                "ratio": s.ratio,
                "confidence": s.confidence,
                "enables_diets": s.diet_ok,
            }
        )
    out.sort(key=lambda x: x["confidence"], reverse=True)
    return {"ingredient": id_to_name.get(ing_id, name), "substitutes": out}


# --------------------------------------------------------------------------- #
# estimate_nutrition
# --------------------------------------------------------------------------- #
def _estimate_nutrition(session: Session, inp: dict) -> dict:
    recipe = session.get(Recipe, inp["recipe_id"])
    if recipe is None:
        return {"recipe_id": inp["recipe_id"], "error": "recipe not found"}
    per_serving = recipe.nutrition or {}
    servings = inp.get("servings") or recipe.servings
    total = {k: round(v * servings, 1) for k, v in per_serving.items()}
    return {
        "recipe_id": recipe.id,
        "title": recipe.title,
        "servings": servings,
        "per_serving": per_serving,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# build_shopping_list
# --------------------------------------------------------------------------- #
def _build_shopping_list_tool(session: Session, inp: dict) -> dict:
    resp = _build_shopping_list(session, inp["recipe_ids"], inp.get("pantry", []))
    return resp.model_dump()


# --------------------------------------------------------------------------- #
# check_inventory  (Stage 11 — reads the persistent pantry, Stage 5)
# --------------------------------------------------------------------------- #
def _check_inventory(session: Session, inp: dict) -> dict:
    user_key = inp["user_key"]
    items = get_pantry(session, user_key)  # list[PantryItemOut]
    return {
        "user_key": user_key,
        "pantry": [
            {"ingredient": i.ingredient, "category": i.category, "is_staple": i.is_staple}
            for i in items
        ],
    }


# --------------------------------------------------------------------------- #
# save_meal_plan  (Stage 11 — writes into Stage 10's meal_plans)
# --------------------------------------------------------------------------- #
def _save_meal_plan(session: Session, inp: dict) -> dict:
    user_key = inp["user_key"]
    recipe_ids = inp["recipe_ids"]
    # skip ids that don't exist so add_item's FK never errors
    valid = [rid for rid in recipe_ids if session.get(Recipe, rid) is not None]
    plan = create_plan(session, user_key, inp["name"])
    for rid in valid:
        add_item(session, user_key, plan.id, rid, None)
    return {
        "plan_id": plan.id,
        "name": plan.name,
        "added": len(valid),
        "skipped": [r for r in recipe_ids if r not in valid],
    }


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
TOOLS: dict[str, ToolSpec] = {
    "search_recipes": ToolSpec(
        name="search_recipes",
        description=(
            "Find recipes that best use a pantry. Call this first to get candidate "
            "recipes. Pass the user's on-hand ingredients as `pantry` (bare names). "
            "Optionally constrain by `diet`, `exclude_allergens`, and `max_time_minutes`."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pantry": {"type": "array", "items": {"type": "string"}},
                "diet": {"type": "string"},
                "exclude_allergens": {"type": "array", "items": {"type": "string"}},
                "max_time_minutes": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["pantry"],
            "additionalProperties": False,
        },
        fn=_search_recipes,
    ),
    "check_allergens": ToolSpec(
        name="check_allergens",
        description=(
            "Verify a recipe against allergens to avoid. Call this before recommending "
            "any recipe when the user has allergen restrictions. Returns the recipe's "
            "allergens and any that violate the given list."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "recipe_id": {"type": "integer"},
                "allergens": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["recipe_id", "allergens"],
            "additionalProperties": False,
        },
        fn=_check_allergens,
    ),
    "find_substitutions": ToolSpec(
        name="find_substitutions",
        description=(
            "Find ingredient substitutes for one ingredient, optionally constrained to "
            "swaps that enable a `diet` (e.g. substitutes for 'chicken breast' that make "
            "a recipe 'vegan'). Ranked by confidence."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ingredient": {"type": "string"},
                "diet": {"type": "string"},
            },
            "required": ["ingredient"],
            "additionalProperties": False,
        },
        fn=_find_substitutions,
    ),
    "estimate_nutrition": ToolSpec(
        name="estimate_nutrition",
        description=(
            "Get per-serving and total nutrition (calories, protein_g, carbs_g, fat_g) "
            "for a recipe at a given serving count. Use when the user asks about "
            "nutrition or wants high-protein / low-calorie options."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "recipe_id": {"type": "integer"},
                "servings": {"type": "integer"},
            },
            "required": ["recipe_id"],
            "additionalProperties": False,
        },
        fn=_estimate_nutrition,
    ),
    "build_shopping_list": ToolSpec(
        name="build_shopping_list",
        description=(
            "Aggregate the ingredients the user needs to buy for the chosen recipes, "
            "excluding what's already in `pantry`. Call this last, once recipes are picked."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "recipe_ids": {"type": "array", "items": {"type": "integer"}},
                "pantry": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["recipe_ids"],
            "additionalProperties": False,
        },
        fn=_build_shopping_list_tool,
    ),
    "check_inventory": ToolSpec(
        name="check_inventory",
        description=(
            "Return the user's saved pantry (on-hand + staples). Call to see what "
            "they already have before suggesting a shopping list."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_key": {"type": "string"},
            },
            "required": ["user_key"],
            "additionalProperties": False,
        },
        fn=_check_inventory,
    ),
    "save_meal_plan": ToolSpec(
        name="save_meal_plan",
        description=(
            "Persist a named meal plan of recipe ids for the user. Returns the new "
            "plan_id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_key": {"type": "string"},
                "name": {"type": "string"},
                "recipe_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["user_key", "name", "recipe_ids"],
            "additionalProperties": False,
        },
        fn=_save_meal_plan,
    ),
}


def anthropic_tools() -> list[dict]:
    """Render the registry as Messages API tool definitions (strict inputs)."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "strict": True,
        }
        for t in TOOLS.values()
    ]


def call_tool(session: Session, name: str, tool_input: dict) -> object:
    """Dispatch a tool by name. Raises KeyError for unknown tools."""
    return TOOLS[name].fn(session, tool_input)
