"""Recipe generation: fail-closed validation, fail-open failure, and persistence.

The model is always stubbed — these assert the guards around generation, not
the model's cooking. The guards are the point: a generated recipe reaches users
with the same diet/allergen authority as a curated one, so nothing it claims
about itself may be taken at face value.
"""
import pytest
from sqlalchemy import select

from app.models import GenerationEvent, Ingredient, Recipe, RecipeIngredient
from app.schemas.generation import (
    GeneratedIngredientLine,
    GeneratedRecipe,
    GenerationResult,
    Macros,
    NewIngredient,
)
from app.schemas.recommend import RecommendRequest
from app.services import generation
from app.tests.conftest import requires_db


class _FakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def generate_structured(self, *a, **kw):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _recipe(title, ingredients, **kw):
    return GeneratedRecipe(
        title=title,
        description="",
        time_minutes=kw.pop("time_minutes", 30),
        servings=kw.pop("servings", 2),
        ingredients=[
            GeneratedIngredientLine(name=n, qty=q, unit=u, essential=True)
            for n, q, u in ingredients
        ],
        steps=["Cook it."],
        **kw,
    )


def _use(monkeypatch, result):
    fake = _FakeLLM(result)
    monkeypatch.setattr(generation, "get_llm", lambda: fake)
    monkeypatch.setattr(generation, "is_enabled", lambda: True)
    return fake


def _titles(session):
    return set(session.execute(select(Recipe.title)).scalars())


# --------------------------------------------------------------------------- #
# Ingredient plausibility
# --------------------------------------------------------------------------- #
def _ingredient(**kw):
    base = dict(
        name="fish sauce", category="sauce", aliases=[], vegetarian=False, vegan=False,
        allergens=["fish"],
        per_100g=Macros(calories=35, protein_g=5.0, carbs_g=3.6, fat_g=0.0),
        default_unit="tbsp", grams_per_piece=18,
    )
    base.update(kw)
    return NewIngredient(**base)


def test_a_plausible_ingredient_is_accepted():
    assert generation._ingredient_is_plausible(_ingredient()) is None


@pytest.mark.parametrize(
    "kw, expect",
    [
        ({"per_100g": Macros(calories=5000, protein_g=1, carbs_g=1, fat_g=1)}, "kcal"),
        ({"per_100g": Macros(calories=400, protein_g=500, carbs_g=0, fat_g=0)}, "macro"),
        # Internally inconsistent: the macros imply ~800 kcal, not 100.
        ({"per_100g": Macros(calories=100, protein_g=50, carbs_g=50, fat_g=40)}, "imply"),
        ({"category": "invented"}, "category"),
        ({"default_unit": "handful"}, "unit"),
        ({"allergens": ["gluten", "unicorn"]}, "off-vocab"),
        ({"vegan": True, "vegetarian": False}, "vegetarian"),
    ],
)
def test_implausible_ingredients_are_rejected(kw, expect):
    # A hallucinated per_100g becomes the basis for the nutrition of every
    # recipe that later uses the ingredient, so this has to be strict.
    why = generation._ingredient_is_plausible(_ingredient(**kw))
    assert why and expect in why


# --------------------------------------------------------------------------- #
# Fail-closed
# --------------------------------------------------------------------------- #
@requires_db
def test_a_recipe_whose_derived_labels_violate_the_request_is_discarded(session, monkeypatch):
    # The model labels nothing here — it just returns paneer in a vegan request.
    # classify_and_derive sees dairy, so the recipe must never be stored.
    _use(monkeypatch, GenerationResult(
        recipes=[_recipe("Test Fake Vegan Paneer", [("paneer", 200, "g"), ("rice", 1, "cup")])],
        new_ingredients=[],
    ))
    req = RecommendRequest(diet="vegan", limit=5)
    before = _titles(session)
    ids = generation.generate_recipes(session, req, [], user_key="test")

    assert ids == [], "a diet-violating recipe must not be persisted"
    assert "Test Fake Vegan Paneer" not in _titles(session) - before
    event = session.execute(
        select(GenerationEvent).order_by(GenerationEvent.id.desc())
    ).scalars().first()
    assert any("vegan" in v.get("detail", "") for v in event.violations), event.violations


@requires_db
def test_an_excluded_allergen_is_caught_from_the_ingredients(session, monkeypatch):
    _use(monkeypatch, GenerationResult(
        recipes=[_recipe("Test Peanut Dish", [("peanuts", 100, "g"), ("rice", 1, "cup")])],
        new_ingredients=[],
    ))
    req = RecommendRequest(exclude_allergens=["peanuts"], limit=5)
    assert generation.generate_recipes(session, req, [], user_key="test") == []


# --------------------------------------------------------------------------- #
# Fail-open
# --------------------------------------------------------------------------- #
@requires_db
def test_generation_disabled_returns_nothing_and_does_not_raise(session, monkeypatch):
    monkeypatch.setattr(generation, "is_enabled", lambda: False)
    assert generation.generate_recipes(session, RecommendRequest(limit=5), []) == []


@requires_db
def test_an_llm_error_degrades_instead_of_raising(session, monkeypatch):
    from app.llm.client import LLMError

    _use(monkeypatch, LLMError("upstream exploded"))
    assert generation.generate_recipes(session, RecommendRequest(limit=5), []) == []
    event = session.execute(
        select(GenerationEvent).order_by(GenerationEvent.id.desc())
    ).scalars().first()
    assert event.degraded is True


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
@requires_db
def test_a_clean_recipe_is_stored_with_derived_labels_and_learned_ingredients(
    session, monkeypatch
):
    _use(monkeypatch, GenerationResult(
        recipes=[_recipe(
            "Test Generated Tofu Bowl",
            [("tofu", 200, "g"), ("rice", 1, "cup"), ("test-yuzu-kosho", 1, "tbsp")],
            cuisine="korean",  # deliberately the model's word, not a taxonomy id
        )],
        new_ingredients=[_ingredient(
            name="test-yuzu-kosho", category="sauce", vegetarian=True, vegan=True,
            allergens=[], per_100g=Macros(calories=60, protein_g=2, carbs_g=12, fat_g=0.5),
        )],
    ))
    req = RecommendRequest(diet="vegan", cuisines=["asian/korean"], limit=5)
    ids = generation.generate_recipes(session, req, [], user_key="test")
    try:
        assert ids, "a compliant recipe should be persisted"
        recipe = session.get(Recipe, ids[0])
        assert "vegan" in recipe.diet_labels, "labels are derived, not copied"
        assert recipe.source == "generated" and recipe.nutrition_estimated
        assert recipe.embedding is not None, "must be embedded to be retrievable"
        # The request's taxonomy id wins over the model's own label, or the
        # recipe is unmatchable by the very filter that asked for it.
        assert (recipe.cuisine, recipe.region) == ("asian", "korean")
        assert session.execute(
            select(Ingredient).where(Ingredient.name == "test-yuzu-kosho")
        ).scalar_one().per_100g["calories"] == 60
    finally:
        session.execute(
            Recipe.__table__.delete().where(Recipe.id.in_(ids))
        )
        session.execute(
            Ingredient.__table__.delete().where(Ingredient.name == "test-yuzu-kosho")
        )
        session.commit()


# --------------------------------------------------------------------------- #
# Endpoint behaviour after a successful generation
# --------------------------------------------------------------------------- #
def _endpoint(monkeypatch, cuisine, generated, in_cuisine=None):
    """POST /v1/recommendations with generation stubbed to a known outcome.

    Patches the endpoint's OWN bound names: recommendations.py does
    `from app.services.cache import get_cached`, so patching the cache module
    leaves its reference untouched and the assertion reads a cached response.
    """
    from fastapi.testclient import TestClient

    from app.api import recommendations
    from app.main import app

    monkeypatch.setattr(recommendations, "get_cached", lambda k: None)
    monkeypatch.setattr(recommendations, "set_cached", lambda k, v: None)
    monkeypatch.setattr(recommendations, "can_generate", lambda session: True)
    monkeypatch.setattr(
        recommendations, "generate_recipes",
        lambda session, req, pantry, user_key: generated,
    )
    if in_cuisine is not None:
        monkeypatch.setattr(recommendations, "OFF_CUISINE_FLOOR", in_cuisine)
    return TestClient(app).post(
        "/v1/recommendations",
        json={"pantry": ["rice"], "cuisines": [cuisine], "limit": 10},
    ).json()


# african/ethiopian has no recipes at all, so the padding path genuinely fires
# here — with a cuisine the corpus can serve, this assertion passes vacuously.
_EMPTY_CUISINE = "african/ethiopian"


@requires_db
def test_off_cuisine_padding_still_applies_when_generation_produced_nothing(monkeypatch):
    body = _endpoint(monkeypatch, _EMPTY_CUISINE, generated=[])
    assert body["mode"] == "off_cuisine"
    assert body["results"] and all(not r["cuisine_matched"] for r in body["results"])
    assert body["explanation"]


@requires_db
def test_off_cuisine_padding_is_skipped_when_generation_succeeded(session, monkeypatch):
    # Writing recipes in the requested cuisine and then appending other cuisines
    # under "we don't have many X recipes yet" contradicts what just happened.
    # The stub has to actually leave a retrievable recipe behind: reporting
    # success while surfacing nothing must still fall through to the divider,
    # so a bare [id] would exercise the wrong branch.
    rice = session.execute(select(Ingredient).where(Ingredient.name == "rice")).scalar_one()
    recipe = Recipe(
        title="Test Ethiopian Shiro Wat", description="", ingredients=[{"name": "rice"}],
        steps=["Cook."], tags=[], diet_labels=["vegan", "vegetarian"], allergens=[],
        cuisine="african", region="ethiopian", meal_types=["dinner"], time_minutes=30,
        servings=2, nutrition={"calories": 400, "protein_g": 12, "carbs_g": 60, "fat_g": 8},
        search_text="test ethiopian shiro wat rice", embedding=[0.0] * 384,
        source="generated", nutrition_estimated=True,
    )
    session.add(recipe)
    session.flush()
    session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=rice.id, essential=True))
    session.commit()
    try:
        body = _endpoint(monkeypatch, _EMPTY_CUISINE, generated=[recipe.id])
        assert body["mode"] != "off_cuisine"
        assert body["results"], "the generated recipe should surface"
        assert all(r["cuisine_matched"] for r in body["results"])
    finally:
        session.execute(RecipeIngredient.__table__.delete().where(
            RecipeIngredient.recipe_id == recipe.id))
        session.execute(Recipe.__table__.delete().where(Recipe.id == recipe.id))
        session.commit()
