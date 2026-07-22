"""Meal-plan endpoint tests. DB-backed; discover ids dynamically."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import MealPlan, Recipe
from app.tests.conftest import requires_db

client = TestClient(app)


@requires_db
def test_plan_crud_add_items_and_combined_shopping_list(session):
    rids = list(session.execute(select(Recipe.id).limit(3)).scalars())
    hdr = {"X-User-Key": "test-plan-user"}
    session.query(MealPlan).filter_by(user_key="test-plan-user").delete()
    session.commit()
    try:
        plan = client.post("/v1/plans", json={"name": "Week 1"}, headers=hdr).json()
        pid = plan["id"]
        assert plan["name"] == "Week 1" and plan["items"] == []

        for i, rid in enumerate(rids):
            resp = client.post(
                f"/v1/plans/{pid}/items",
                json={"recipe_id": rid, "slot": f"day {i}"},
                headers=hdr,
            )
            assert resp.status_code == 200
        detail = client.get(f"/v1/plans/{pid}", headers=hdr).json()
        assert {it["recipe"]["id"] for it in detail["items"]} == set(rids)

        # re-adding updates the slot, doesn't duplicate
        client.post(
            f"/v1/plans/{pid}/items",
            json={"recipe_id": rids[0], "slot": "moved"},
            headers=hdr,
        )
        detail = client.get(f"/v1/plans/{pid}", headers=hdr).json()
        assert len(detail["items"]) == len(rids)
        assert any(it["slot"] == "moved" for it in detail["items"])

        # combined shopping list aggregates across the plan's recipes
        sl = client.get(f"/v1/plans/{pid}/shopping-list", headers=hdr)
        assert sl.status_code == 200
        assert len(sl.json()["items"]) > 0

        # plan list shows the item count
        plans = client.get("/v1/plans", headers=hdr).json()["plans"]
        assert next(p for p in plans if p["id"] == pid)["item_count"] == len(rids)

        # remove an item, then the whole plan
        client.delete(f"/v1/plans/{pid}/items/{rids[0]}", headers=hdr)
        assert (
            len(client.get(f"/v1/plans/{pid}", headers=hdr).json()["items"])
            == len(rids) - 1
        )
        assert client.delete(f"/v1/plans/{pid}", headers=hdr).status_code == 200
        assert client.get(f"/v1/plans/{pid}", headers=hdr).status_code == 404
    finally:
        session.query(MealPlan).filter_by(user_key="test-plan-user").delete()
        session.commit()


@requires_db
def test_plan_isolated_per_user(session):
    hdr_a, hdr_b = {"X-User-Key": "plan-iso-a"}, {"X-User-Key": "plan-iso-b"}
    try:
        pid = client.post("/v1/plans", json={"name": "mine"}, headers=hdr_a).json()["id"]
        # b can't see or fetch a's plan
        assert client.get("/v1/plans", headers=hdr_b).json()["plans"] == []
        assert client.get(f"/v1/plans/{pid}", headers=hdr_b).status_code == 404
    finally:
        for uk in ("plan-iso-a", "plan-iso-b"):
            session.query(MealPlan).filter_by(user_key=uk).delete()
        session.commit()


def test_plan_not_found_404():
    r = client.get("/v1/plans/999999", headers={"X-User-Key": "x"})
    assert r.status_code == 404
