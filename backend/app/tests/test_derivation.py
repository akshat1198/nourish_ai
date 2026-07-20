"""Shared diet/allergen derivation (7.3a) — the validator the modify endpoint
re-runs after a swap. Pure, no DB; props built inline."""
from app.services.derivation import classify_and_derive, load_props

_PANEER = {"vegetarian": True, "vegan": False, "allergens": ["dairy"],
           "per_100g": {"calories": 265, "protein_g": 18, "carbs_g": 1.2, "fat_g": 21}}
_TOFU = {"vegetarian": True, "vegan": True, "allergens": ["soy"],
         "per_100g": {"calories": 76, "protein_g": 8, "carbs_g": 1.9, "fat_g": 4.8}}
_RICE = {"vegetarian": True, "vegan": True, "allergens": [],
         "per_100g": {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}}


def test_paneer_set_is_vegetarian_with_dairy():
    props = {"paneer": _PANEER, "rice": _RICE}
    d = classify_and_derive(props, [("paneer", 100.0, True), ("rice", 200.0, True)],
                            ["paneer", "rice"], servings=2)
    assert "dairy" in d["allergens"]
    assert "vegetarian" in d["diet_labels"]
    assert "vegan" not in d["diet_labels"]


def test_tofu_set_is_vegan_with_soy():
    props = {"tofu": _TOFU, "rice": _RICE}
    d = classify_and_derive(props, [("tofu", 100.0, True), ("rice", 200.0, True)],
                            ["tofu", "rice"], servings=2)
    assert "soy" in d["allergens"]
    assert "vegan" in d["diet_labels"]


def test_swap_paneer_to_tofu_drops_dairy_adds_soy():
    props = {"paneer": _PANEER, "tofu": _TOFU, "rice": _RICE}
    before = classify_and_derive(props, [("paneer", 100.0, True), ("rice", 200.0, True)],
                                 ["paneer", "rice"], servings=2)
    after = classify_and_derive(props, [("tofu", 100.0, True), ("rice", 200.0, True)],
                                ["tofu", "rice"], servings=2)
    added = set(after["allergens"]) - set(before["allergens"])
    removed = set(before["allergens"]) - set(after["allergens"])
    assert added == {"soy"}
    assert removed == {"dairy"}


def test_load_props_reads_seed_file():
    props = load_props()
    assert "paneer" in props and "tofu" in props
    assert props["paneer"]["allergens"]  # non-empty (dairy)
