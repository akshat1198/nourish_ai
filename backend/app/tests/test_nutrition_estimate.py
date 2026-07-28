"""LLM nutrition estimation: the guards, not the model's arithmetic.

The estimate only exists for recipes whose derived nutrition was already
rejected as implausible, so the one thing that must hold is that it cannot
smuggle an equally implausible number back in through a different door.
"""
from app.llm.client import LLMError
from app.models import Recipe
from app.schemas.llm import EstimatedNutrition
from app.services import nutrition_estimate
from app.services.nutrition_estimate import as_nutrition, estimate_nutrition


class _FakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def generate_structured(self, *a, **kw):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _recipe():
    return Recipe(
        id=1,
        title="Bhuna Murgh",
        servings=2,
        ingredients=[
            {"qty": 750, "unit": "grams", "name": "chicken"},
            {"qty": 2, "unit": None, "name": "onion"},
            {"qty": None, "unit": None, "name": "salt"},
        ],
    )


def _install(monkeypatch, result, enabled=True):
    fake = _FakeLLM(result)
    monkeypatch.setattr(nutrition_estimate, "is_enabled", lambda: enabled)
    monkeypatch.setattr(nutrition_estimate, "get_llm", lambda: fake)
    return fake


# 4/4/9-consistent and comfortably inside the ceilings.
_GOOD = EstimatedNutrition(calories=520.0, protein_g=42.0, carbs_g=18.0, fat_g=28.0, serves=4)


def test_a_plausible_estimate_is_returned_and_shaped_for_storage(monkeypatch):
    fake = _install(monkeypatch, _GOOD)
    est = estimate_nutrition(_recipe())
    assert est is not None
    assert fake.calls == 1
    assert as_nutrition(est) == {
        "calories": 520.0, "protein_g": 42.0, "carbs_g": 18.0, "fat_g": 28.0
    }
    assert "serves" not in as_nutrition(est), "the model's serving count is diagnostic only"


def test_an_estimate_past_the_plausibility_ceiling_is_rejected(monkeypatch):
    # The whole point: the estimate must clear the same bar a derived value must,
    # or it just launders an implausible number past the ceilings.
    _install(monkeypatch, EstimatedNutrition(
        calories=2500.0, protein_g=140.0, carbs_g=200.0, fat_g=140.0, serves=1))
    assert estimate_nutrition(_recipe()) is None


def test_internally_inconsistent_macros_are_rejected(monkeypatch):
    # Inside every ceiling, but 10P/5C/3F implies ~87 kcal, not 900. Derived
    # nutrition reconciles by construction; an independently-generated set does
    # not, which is the case this check exists for.
    _install(monkeypatch, EstimatedNutrition(
        calories=900.0, protein_g=10.0, carbs_g=5.0, fat_g=3.0, serves=2))
    assert estimate_nutrition(_recipe()) is None


def test_negative_and_non_finite_macros_are_rejected(monkeypatch):
    _install(monkeypatch, EstimatedNutrition(
        calories=500.0, protein_g=-10.0, carbs_g=20.0, fat_g=20.0, serves=2))
    assert estimate_nutrition(_recipe()) is None

    _install(monkeypatch, EstimatedNutrition(
        calories=float("inf"), protein_g=30.0, carbs_g=20.0, fat_g=20.0, serves=2))
    assert estimate_nutrition(_recipe()) is None


def test_zero_calories_is_missing_data_not_a_zero_calorie_meal(monkeypatch):
    _install(monkeypatch, EstimatedNutrition(
        calories=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0, serves=2))
    assert estimate_nutrition(_recipe()) is None


def test_it_fails_open_when_the_assistant_is_unavailable(monkeypatch):
    fake = _install(monkeypatch, _GOOD, enabled=False)
    assert estimate_nutrition(_recipe()) is None
    assert fake.calls == 0, "no call should be made when the LLM is disabled"


def test_it_fails_open_on_an_llm_error(monkeypatch):
    _install(monkeypatch, LLMError("upstream 529"))
    assert estimate_nutrition(_recipe()) is None


def test_the_prompt_carries_the_quantities_and_the_claimed_servings(monkeypatch):
    captured = {}

    class _Capture(_FakeLLM):
        def generate_structured(self, *a, **kw):
            captured["content"] = kw["messages"][0]["content"]
            return _GOOD

    fake = _Capture(_GOOD)
    monkeypatch.setattr(nutrition_estimate, "is_enabled", lambda: True)
    monkeypatch.setattr(nutrition_estimate, "get_llm", lambda: fake)
    estimate_nutrition(_recipe())
    content = captured["content"]
    assert "750 grams chicken" in content
    assert "Claimed servings: 2" in content
    # The stated count being wrong is the reason these rows need estimating, so
    # the model has to be told it may disagree with it.
    assert "serves" in content.lower()
