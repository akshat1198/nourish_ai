"""Three-tier filter model: safety > cuisine > preference.

Guards the behaviour the recommend flow was rebuilt around — that a soft filter
demotes rather than empties, that cuisine is never silently substituted, and
that a matched spice does not count for as much as a matched protein.
"""
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Recipe, RecipeIngredient
from app.schemas.recommend import RecipeCandidate
from app.services.ingredients import resolve_pantry
from app.services.ranking import SoftFilters, rank
from app.services.retrieval import fetch_hybrid, hard_clauses
from app.tests.conftest import requires_db


def _candidate(title, **kw):
    base = dict(
        id=abs(hash(title)) % 100000,
        title=title,
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


def test_a_matched_soft_filter_ranks_higher():
    matches = _candidate("Dinner", meal_types=["dinner"])
    misses = _candidate("Breakfast", meal_types=["breakfast"])
    ranked = rank([misses, matches], limit=10, filters=SoftFilters(meal_type="dinner"))
    assert [r.title for r in ranked] == ["Dinner", "Breakfast"]
    assert [r.filters_matched for r in ranked] == [1, 0]
    assert all(r.filters_requested == 1 for r in ranked)


def test_requested_filters_outrank_what_the_pantry_happens_to_hold():
    # The reported bug: asking for high-protein put a low-protein recipe on top
    # because nothing was missing from it. What the user asked for wins.
    stocked_but_wrong = _candidate(
        "Stocked Low Protein", nutrition={"calories": 400, "protein_g": 5, "carbs_g": 60},
        missing_substantive=0, matched_weight=3.0,
    )
    high_protein = _candidate(
        "Missing But High Protein", nutrition={"calories": 500, "protein_g": 40, "carbs_g": 10},
        missing_substantive=3, matched_weight=0.5,
    )
    ranked = rank(
        [stocked_but_wrong, high_protein],
        limit=10,
        filters=SoftFilters(nutrition_goals=("high_protein",)),
    )
    assert [r.title for r in ranked] == ["Missing But High Protein", "Stocked Low Protein"]


def test_nutrition_grades_within_the_passing_set():
    # Passing the threshold is binary, but more protein is better than just enough.
    lots = _candidate("Lots", nutrition={"calories": 600, "protein_g": 60, "carbs_g": 10})
    some = _candidate("Some", nutrition={"calories": 500, "protein_g": 40, "carbs_g": 10})
    barely = _candidate("Barely", nutrition={"calories": 400, "protein_g": 26, "carbs_g": 10})
    ranked = rank([barely, lots, some], limit=10,
                  filters=SoftFilters(nutrition_goals=("high_protein",)))
    assert [r.title for r in ranked] == ["Lots", "Some", "Barely"]

    # low_carb runs the other way: fewer carbs ranks higher.
    ranked = rank([lots, some, barely], limit=10,
                  filters=SoftFilters(nutrition_goals=("low_carb",)))
    assert [r.nutrition["carbs_g"] for r in ranked] == sorted(
        r.nutrition["carbs_g"] for r in ranked
    )


def test_nutrition_ordering_is_inert_without_a_goal():
    a = _candidate("A", nutrition={"calories": 400, "protein_g": 50, "carbs_g": 5},
                   missing_substantive=2, matched_weight=0.5)
    b = _candidate("B", nutrition={"calories": 400, "protein_g": 2, "carbs_g": 90},
                   missing_substantive=0, matched_weight=3.0)
    # No goal requested -> nutrition_fit is 0.0 for both and pantry fit decides.
    ranked = rank([a, b], limit=10)
    assert all(r.nutrition_fit == 0.0 for r in ranked)
    assert ranked[0].title == "B"


def test_a_wildly_high_macro_cannot_outrank_a_merely_high_one():
    # The reported bug: nutrition_fit was an uncapped ratio, so the rows with the
    # most badly mis-parsed measures sorted above every correct recipe. Both rows
    # here sit inside the plausibility ceilings on purpose — this must exercise
    # the cap, not the gate, or it would still pass with the cap removed.
    inflated = _candidate("Inflated", nutrition={"calories": 900, "protein_g": 75,
                                                 "carbs_g": 10, "fat_g": 20},
                          missing_substantive=3, matched_weight=0.5)
    genuine = _candidate("Genuine", nutrition={"calories": 600, "protein_g": 50,
                                               "carbs_g": 10, "fat_g": 15},
                         missing_substantive=0, matched_weight=3.0)
    ranked = rank([inflated, genuine], limit=10,
                  filters=SoftFilters(nutrition_goals=("high_protein",)))
    fits = {r.title: r.nutrition_fit for r in ranked}
    assert fits["Inflated"] == fits["Genuine"], "past the cap both are simply 'lots'"
    # Tied on the goal, the next ordering key decides — here pantry fit.
    assert ranked[0].title == "Genuine"


def test_the_cap_leaves_grading_below_it_intact():
    # Clamping must not flatten the range the goal actually discriminates over.
    lots = _candidate("Lots", nutrition={"calories": 600, "protein_g": 45, "carbs_g": 10})
    some = _candidate("Some", nutrition={"calories": 500, "protein_g": 35, "carbs_g": 10})
    barely = _candidate("Barely", nutrition={"calories": 400, "protein_g": 26, "carbs_g": 10})
    ranked = rank([barely, lots, some], limit=10,
                  filters=SoftFilters(nutrition_goals=("high_protein",)))
    assert [r.title for r in ranked] == ["Lots", "Some", "Barely"]
    assert len({r.nutrition_fit for r in ranked}) == 3, "below the cap, grading is intact"


def test_implausible_nutrition_is_treated_as_unknown():
    # The corpus holds a recipe at 46,502 g protein. Ordering by a macro floats
    # exactly those rows to the top unless they're excluded outright.
    absurd = _candidate("Absurd", nutrition={"calories": 247577, "protein_g": 46502})
    real = _candidate("Real", nutrition={"calories": 600, "protein_g": 45, "carbs_g": 10})
    ranked = rank([absurd, real], limit=10,
                  filters=SoftFilters(nutrition_goals=("high_protein",)))
    assert ranked[0].title == "Real"
    assert ranked[1].nutrition_fit == 0.0, "unusable nutrition can't score a goal"

    # Calories but no protein is missing data, not a low-carb recipe.
    empty = _candidate("No Macros", nutrition={"calories": 130, "protein_g": 0,
                                               "carbs_g": 0, "fat_g": 0})
    assert rank([empty], limit=1, filters=SoftFilters(nutrition_goals=("low_carb",))
                )[0].nutrition_fit == 0.0


def test_a_nutrition_goal_nothing_can_satisfy_still_orders_best_first():
    # No vegetarian Thai recipe in the corpus reaches 25 g protein. Asking for
    # high protein must still return the highest protein available, in order —
    # a threshold that nothing clears must not flatten the ranking.
    cands = [
        _candidate("22g", nutrition={"calories": 400, "protein_g": 22, "carbs_g": 30}),
        _candidate("8g", nutrition={"calories": 300, "protein_g": 8, "carbs_g": 30}),
        _candidate("19g", nutrition={"calories": 350, "protein_g": 19, "carbs_g": 30}),
    ]
    ranked = rank(cands, limit=10, filters=SoftFilters(nutrition_goals=("high_protein",)))
    assert [r.title for r in ranked] == ["22g", "19g", "8g"]
    assert all(r.filters_matched == 0 for r in ranked), "goal is graded, not gated"


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
def _eligible(session, pantry_ids, *, diet=None, cuisines=()):
    """How many recipes in THIS corpus satisfy the filters and touch the pantry.

    Derived rather than hardcoded so the assertion means the same thing against
    the 144-recipe CI seed and the full local corpus.
    """
    clauses = hard_clauses(diet, (), cuisines)
    return (
        session.execute(
            select(func.count(func.distinct(RecipeIngredient.recipe_id)))
            .select_from(RecipeIngredient)
            .join(Recipe, Recipe.id == RecipeIngredient.recipe_id)
            .where(RecipeIngredient.ingredient_id.in_(list(pantry_ids)), *clauses)
        ).scalar()
        or 0
    )


@requires_db
def test_filter_combinations_reach_the_recipes_that_satisfy_them(session):
    # These returned 0 and 1 when the arms truncated to their top 30 before the
    # filters were applied, while 45 and 42 eligible recipes sat in the corpus.
    # Retrieval must surface what exists, whatever the corpus size.
    for pantry, kw in [
        (["onion", "tomato", "garlic", "rice", "lentils"],
         dict(diet="vegan", cuisines=["italian"])),
        (["onion", "tomato", "garlic", "rice", "chicken"],
         dict(diet="gluten_free", cuisines=["mexican"])),
    ]:
        ids = resolve_pantry(session, pantry).ingredient_ids
        eligible = _eligible(session, ids, **kw)
        if not eligible:
            continue  # this corpus has none; nothing to prove
        got = fetch_hybrid(session, ids, [], limit=50, **kw)
        assert len(got) >= min(10, eligible), (
            f"{kw}: {eligible} eligible in corpus but only {len(got)} surfaced"
        )


@requires_db
def test_hard_tier_is_never_violated(session):
    # Whatever ranking does, a diet/allergen/cuisine constraint holds for every
    # returned candidate — the arms filter in SQL and _passes_filters re-asserts.
    ids = resolve_pantry(session, ["onion", "tomato", "garlic", "rice"]).ingredient_ids
    got = fetch_hybrid(
        session, ids, [], limit=50,
        diet="vegan", exclude_allergens=["nuts"], cuisines=["italian"],
    )
    assert _eligible(session, ids, diet="vegan", cuisines=["italian"]) == 0 or got
    for c in got:
        assert "vegan" in c.diet_labels
        assert "nuts" not in c.allergens
        assert c.cuisine == "italian"


@requires_db
def test_the_sql_nutrition_filter_agrees_with_the_python_gate(session):
    # soft_clauses mirrors _nutrition_ok in SQL by hand. Nothing caught the two
    # drifting apart, and they disagreeing means a recipe is filtered one way
    # during retrieval and judged another way in ranking. Run over the real
    # corpus so the comparison spans every boundary the data actually reaches.
    from app.services.retrieval import _nutrition_ok, soft_clauses

    goals = ["high_protein"]
    rows = session.execute(select(Recipe.id, Recipe.nutrition)).all()
    expected = {rid for rid, n in rows if _nutrition_ok(n or {}, goals)}
    got = set(session.execute(
        select(Recipe.id).where(*soft_clauses(nutrition_goals=goals))
    ).scalars())
    assert got == expected, (
        f"SQL and Python disagree on {len(got ^ expected)} recipes"
    )


@requires_db
def test_browse_mode_returns_recipes_but_an_unresolved_pantry_does_not(session):
    # Entering no ingredients at all used to come back completely empty, because
    # the pantry-match query returns nothing when there is no pantry.
    got = fetch_hybrid(
        session, [], [], limit=10, nutrition_goals=["high_protein"], browse=True
    )
    assert got, "browsing with no ingredients must still surface recipes"
    # Ordered by the goal, but only up to the cap: past NUTRI_FIT_CAP multiples of
    # the threshold, more protein is a data-quality artifact rather than a better
    # match, so those rows tie and a later key settles them. Comparing raw grams
    # here would assert an ordering the ranking deliberately no longer promises.
    ceiling = settings.NUTRI_FIT_CAP * settings.NUTRI_HIGH_PROTEIN_G
    capped = [min((c.nutrition or {}).get("protein_g", 0), ceiling) for c in got]
    assert capped == sorted(capped, reverse=True), "browse mode orders by the goal"

    # But a pantry that was typed and resolved to nothing is a different thing:
    # returning arbitrary recipes there would imply we matched what they typed.
    assert fetch_hybrid(session, [], [], limit=10, nutrition_goals=["high_protein"]) == []


@requires_db
def test_fallback_modes_preserve_the_filter_ordering(session):
    # substitution_first fires constantly on a thin pantry, and it used to
    # re-sort on swap-count alone — undoing the filter ordering rank() had just
    # established. Whatever mode fires, the goal ordering must survive.
    from app.services.fallback import apply_fallback

    ids = resolve_pantry(session, ["chicken"]).ingredient_ids
    cands = fetch_hybrid(session, ids, [], limit=50,
                         nutrition_goals=["high_protein"], soften=True)
    filters = SoftFilters(nutrition_goals=("high_protein",))
    pool = rank(cands, limit=50, filters=filters)
    _mode, _expl, results = apply_fallback(session, pool, ids, limit=10)
    fits = [r.nutrition_fit for r in results]
    assert fits == sorted(fits, reverse=True), f"{_mode} reordered against the goal"


@requires_db
def test_soft_filters_are_strict_unless_softening_is_requested(session):
    # The agent tools, MCP surface, and eval harness all call retrieval directly
    # and mean it literally: meal_type="dinner" must return dinner recipes.
    # Only /v1/recommendations opts into demotion.
    ids = resolve_pantry(session, ["onion", "tomato", "garlic", "rice"]).ingredient_ids
    strict = fetch_hybrid(session, ids, [], limit=50, meal_type="dinner")
    assert all("dinner" in (c.meal_types or []) for c in strict)

    softened = fetch_hybrid(session, ids, [], limit=50, meal_type="dinner", soften=True)
    assert len(softened) >= len(strict), "softening must only ever widen the pool"
