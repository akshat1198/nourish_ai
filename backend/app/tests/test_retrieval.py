"""Retrieval + ingredient-normalization tests."""
from app.services.ingredients import normalize, resolve_pantry
from app.services.retrieval import fetch_candidates
from app.tests.conftest import requires_db


def test_normalize_singularizes_and_lowercases():
    assert normalize("Tomatoes") == "tomato"
    assert normalize("  Cherry   Tomatoes ") == "cherry tomato"
    assert normalize("Garlic Cloves") == "garlic clove"


@requires_db
def test_resolve_pantry_matches_aliases_and_reports_unknown(session):
    resolved = resolve_pantry(
        session, ["capsicum", "green onions", "definitely-not-food"]
    )
    matched = set(resolved.matched_names.values())
    assert "bell pepper" in matched  # capsicum alias
    assert "scallion" in matched  # green onion alias
    assert resolved.unmatched == ["definitely-not-food"]


@requires_db
def test_pantry_surfaces_expected_recipe(session):
    resolved = resolve_pantry(session, ["pasta", "tomato", "garlic", "olive oil"])
    results = fetch_candidates(session, resolved.ingredient_ids, limit=10)
    titles = [c.title for c in results]
    assert "Tomato Garlic Pasta" in titles
    top = next(c for c in results if c.title == "Tomato Garlic Pasta")
    assert "pasta" in top.matched_ingredients
    assert top.matched_essential >= 3


@requires_db
def test_diet_filter_excludes_non_vegan(session):
    resolved = resolve_pantry(session, ["rice", "soy sauce", "garlic", "tofu", "broccoli"])
    results = fetch_candidates(session, resolved.ingredient_ids, diet="vegan", limit=20)
    assert results, "expected some vegan matches"
    assert all("vegan" in c.diet_labels for c in results)


@requires_db
def test_allergen_exclusion(session):
    resolved = resolve_pantry(session, ["pasta", "tomato", "garlic", "parmesan"])
    results = fetch_candidates(
        session, resolved.ingredient_ids, exclude_allergens=["dairy"], limit=20
    )
    assert all("dairy" not in c.allergens for c in results)


@requires_db
def test_unknown_pantry_degrades_gracefully(session):
    # No exception; simply no matches from a nonsense pantry.
    resolved = resolve_pantry(session, ["xyzzy", "florble"])
    assert resolved.ingredient_ids == []
    results = fetch_candidates(session, resolved.ingredient_ids)
    assert results == []
