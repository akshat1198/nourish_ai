"""Free-text dietary constraints must reach the hard filter, not the model.

The bug this pins: asking the planner for "something high protein tonight, no
dairy" with an empty exclude_allergens returned two recipes labelled `dairy`
and reported `violations: []`. Nothing deterministic had been told dairy was
excluded, so the hard SQL filter and the validator both had nothing to enforce
and the model's reading was the only thing standing between the user and an
allergen.
"""
import pytest

from app.schemas.agent import AgentRequest
from app.services.question_constraints import (
    all_excluded,
    extract_constraints,
    merge_into_request,
)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("something high protein tonight, no dairy", ["dairy"]),
        ("dairy-free dinner please", ["dairy"]),
        ("a gluten free pasta", ["gluten"]),
        ("no nuts and no shellfish", ["nuts", "shellfish"]),
        ("I'm allergic to peanuts", ["peanuts"]),
        ("without any eggs", ["eggs"]),
        ("nut-free snack for school", ["nuts"]),
        ("skip the cheese", ["dairy"]),
        ("can't have seafood", ["shellfish"]),
    ],
)
def test_negated_terms_become_hard_exclusions(question, expected):
    _, allergens = extract_constraints(question)
    assert sorted(allergens) == sorted(expected)


@pytest.mark.parametrize(
    "question",
    [
        "I love dairy",
        "extra cheese please",
        "something with peanuts",
        "a rich creamy pasta",
    ],
)
def test_no_negation_means_no_exclusion(question):
    """An over-eager match silently shrinks results for a constraint nobody set."""
    _, allergens = extract_constraints(question)
    assert allergens == []


@pytest.mark.parametrize(
    "question,diet",
    [
        ("a vegan curry", "vegan"),
        ("something vegetarian", "vegetarian"),
        ("gluten free bread", "gluten_free"),
        ("just something quick", None),
    ],
)
def test_diet_is_detected(question, diet):
    found, _ = extract_constraints(question)
    assert found == diet


def test_explicit_request_values_are_never_overridden():
    """A user's chosen filters outrank a phrase parsed out of their prose."""
    req = AgentRequest(pantry=["egg"], question="a vegan dinner", diet="vegetarian")
    applied = merge_into_request(req, req.question)
    assert req.diet == "vegetarian"
    assert applied["diet"] is None


def test_merge_is_additive_and_reports_what_it_applied():
    req = AgentRequest(
        pantry=["egg"], question="no dairy please", exclude_allergens=["nuts"]
    )
    applied = merge_into_request(req, req.question)
    assert sorted(req.exclude_allergens) == ["dairy", "nuts"]
    assert applied["exclude_allergens"] == ["dairy"]


def test_already_excluded_is_not_duplicated():
    req = AgentRequest(pantry=["egg"], question="no dairy", exclude_allergens=["dairy"])
    applied = merge_into_request(req, req.question)
    assert req.exclude_allergens == ["dairy"]
    assert applied["exclude_allergens"] == []


def test_diet_implications_match_the_frontend_mapping():
    """Mirrors dietImpliedAllergens in frontend/lib/filter-options.ts; the two
    must not drift, per the single-source rule in CLAUDE.md."""
    assert all_excluded("vegan", []) == ["dairy", "eggs", "fish", "shellfish"]
    assert all_excluded("vegetarian", []) == ["fish", "shellfish"]
    assert all_excluded("gluten_free", []) == ["gluten"]
    assert all_excluded(None, ["nuts"]) == ["nuts"]


def test_empty_question_is_safe():
    assert extract_constraints(None) == (None, [])
    assert extract_constraints("") == (None, [])
