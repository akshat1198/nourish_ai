"""POST /v1/recipes/{id}/modify deterministic core.

DB-backed. Uses seed recipes + seed substitutions (both in the CI baseline);
looks the recipe up by title so it never hard-codes an id.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.llm.client import LLMError
from app.main import app
from app.models import Recipe
from app.schemas.llm import ModifiedStep, ModifiedSteps
from app.tests.conftest import requires_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def _llm_off(monkeypatch):
    # Default the LLM OFF so the deterministic-core assertions don't depend on
    # whether an API key is set in the environment. LLM tests re-enable it.
    from app.services import modify

    monkeypatch.setattr(modify, "is_enabled", lambda: False)


def _pasta_id(session) -> int:
    return session.execute(
        select(Recipe.id).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()


@requires_db
def test_modify_swap_removes_allergen(session):
    # pasta (gluten) -> rice noodles (no allergens): the dish loses gluten.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    )
    assert r.status_code == 200
    body = r.json()

    names = [i["name"] for i in body["ingredients"]]
    assert "rice noodles" in names and "pasta" not in names
    assert "gluten" in body["removed_allergens"]
    assert "gluten" not in body["allergens"]
    assert body["added_allergens"] == []
    # Deterministic core: steps untouched, no LLM.
    assert body["llm_used"] is False
    assert body["changed_step_indexes"] == []
    assert body["swap"] == {
        "from_ingredient": "pasta",
        "to_ingredient": "rice noodles",
        "ratio": "1:1",
    }


@requires_db
def test_modify_scales_qty_by_ratio(session):
    # parmesan 30 g -> cheddar at 1:0.75 => 22.5 g.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "parmesan", "to_ingredient": "cheddar"},
    )
    assert r.status_code == 200
    cheddar = next(i for i in r.json()["ingredients"] if i["name"] == "cheddar")
    assert cheddar["qty"] == 22.5


@requires_db
def test_modify_unknown_ingredient_422(session):
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "zzznotreal", "to_ingredient": "tofu"},
    )
    assert r.status_code == 422


@requires_db
def test_modify_arbitrary_canonical_swap_ok(session):
    # Any canonical target is allowed now (not just table rows). tomato->rice
    # has no curated row, so it defaults to 1:1 and is NOT flagged approximate.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "tomato", "to_ingredient": "rice"},
    )
    assert r.status_code == 200
    body = r.json()
    names = [i["name"] for i in body["ingredients"]]
    assert "rice" in names and "tomato" not in names
    assert body["approximate"] is False
    assert body["swap"]["ratio"] == "1:1"


@requires_db
def test_modify_recipe_lacks_ingredient_422(session):
    # chicken breast -> tofu is a real substitution, but the pasta recipe has
    # no chicken breast, so the swap doesn't apply.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "chicken breast", "to_ingredient": "tofu"},
    )
    assert r.status_code == 422


@requires_db
def test_modify_estimates_nutrition_delta(session):
    # rice noodles (109 kcal/100g) are lighter than pasta (157) -> calories drop.
    from app.services.modify import NUTRITION_WARNING

    pasta_id = _pasta_id(session)
    original = client.get(f"/v1/recipes/{pasta_id}").json()["nutrition"]
    body = client.post(
        f"/v1/recipes/{pasta_id}/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    ).json()

    assert body["nutrition"]  # a post-swap estimate is present
    assert body["nutrition_delta"]["calories"] < 0
    assert body["nutrition"]["calories"] < original["calories"]
    assert NUTRITION_WARNING not in body["warnings"]  # real estimate -> no caveat


@requires_db
def test_modify_unknown_recipe_404(session):
    r = client.post(
        "/v1/recipes/999999999/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    )
    assert r.status_code == 404


# --- LLM step rewrite (7.3c), mocked -------------------------------------- #
@requires_db
def test_modify_llm_rewrites_steps(session, monkeypatch):
    from app.services import modify

    monkeypatch.setattr(modify, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = ModifiedSteps(
        steps=[ModifiedStep(index=0, text="Cook the rice noodles until just tender.")],
        knock_on_flags=["Rice noodles cook faster than pasta — watch closely."],
        notes="",
    )
    monkeypatch.setattr(modify, "get_llm", lambda: fake)

    body = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    ).json()

    assert body["llm_used"] is True
    assert body["changed_step_indexes"] == [0]
    assert body["steps"][0] == "Cook the rice noodles until just tender."
    assert body["knock_on_flags"]


@requires_db
def test_modify_llm_error_degrades_to_original_steps(session, monkeypatch):
    from app.services import modify

    monkeypatch.setattr(modify, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.side_effect = LLMError("model down")
    monkeypatch.setattr(modify, "get_llm", lambda: fake)

    pasta_id = _pasta_id(session)
    original = client.get(f"/v1/recipes/{pasta_id}").json()["steps"]
    body = client.post(
        f"/v1/recipes/{pasta_id}/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    ).json()

    assert body["llm_used"] is False
    assert body["changed_step_indexes"] == []
    assert body["steps"] == original  # degraded: original method, still a 200
    assert any("couldn't be adjusted" in w.lower() for w in body["warnings"])


@requires_db
def test_modify_llm_disabled_warns(session):
    # _llm_off fixture leaves the LLM disabled.
    body = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    ).json()
    assert body["llm_used"] is False
    assert any("isn't configured" in w for w in body["warnings"])


# --- Free-text (out-of-vocabulary) swaps + LLM suggestions ------------ #
@requires_db
def test_modify_freetext_swap_needs_llm(session):
    # _llm_off: a target we don't know can't be adapted without the assistant.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "parmesan", "to_ingredient": "nutritional yeast"},
    )
    assert r.status_code == 422


@requires_db
def test_modify_freetext_swap_llm_estimates(session, monkeypatch):
    from app.schemas.llm import FreeSwapAdaptation, MacroDelta, ModifiedStep
    from app.services import modify

    monkeypatch.setattr(modify, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = FreeSwapAdaptation(
        ratio="1:1",
        changed_steps=[ModifiedStep(index=0, text="Use nutritional yeast for a cheesy, dairy-free finish.")],
        knock_on_flags=["Less melt than cheese."],
        added_allergens=[],
        removed_allergens=["dairy"],
        enables_diets=["vegan"],
        breaks_diets=[],
        nutrition_delta=MacroDelta(calories=-40, protein_g=2, carbs_g=1, fat_g=-6),
        note="Nutritional yeast stands in for parmesan.",
    )
    monkeypatch.setattr(modify, "get_llm", lambda: fake)

    body = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "parmesan", "to_ingredient": "nutritional yeast"},
    ).json()

    names = [i["name"] for i in body["ingredients"]]
    assert "nutritional yeast" in names and "parmesan" not in names
    assert body["approximate"] is True
    assert body["llm_used"] is True
    assert "dairy" in body["removed_allergens"]
    assert any("approximate" in w.lower() for w in body["warnings"])


# --- Remove-ingredient adaptation ------------------------------------- #
@requires_db
def test_modify_remove_needs_llm(session):
    # _llm_off: can't adapt a removal without the assistant.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"op": "remove", "from_ingredient": "parmesan"},
    )
    assert r.status_code == 422


@requires_db
def test_modify_remove_omit(session, monkeypatch):
    # LLM only decides omit + rewrites a step; allergens/diet/nutrition are derived
    # in code, so removing the recipe's only dairy (parmesan) drops the dairy label.
    from app.schemas.llm import ModifiedStep, RemovalPlan
    from app.services import modify

    monkeypatch.setattr(modify, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = RemovalPlan(
        strategy="omit",
        changed_steps=[ModifiedStep(index=0, text="Cook the pasta and toss with the garlic oil.")],
        knock_on_flags=["Less savoury depth without the cheese."],
        note="Left out the parmesan — finish with a pinch of salt for savouriness.",
    )
    monkeypatch.setattr(modify, "get_llm", lambda: fake)

    body = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"op": "remove", "from_ingredient": "parmesan"},
    ).json()

    names = [i["name"] for i in body["ingredients"]]
    assert "parmesan" not in names  # the line is gone
    assert body["operation"] == "remove"
    assert body["note"] and body["changed_step_indexes"] == [0]
    assert "dairy" in body["removed_allergens"]  # deterministic re-derivation
    assert body["approximate"] is False  # omit is derived from our own data


@requires_db
def test_modify_remove_substitute_freetext(session, monkeypatch):
    # Substitute to something outside our vocab -> flagged approximate.
    from app.schemas.llm import ModifiedStep, RemovalPlan
    from app.services import modify

    monkeypatch.setattr(modify, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = RemovalPlan(
        strategy="substitute",
        substitute="nutritional yeast",
        ratio="1:0.5",
        changed_steps=[ModifiedStep(index=0, text="Finish with nutritional yeast for a cheesy note.")],
        note="Used nutritional yeast instead of parmesan.",
    )
    monkeypatch.setattr(modify, "get_llm", lambda: fake)

    body = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"op": "remove", "from_ingredient": "parmesan"},
    ).json()

    names = [i["name"] for i in body["ingredients"]]
    assert "nutritional yeast" in names and "parmesan" not in names
    assert body["operation"] == "remove"
    assert body["swap"]["to_ingredient"] == "nutritional yeast"
    assert body["approximate"] is True


# --- Lazy enrichment on view + cache ---------------------------------- #
@requires_db
def test_enrich_caches_and_flags(session, monkeypatch):
    from app.schemas.llm import EnrichedRecipe
    from app.services import enrich

    r = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    orig_rich, orig_ing = r.steps_rich, r.ingredients_rich
    r.steps_rich, r.ingredients_rich = None, None
    session.commit()

    monkeypatch.setattr(enrich, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = EnrichedRecipe(
        steps=[f"Enriched: {s}" for s in r.steps], quantities=[]
    )
    monkeypatch.setattr(enrich, "get_llm", lambda: fake)
    try:
        body = client.post(f"/v1/recipes/{r.id}/enrich").json()
        assert body["enriched"] is True
        assert body["steps"][0].startswith("Enriched:")

        # Cached: a second call serves it without hitting the LLM again.
        fake.generate_structured.reset_mock()
        client.post(f"/v1/recipes/{r.id}/enrich")
        fake.generate_structured.assert_not_called()

        # GET now flags enriched and serves the rich method.
        detail = client.get(f"/v1/recipes/{r.id}").json()
        assert detail["steps_enriched"] is True
        assert detail["steps"][0].startswith("Enriched:")
    finally:
        session.rollback()
        row = session.get(Recipe, r.id)
        row.steps_rich, row.ingredients_rich = orig_rich, orig_ing
        session.commit()


@requires_db
def test_enrich_disabled_returns_original_unstored(session, monkeypatch):
    from app.services import enrich

    r = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    orig_rich = r.steps_rich
    r.steps_rich, r.ingredients_rich = None, None
    session.commit()

    monkeypatch.setattr(enrich, "is_enabled", lambda: False)
    try:
        body = client.post(f"/v1/recipes/{r.id}/enrich").json()
        assert body["enriched"] is False
        assert body["steps"] == r.steps
        session.rollback()
        assert session.get(Recipe, r.id).steps_rich is None  # nothing stored
    finally:
        session.rollback()
        row = session.get(Recipe, r.id)
        row.steps_rich = orig_rich
        session.commit()


@requires_db
def test_recipe_detail_prefers_steps_rich(session):
    r = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    original = r.steps_rich
    r.steps_rich = ["Finely dice the onion.", "Sauté until golden, about 5 minutes."]
    session.commit()
    try:
        steps = client.get(f"/v1/recipes/{r.id}").json()["steps"]
        assert steps == ["Finely dice the onion.", "Sauté until golden, about 5 minutes."]
    finally:
        r.steps_rich = original
        session.commit()


@requires_db
def test_modify_swap_from_noncanonical_display_name(session, monkeypatch):
    # Recipes can carry source-worded display lines ("cheese", "oil") that don't
    # map to our vocabulary. Swapping FROM one must work (via the LLM path), not
    # 422 with "unknown ingredient".
    from app.schemas.llm import FreeSwapAdaptation
    from app.services import modify

    r = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    orig = r.ingredients
    r.ingredients = list(orig) + [{"name": "cheese", "qty": None, "unit": "", "essential": True}]
    session.commit()

    monkeypatch.setattr(modify, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = FreeSwapAdaptation(
        ratio="1:1", changed_steps=[], knock_on_flags=[], added_allergens=["dairy"],
        removed_allergens=[], enables_diets=[], breaks_diets=[], nutrition_delta=None, note="",
    )
    monkeypatch.setattr(modify, "get_llm", lambda: fake)
    try:
        resp = client.post(
            f"/v1/recipes/{r.id}/modify",
            json={"op": "swap", "from_ingredient": "cheese", "to_ingredient": "paneer"},
        )
        assert resp.status_code == 200
        body = resp.json()
        names = [i["name"] for i in body["ingredients"]]
        assert "paneer" in names and "cheese" not in names
        assert body["approximate"] is True
    finally:
        session.rollback()
        row = session.get(Recipe, r.id)
        row.ingredients = orig
        session.commit()


@requires_db
def test_substitutions_merges_llm_suggestions(monkeypatch):
    from app.api import substitutions as subs_api
    from app.schemas.llm import SuggestedSwap, SuggestedSwaps

    monkeypatch.setattr(subs_api, "is_enabled", lambda: True)
    fake = MagicMock()
    fake.generate_structured.return_value = SuggestedSwaps(
        substitutes=[SuggestedSwap(use="dahi", ratio="1:1", note="tangy Indian yogurt", enables_diets=[])]
    )
    monkeypatch.setattr(subs_api, "get_llm", lambda: fake)

    body = client.post("/v1/substitutions", json={"ingredient": "greek yogurt"}).json()
    suggested = [s for s in body["substitutes"] if s.get("source") == "suggested"]
    assert any(s["use"] == "dahi" for s in suggested)
