"""Saved-recipe endpoint tests. DB-backed; discover ids dynamically."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Recipe, SavedRecipe
from app.tests.conftest import requires_db

client = TestClient(app)


@requires_db
def test_save_list_unsave_roundtrip(session):
    rid = session.execute(select(Recipe.id).limit(1)).scalar_one()
    hdr = {"X-User-Key": "test-saved-user"}
    session.query(SavedRecipe).filter_by(user_key="test-saved-user").delete()
    session.commit()
    try:
        r = client.post("/v1/saved", json={"recipe_id": rid}, headers=hdr)
        assert r.status_code == 200
        assert rid in [x["id"] for x in r.json()["recipes"]]

        # idempotent — saving again doesn't duplicate
        again = client.post("/v1/saved", json={"recipe_id": rid}, headers=hdr)
        assert [x["id"] for x in again.json()["recipes"]].count(rid) == 1

        got = client.get("/v1/saved", headers=hdr).json()["recipes"]
        assert [x["id"] for x in got] == [rid]

        client.delete(f"/v1/saved/{rid}", headers=hdr)
        assert client.get("/v1/saved", headers=hdr).json()["recipes"] == []
    finally:
        session.query(SavedRecipe).filter_by(user_key="test-saved-user").delete()
        session.commit()


@requires_db
def test_saved_isolated_per_user(session):
    rid = session.execute(select(Recipe.id).limit(1)).scalar_one()
    a, b = {"X-User-Key": "saved-iso-a"}, {"X-User-Key": "saved-iso-b"}
    try:
        client.post("/v1/saved", json={"recipe_id": rid}, headers=a)
        assert client.get("/v1/saved", headers=b).json()["recipes"] == []
    finally:
        for uk in ("saved-iso-a", "saved-iso-b"):
            session.query(SavedRecipe).filter_by(user_key=uk).delete()
        session.commit()


def test_save_unknown_recipe_404():
    r = client.post(
        "/v1/saved", json={"recipe_id": 999999}, headers={"X-User-Key": "x"}
    )
    assert r.status_code == 404
