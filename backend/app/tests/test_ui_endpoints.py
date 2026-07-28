"""UI endpoint tests — pantry CRUD, ingredient autocomplete, new filters.

DB-backed (require the seeded corpus + migration 0007 applied). Auth stays in
disabled mode (default), so identity is the X-User-Key header.
"""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.services.ingredients import resolve_pantry
from app.tests.conftest import requires_db

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Pantry
# --------------------------------------------------------------------------- #
@requires_db
def test_pantry_put_get_roundtrip_and_staples():
    hdr = {"X-User-Key": "test-pantry-user"}
    try:
        r = client.put(
            "/v1/pantry",
            json={"items": [
                {"ingredient": "tomato", "is_staple": True},
                {"ingredient": "garlic", "is_staple": False},
            ]},
            headers=hdr,
        )
        assert r.status_code == 200
        items = {i["ingredient"]: i["is_staple"] for i in r.json()["items"]}
        assert items.get("tomato") is True and items.get("garlic") is False

        got = client.get("/v1/pantry", headers=hdr).json()["items"]
        assert {i["ingredient"] for i in got} == {"tomato", "garlic"}
    finally:
        client.put("/v1/pantry", json={"items": []}, headers=hdr)


@requires_db
def test_pantry_put_replaces_whole_set():
    hdr = {"X-User-Key": "test-pantry-replace"}
    try:
        client.put("/v1/pantry", json={"items": [{"ingredient": "tomato"}]}, headers=hdr)
        r = client.put("/v1/pantry", json={"items": [{"ingredient": "garlic"}]}, headers=hdr)
        names = {i["ingredient"] for i in r.json()["items"]}
        assert names == {"garlic"}  # tomato is gone (whole-set replace)
    finally:
        client.put("/v1/pantry", json={"items": []}, headers=hdr)


@requires_db
def test_pantry_reports_unmatched():
    hdr = {"X-User-Key": "test-pantry-unmatched"}
    try:
        r = client.put(
            "/v1/pantry",
            json={"items": [{"ingredient": "tomato"}, {"ingredient": "zzznotreal"}]},
            headers=hdr,
        )
        body = r.json()
        assert "zzznotreal" in body["unmatched"]
        assert {i["ingredient"] for i in body["items"]} == {"tomato"}
    finally:
        client.put("/v1/pantry", json={"items": []}, headers=hdr)


@requires_db
def test_pantry_isolated_per_user():
    a, b = {"X-User-Key": "iso-a"}, {"X-User-Key": "iso-b"}
    try:
        client.put("/v1/pantry", json={"items": [{"ingredient": "tomato"}]}, headers=a)
        assert client.get("/v1/pantry", headers=b).json()["items"] == []
    finally:
        client.put("/v1/pantry", json={"items": []}, headers=a)


# --------------------------------------------------------------------------- #
# Ingredient autocomplete
# --------------------------------------------------------------------------- #
@requires_db
def test_ingredients_autocomplete_prefix():
    names = [s["name"] for s in client.get("/v1/ingredients", params={"q": "tom"}).json()]
    assert any("tomato" in n for n in names)


@requires_db
def test_ingredients_empty_query_returns_some():
    assert len(client.get("/v1/ingredients").json()) > 0


# --------------------------------------------------------------------------- #
# New recommendation filters
# --------------------------------------------------------------------------- #
@requires_db
def test_recommendations_cuisine_filter_only_italian():
    r = client.post(
        "/v1/recommendations",
        json={"pantry": ["pasta", "tomato", "garlic", "olive oil"],
              "cuisines": ["italian"], "limit": 10},
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results  # italian recipes exist in the seed
    assert all(rec["cuisine"] == "italian" for rec in results)


@requires_db
def test_recommendations_high_protein_goal():
    r = client.post(
        "/v1/recommendations",
        json={"pantry": ["chicken breast", "rice", "broccoli"],
              "nutrition_goals": ["high_protein"], "limit": 10},
    )
    results = r.json()["results"]
    assert all(rec["nutrition"].get("protein_g", 0) >= 25 for rec in results)


def _photo(name: str = "shelf.jpg", data: bytes = b"jpegbytes", mime: str = "image/jpeg"):
    return ("images", (name, data, mime))


@requires_db
def test_pantry_parse_images(monkeypatch):
    # Vision extraction is mocked; the endpoint resolves terms to canonical/generic
    # items and reports what it couldn't place.
    from app.api import pantry as pantry_api

    monkeypatch.setattr(
        pantry_api, "parse_pantry_images",
        lambda images: ["spinach", "eggs", "chicken", "unicorn tears"],
    )
    body = client.post("/v1/pantry/parse-images", files=[_photo(), _photo("fridge.png")]).json()
    recognized = {r["name"]: r for r in body["recognized"]}
    assert {"spinach", "eggs"} <= recognized.keys()
    assert recognized.get("chicken", {}).get("is_group") is True  # generic
    assert "unicorn tears" in body["unmatched"]


@requires_db
def test_pantry_parse_images_fails_open_when_llm_disabled(monkeypatch):
    # No API key: the request still succeeds with nothing recognised, rather
    # than 500ing on a feature the deterministic pantry doesn't depend on.
    from app.api import pantry as pantry_api

    monkeypatch.setattr(pantry_api, "parse_pantry_images", lambda images: [])
    r = client.post("/v1/pantry/parse-images", files=[_photo()])
    assert r.status_code == 200
    assert r.json() == {"recognized": [], "unmatched": []}


def test_pantry_parse_images_rejects_bad_uploads():
    from app.core.config import settings

    over_cap = [_photo(f"{i}.jpg") for i in range(settings.PANTRY_IMAGE_MAX_COUNT + 1)]
    assert client.post("/v1/pantry/parse-images", files=over_cap).status_code == 400

    oversized = _photo(data=b"x" * (settings.PANTRY_IMAGE_MAX_BYTES + 1))
    assert client.post("/v1/pantry/parse-images", files=[oversized]).status_code == 400

    wrong_type = _photo("notes.pdf", b"%PDF-1.4", "application/pdf")
    assert client.post("/v1/pantry/parse-images", files=[wrong_type]).status_code == 400


@requires_db
def test_generic_chicken_expands_to_breast_and_thigh():
    # Picking the generic "chicken" should match recipes using either cut.
    with SessionLocal() as s:
        r = resolve_pantry(s, ["chicken"])
    names = set(r.matched_names.values())
    assert {"chicken breast", "chicken thigh"} <= names
    assert "chicken" not in r.unmatched


@requires_db
def test_autocomplete_offers_generic_group():
    res = client.get("/v1/ingredients", params={"q": "chicken"}).json()
    groups = [x for x in res if x.get("is_group")]
    assert any(x["name"] == "chicken" and x.get("members") for x in groups)


def test_config_exposes_nutrition_thresholds():
    # No DB needed — the UI reads these to label each goal; guard against drift.
    goals = {g["value"]: g["hint"] for g in client.get("/v1/config").json()["nutrition_goals"]}
    assert {"high_protein", "low_calorie", "low_fat", "low_carb"} <= goals.keys()
    assert "25" in goals["high_protein"] and "protein" in goals["high_protein"]
    assert "10" in goals["low_fat"] and "fat" in goals["low_fat"]


@requires_db
def test_recommendations_demote_rather_than_drop_an_unmatchable_soft_filter():
    # A savory pantry with meal_type=dessert matches nothing. A soft filter must
    # never empty the list: the near-misses stay in the pool, ranked below any
    # recipe that does satisfy it, and report filters_matched=0 so the UI can say so.
    r = client.post(
        "/v1/recommendations",
        json={"pantry": ["chicken breast", "onion", "garlic"],
              "meal_type": "dessert", "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"], "a soft filter must never dead-end the list"
    assert all(f["filters_requested"] == 1 for f in body["results"])
    matched = [f["filters_matched"] for f in body["results"]]
    assert matched == sorted(matched, reverse=True), "satisfied filters must rank first"


@requires_db
def test_recommendations_never_silently_swap_the_cuisine():
    # The original bug: ask for Italian, get Indian, because an empty first pass
    # retried with the cuisine dropped. Off-cuisine results may only appear
    # below the in-cuisine ones and must be flagged cuisine_matched=False.
    r = client.post(
        "/v1/recommendations",
        json={"pantry": ["pasta", "tomato", "garlic", "olive oil"],
              "cuisines": ["italian"], "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in {"normal", "off_cuisine", "substitution_first",
                            "shopping_assisted"}
    flags = [f["cuisine_matched"] for f in body["results"]]
    assert flags == sorted(flags, reverse=True), "off-cuisine results must sort last"
    for item in body["results"]:
        if item["cuisine_matched"]:
            assert item["cuisine"] == "italian"
    if body["mode"] == "off_cuisine":
        assert body["explanation"], "an off-cuisine list must say so"


@requires_db
def test_recommendations_never_dead_ends_on_strict_nutrition():
    # Even an near-impossible nutrition combo should never leave a matching pantry
    # with zero suggestions — relaxation surfaces the closest recipes.
    r = client.post(
        "/v1/recommendations",
        json={"pantry": ["chicken breast", "rice", "broccoli", "onion", "garlic"],
              "nutrition_goals": ["high_protein", "low_fat", "low_carb"], "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["results"], "a matching pantry should never dead-end"
    # If the strict goals matched nothing, we relaxed; otherwise a normal match.
    assert body["mode"] in {"normal", "relaxed", "substitution_first", "shopping_assisted"}


@requires_db
def test_recommendations_rejects_unknown_cuisine():
    r = client.post(
        "/v1/recommendations",
        json={"pantry": ["tomato"], "cuisines": ["klingon"], "limit": 5},
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Cuisines
# --------------------------------------------------------------------------- #
@requires_db
def test_cuisines_tree_with_counts():
    tree = client.get("/v1/cuisines").json()
    ids = {n["id"] for n in tree}
    assert {"indian", "asian", "italian"} <= ids
    indian = next(n for n in tree if n["id"] == "indian")
    child_ids = {c["id"] for c in indian["children"]}
    # Regions promoted in 6.4 must be present as nodes…
    assert {"indian/gujarati", "indian/kerala", "indian/karnataka"} <= child_ids
    # …each with a non-negative integer count, and the parent count covering its
    # regions. Absolute regional counts come from the manual Archana's import
    # (not run in CI), so assert the invariant here — not a specific value — and
    # check a live count on a cuisine that IS in the 144-seed baseline (italian).
    for c in indian["children"]:
        assert isinstance(c["count"], int) and c["count"] >= 0
    assert indian["count"] >= sum(c["count"] for c in indian["children"])
    italian = next(n for n in tree if n["id"] == "italian")
    assert italian["count"] > 0
