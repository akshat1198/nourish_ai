"""Stage 7.3b — POST /v1/recipes/{id}/modify deterministic core.

DB-backed. Uses seed recipes + seed substitutions (both in the CI baseline);
looks the recipe up by title so it never hard-codes an id.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Recipe
from app.tests.conftest import requires_db

client = TestClient(app)


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
def test_modify_unknown_recipe_404(session):
    r = client.post(
        "/v1/recipes/999999999/modify",
        json={"from_ingredient": "pasta", "to_ingredient": "rice noodles"},
    )
    assert r.status_code == 404
