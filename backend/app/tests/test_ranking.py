"""Ranking tests (RETR-03) — pure, no DB required."""
from app.schemas.recommend import RecipeCandidate
from app.services.ranking import rank


def _candidate(title, *, matched_ess, total_ess, matched, missing, time=30):
    return RecipeCandidate(
        id=abs(hash(title)) % 100000,
        title=title,
        time_minutes=time,
        diet_labels=[],
        allergens=[],
        tags=[],
        nutrition={},
        matched_ingredients=matched,
        missing_ingredients=missing,
        matched_essential=matched_ess,
        total_essential=total_ess,
    )


def test_fewer_missing_wins_at_equal_coverage():
    a = _candidate("A", matched_ess=3, total_ess=3, matched=["x", "y", "z"], missing=["m1"])
    b = _candidate(
        "B", matched_ess=3, total_ess=3, matched=["x", "y", "z"], missing=["m1", "m2", "m3"]
    )
    ranked = rank([b, a], limit=10)
    assert [r.title for r in ranked] == ["A", "B"]
    assert ranked[0].score > ranked[1].score


def test_higher_coverage_wins():
    a = _candidate("A", matched_ess=4, total_ess=4, matched=["a", "b", "c", "d"], missing=[])
    b = _candidate("B", matched_ess=2, total_ess=4, matched=["a", "b"], missing=["c", "d"])
    ranked = rank([b, a], limit=10)
    assert ranked[0].title == "A"


def test_why_string_mentions_missing_and_time():
    c = _candidate("C", matched_ess=4, total_ess=5, matched=["a"] * 4, missing=["butter"], time=25)
    ranked = rank([c], limit=1)
    why = ranked[0].why
    assert "4/5" in why
    assert "butter" in why
    assert "25 min" in why


def test_limit_trims_results():
    cands = [
        _candidate(f"R{i}", matched_ess=1, total_ess=2, matched=["a"], missing=["b"])
        for i in range(10)
    ]
    assert len(rank(cands, limit=3)) == 3
