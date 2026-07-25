"""Three-tier filter model: safety > cuisine > preference.

Guards the behaviour the recommend flow was rebuilt around — that a soft filter
demotes rather than empties, that cuisine is never silently substituted, and
that a matched spice does not count for as much as a matched protein.
"""
from app.schemas.recommend import RecipeCandidate
from app.services.ingredients import resolve_pantry
from app.services.ranking import SoftFilters, rank
from app.services.retrieval import fetch_hybrid
from app.tests.conftest import requires_db


def _candidate(title, **kw):
    base = dict(
        id=abs(hash(title)) % 100000,
        title=title,
        time_minutes=30,
        diet_labels=[],
        allergens=[],
        tags=[],
        nutrition={},
        matched_ingredients=[],
        missing_ingredients=[],
        matched_essential=0,
        total_essential=0,
    )
    base.update(kw)
    return RecipeCandidate(**base)


# --------------------------------------------------------------------------- #
# Category weighting
# --------------------------------------------------------------------------- #
def test_substantive_match_outranks_a_larger_pile_of_spices():
    # The bug this encodes: counting every ingredient equally let a spice-dense
    # recipe win on any stocked spice rack. Four spices (4 x 0.2) must not beat
    # a protein and a vegetable (2 x 1.0).
    spices = _candidate(
        "Spice Heavy",
        matched_ingredients=["turmeric", "cumin", "coriander", "chilli"],
        missing_ingredients=["lamb"],
        matched_essential=4, total_essential=5,
        matched_weight=0.8, missing_weight=1.0,
        matched_essential_weight=0.8, total_essential_weight=1.8,
        missing_substantive=1,
    )
    substantive = _candidate(
        "Real Food",
        matched_ingredients=["chicken", "broccoli"],
        missing_ingredients=["cumin"],
        matched_essential=2, total_essential=3,
        matched_weight=2.0, missing_weight=0.2,
        matched_essential_weight=2.0, total_essential_weight=2.2,
        missing_substantive=0,
    )
    ranked = rank([spices, substantive], limit=10)
    assert [r.title for r in ranked] == ["Real Food", "Spice Heavy"]


def test_missing_only_spices_still_counts_as_pantry_complete():
    # Missing cumin doesn't stop you cooking; missing the chicken does.
    c = _candidate(
        "Ready To Cook",
        matched_ingredients=["chicken", "rice"],
        missing_ingredients=["cumin", "salt"],
        missing_substantive=0,
    )
    assert rank([c], limit=1)[0].pantry_complete is True


# --------------------------------------------------------------------------- #
# Tier ordering
# --------------------------------------------------------------------------- #
def test_cuisine_outranks_pantry_completeness():
    # The original complaint: asked for Italian, got Indian. A fully-stocked
    # off-cuisine recipe must still sit below a partially-stocked in-cuisine one.
    off = _candidate(
        "Fully Stocked Curry", cuisine="indian",
        matched_ingredients=["onion", "tomato"], missing_substantive=0,
        matched_weight=2.0, missing_weight=0.0,
    )
    on = _candidate(
        "Half Stocked Pasta", cuisine="italian",
        matched_ingredients=["pasta"], missing_ingredients=["basil", "pancetta"],
        missing_substantive=2, matched_weight=0.9, missing_weight=1.8,
    )
    ranked = rank([off, on], limit=10, filters=SoftFilters(cuisines=("italian",)))
    assert [r.title for r in ranked] == ["Half Stocked Pasta", "Fully Stocked Curry"]
    assert ranked[0].cuisine_matched is True
    assert ranked[1].cuisine_matched is False


def test_more_soft_filters_matched_ranks_higher():
    both = _candidate("Both", time_minutes=20, meal_types=["dinner"])
    one = _candidate("One", time_minutes=20, meal_types=["breakfast"])
    neither = _candidate("Neither", time_minutes=90, meal_types=["breakfast"])
    ranked = rank(
        [neither, one, both],
        limit=10,
        filters=SoftFilters(max_time=30, meal_type="dinner"),
    )
    assert [r.title for r in ranked] == ["Both", "One", "Neither"]
    assert [r.filters_matched for r in ranked] == [2, 1, 0]
    assert all(r.filters_requested == 2 for r in ranked)


def test_disliked_still_sinks_beneath_every_clean_recipe():
    # Dislike outranks pantry-completeness: being fully stocked doesn't redeem
    # a recipe containing something the user said they dislike.
    bad = _candidate("Disliked", missing_substantive=0, matched_weight=3.0)
    ok = _candidate("Clean", missing_substantive=2, matched_weight=0.5)
    ranked = rank([bad, ok], limit=10, disliked_ids={bad.id})
    assert [r.title for r in ranked] == ["Clean", "Disliked"]


# --------------------------------------------------------------------------- #
# Recall against the real corpus
# --------------------------------------------------------------------------- #
@requires_db
def test_filter_combinations_reach_the_recipes_that_satisfy_them(session):
    # Each of these returned 0 or 1 when hard filters ran after the arms had
    # already truncated to their top 30, despite 40+ eligible recipes existing.
    cases = [
        (["onion", "tomato", "garlic", "rice", "lentils"],
         dict(diet="vegan", cuisines=["italian"])),
        (["onion", "tomato", "garlic", "rice", "chicken"],
         dict(diet="gluten_free", cuisines=["mexican"], meal_type="dinner")),
    ]
    for pantry, kw in cases:
        ids = resolve_pantry(session, pantry).ingredient_ids
        got = fetch_hybrid(session, ids, [], limit=50, **kw)
        assert len(got) >= 10, f"{kw} surfaced only {len(got)}"


@requires_db
def test_hard_tier_is_never_violated(session):
    # Whatever ranking does, a diet/allergen/cuisine constraint holds for every
    # returned candidate — the arms filter in SQL and _passes_filters re-asserts.
    ids = resolve_pantry(session, ["onion", "tomato", "garlic", "rice"]).ingredient_ids
    got = fetch_hybrid(
        session, ids, [], limit=50,
        diet="vegan", exclude_allergens=["nuts"], cuisines=["italian"],
    )
    assert got, "expected candidates to assert over"
    for c in got:
        assert "vegan" in c.diet_labels
        assert "nuts" not in c.allergens
        assert c.cuisine == "italian"
