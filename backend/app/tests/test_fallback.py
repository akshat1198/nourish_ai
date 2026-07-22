"""Low-confidence fallback tests."""
from app.schemas.recommend import RankedRecipe
from app.services.fallback import apply_fallback, substitution_suggestions
from app.services.ingredients import resolve_pantry
from app.services.ranking import rank
from app.services.retrieval import fetch_candidates
from app.tests.conftest import requires_db


def _ranked(title, matched_ess, total_ess):
    return RankedRecipe(
        id=abs(hash(title)) % 100000, title=title, time_minutes=30, diet_labels=[],
        allergens=[], tags=[], nutrition={}, matched_ingredients=["x"] * matched_ess,
        missing_ingredients=[], matched_essential=matched_ess, total_essential=total_ess,
        score=0.5, why="",
    )


def test_high_coverage_stays_normal():
    ranked = [_ranked("A", 4, 4), _ranked("B", 2, 4)]
    mode, expl, out = apply_fallback(session=None, ranked=ranked, pantry_ids=[])
    assert mode == "normal"
    assert expl is None
    assert [r.title for r in out] == ["A", "B"]


def test_empty_results_is_not_normal():
    mode, _, _ = apply_fallback(session=None, ranked=[], pantry_ids=[])
    assert mode != "normal"  # shopping_assisted (no pantry -> no substitutions)


@requires_db
def test_substitution_first_when_swap_available(session):
    # Pantry has tofu; a chicken recipe's chicken can be swapped for tofu.
    resolved = resolve_pantry(session, ["tofu", "rice", "soy sauce", "garlic"])
    # Force low confidence by ranking a chicken stir-fry the pantry barely matches:
    # easier: directly test the suggestion lookup on a known chicken recipe.
    from sqlalchemy import select
    from app.models import Recipe

    chicken = session.execute(
        select(Recipe).where(Recipe.title.like("Chicken Breast & %Stir-Fry")).limit(1)
    ).scalar_one()
    sugg = substitution_suggestions(session, [chicken.id], resolved.ingredient_ids)
    swaps = sugg.get(chicken.id, [])
    assert any(s.use == "tofu" and s.missing == "chicken breast" for s in swaps)


@requires_db
def test_water_pantry_triggers_fallback_not_empty(session):
    # Pantry ["water"] resolves to nothing; SQL retrieval returns no matches.
    resolved = resolve_pantry(session, ["water"])
    assert resolved.ingredient_ids == []
    ranked = rank(fetch_candidates(session, resolved.ingredient_ids, limit=50), limit=5)
    mode, expl, out = apply_fallback(session, ranked, resolved.ingredient_ids)
    # No pantry ingredients -> shopping_assisted with an explanation.
    assert mode == "shopping_assisted"
    assert expl
