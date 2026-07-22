"""Ranking tests — pure, no DB required."""
from app.schemas.recommend import RecipeCandidate
from app.services.ranking import annotate, rank


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


def test_disliked_recipe_sinks_below_clean_but_remains():
    # 'Bad' has the BEST base fit but is disliked; 'OK' is a weaker clean match.
    bad = _candidate("Bad", matched_ess=3, total_ess=3, matched=["x", "y", "z"], missing=[])
    ok = _candidate("OK", matched_ess=1, total_ess=3, matched=["x"], missing=["y", "z"])
    ranked = rank([bad, ok], limit=10, disliked_ids={bad.id})
    assert [r.title for r in ranked] == ["OK", "Bad"]  # disliked sank beneath clean
    assert ranked[-1].title == "Bad"                    # but is still present
    assert ranked[-1].score < ranked[0].score
    assert "dislike" in ranked[-1].why                  # and the demotion is explained


def test_no_disliked_ids_leaves_ranking_unchanged():
    a = _candidate("A", matched_ess=3, total_ess=3, matched=["x", "y", "z"], missing=[])
    b = _candidate("B", matched_ess=1, total_ess=3, matched=["x"], missing=["y", "z"])
    assert [r.title for r in rank([a, b], limit=10)] == ["A", "B"]
    assert [r.title for r in rank([a, b], limit=10, disliked_ids=set())] == ["A", "B"]


def test_annotate_demotes_disliked_preserving_rrf_order_within_groups():
    # incoming (RRF) order interleaves disliked (D) and clean (C): D1, C1, D2, C2
    d1 = _candidate("D1", matched_ess=3, total_ess=3, matched=["x", "y", "z"], missing=[])
    c1 = _candidate("C1", matched_ess=1, total_ess=3, matched=["x"], missing=["y", "z"])
    d2 = _candidate("D2", matched_ess=2, total_ess=3, matched=["x", "y"], missing=["z"])
    c2 = _candidate("C2", matched_ess=1, total_ess=3, matched=["x"], missing=["y", "z"])
    out = annotate([d1, c1, d2, c2], limit=10, disliked_ids={d1.id, d2.id})
    # clean first (original order kept), then disliked (original order kept)
    assert [r.title for r in out] == ["C1", "C2", "D1", "D2"]


def test_annotate_without_disliked_preserves_incoming_order():
    # annotate must NOT re-sort by score when no dislikes (hybrid keeps RRF order)
    strong = _candidate("Strong", matched_ess=3, total_ess=3, matched=["x", "y", "z"], missing=[])
    weak = _candidate("Weak", matched_ess=1, total_ess=3, matched=["x"], missing=["y", "z"])
    assert [r.title for r in annotate([weak, strong], limit=10)] == ["Weak", "Strong"]
