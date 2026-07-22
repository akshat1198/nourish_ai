"""Shopping-list aggregation and cache-key tests."""
from app.services.cache import recommend_key
from app.services.shopping import build_shopping_list
from app.tests.conftest import requires_db


def test_cache_key_is_order_independent_for_sets():
    a = recommend_key(
        {"pantry": ["tomato", "garlic"], "diet": "vegan", "exclude_allergens": ["nuts"],
         "max_time_minutes": 30, "limit": 5}
    )
    b = recommend_key(
        {"pantry": ["garlic", "tomato"], "diet": "vegan", "exclude_allergens": ["nuts"],
         "max_time_minutes": 30, "limit": 5}
    )
    assert a == b


def test_cache_key_changes_with_diet():
    base = {"pantry": ["tomato"], "diet": "vegan", "exclude_allergens": [],
            "max_time_minutes": None, "limit": 5}
    other = {**base, "diet": "vegetarian"}
    assert recommend_key(base) != recommend_key(other)


def test_cache_key_distinguishes_mode():
    base = {"pantry": ["tomato"], "diet": None, "exclude_allergens": [],
            "max_time_minutes": None, "limit": 5}
    assert recommend_key({**base, "mode": "sql"}) != recommend_key({**base, "mode": "hybrid"})


def test_cache_key_distinguishes_disliked_ingredients():
    base = {"pantry": ["tomato"], "diet": None, "exclude_allergens": [],
            "max_time_minutes": None, "limit": 5}
    # a dislike changes ranking, so it must not share a cache entry
    assert recommend_key(base) != recommend_key({**base, "disliked_ingredients": ["garlic"]})
    # but order within the dislike set is irrelevant
    assert recommend_key({**base, "disliked_ingredients": ["garlic", "onion"]}) == recommend_key(
        {**base, "disliked_ingredients": ["onion", "garlic"]}
    )


def test_cache_key_distinguishes_stage5_filters():
    base = {"pantry": ["tomato"], "diet": None, "exclude_allergens": [],
            "max_time_minutes": None, "limit": 5}
    # each new filter must fork the cache entry (proven bug class)
    assert recommend_key(base) != recommend_key({**base, "cuisines": ["italian"]})
    assert recommend_key(base) != recommend_key({**base, "meal_type": "dinner"})
    assert recommend_key(base) != recommend_key({**base, "nutrition_goals": ["high_protein"]})
    # but set order is irrelevant
    assert recommend_key({**base, "cuisines": ["a", "b"]}) == recommend_key(
        {**base, "cuisines": ["b", "a"]}
    )
    assert recommend_key({**base, "nutrition_goals": ["low_fat", "high_protein"]}) == recommend_key(
        {**base, "nutrition_goals": ["high_protein", "low_fat"]}
    )


@requires_db
def test_shopping_list_aggregates_missing_across_recipes(session):
    # Two tomato/garlic pasta-family recipes; empty pantry -> everything missing,
    # and shared ingredients (e.g. garlic) aggregate into a single row.
    from sqlalchemy import select
    from app.models import Recipe

    ids = [
        r.id
        for r in session.execute(select(Recipe).limit(3)).scalars()
    ]
    resp = build_shopping_list(session, ids, pantry=[])
    assert resp.items
    # No pantry -> nothing filtered out; every item has at least one source recipe.
    assert all(item.needed_for for item in resp.items)
    # A shared ingredient should be aggregated (one row per name+unit).
    keys = [(i.name, i.unit) for i in resp.items]
    assert len(keys) == len(set(keys))


@requires_db
def test_shopping_list_respects_pantry(session):
    from sqlalchemy import select
    from app.models import Recipe

    recipe = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    with_empty = build_shopping_list(session, [recipe.id], pantry=[])
    with_garlic = build_shopping_list(session, [recipe.id], pantry=["garlic", "pasta"])
    names_empty = {i.name for i in with_empty.items}
    names_after = {i.name for i in with_garlic.items}
    assert "garlic" in names_empty
    assert "garlic" not in names_after  # now in pantry
    assert "pasta" not in names_after


@requires_db
def test_shopping_list_reports_missing_recipe_ids(session):
    resp = build_shopping_list(session, [999999], pantry=[])
    assert resp.missing_recipe_ids == [999999]
    assert resp.items == []
