"""Adversarial eval wiring — no API.

Guards the plumbing that lets the adversarial suite drive the repair loop:
the suite loads, every case carries a disliked ingredient, and _req threads
disliked_ingredients into the AgentRequest (retrieval can't filter it, so the
validator flags it -> repair fires). The live repair behavior itself is
measured by the eval and unit-tested with fakes in test_agent_loop /
test_orchestrator.
"""
from app.evals.common import SUITES, load_cases
from app.evals.run_agent import _req


def test_adversarial_suite_loads_with_disliked():
    cases = load_cases(SUITES["adversarial"])
    assert len(cases) >= 5
    # every adversarial case names at least one disliked ingredient
    assert all(c.disliked_ingredients for c in cases)


def test_req_threads_disliked_into_request():
    case = load_cases(SUITES["adversarial"])[0]
    req = _req(case)
    assert req.disliked_ingredients == case.disliked_ingredients
    assert req.disliked_ingredients  # non-empty for adversarial cases


def test_gold_suite_still_loads_without_disliked():
    cases = load_cases(SUITES["gold"])
    assert len(cases) == 30
    # gold cases have no disliked ingredients (default empty) — backward compatible
    assert all(c.disliked_ingredients == [] for c in cases)
