"""GET /v1/recipes/{id} detail endpoint.

DB-backed. Looks the seed recipe up by title so it never hard-codes an id
(CI seeds only the 144-recipe baseline, where ids aren't stable).
"""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Recipe
from app.tests.conftest import requires_db

client = TestClient(app)


def _seed_recipe_id(session) -> int:
    return session.execute(
        select(Recipe.id).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()


@requires_db
def test_recipe_detail_returns_full_payload(session):
    body = client.get(f"/v1/recipes/{_seed_recipe_id(session)}").json()

    # Fields the list view (RankedRecipe) drops are all present here.
    assert body["title"] == "Tomato Garlic Pasta"
    assert body["steps"] and all(isinstance(s, str) for s in body["steps"])
    assert body["servings"] >= 1
    assert body["source"] == "seed"
    assert body["source_url"] is None  # seed rows carry no provenance url

    # Display lines carry qty/unit/essential + a resolved category dot.
    lines = {i["name"]: i for i in body["ingredients"]}
    assert lines["tomato"]["category"] == "vegetable"
    assert lines["pasta"]["category"] == "grain"
    assert lines["parmesan"]["essential"] is False
    assert lines["pasta"]["qty"] == 200 and lines["pasta"]["unit"] == "g"


@requires_db
def test_recipe_detail_unknown_id_404():
    r = client.get("/v1/recipes/999999999")
    assert r.status_code == 404
