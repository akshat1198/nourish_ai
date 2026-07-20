"""Stage 7.3b — POST /v1/recipes/{id}/modify deterministic core.

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
def test_modify_no_substitution_422(session):
    # tomato and rice are both real, but there's no tomato->rice substitution.
    r = client.post(
        f"/v1/recipes/{_pasta_id(session)}/modify",
        json={"from_ingredient": "tomato", "to_ingredient": "rice"},
    )
    assert r.status_code == 422


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
