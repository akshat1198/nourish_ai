"""Unit tests for the ingestion foundation (no DB, no LLM, no network)."""
import json
from pathlib import Path

from scripts.ingest.normalize import CanonicalMatcher, parse_ingredient_line
from scripts.ingest.taxonomy_maps import (
    map_course,
    map_cuisine,
    map_diet_seed,
    map_mealdb_area,
)


def test_parse_strips_qty_unit_paren_prep():
    p = parse_ingredient_line("1 cup Tindora (Dondakaya/ Kovakkai) - finely chopped")
    assert p.core == "tindora"
    assert p.qty == 1.0
    assert p.unit == "cup"


def test_parse_multiword_core_and_fraction():
    p = parse_ingredient_line("1/2 teaspoon Red Chilli powder")
    assert p.core == "red chilli powder"
    assert p.qty == 0.5
    assert p.unit == "teaspoon"


def test_parse_unicode_fraction_and_mixed_number():
    assert parse_ingredient_line("½ cup water").qty == 0.5
    assert parse_ingredient_line("1 1/2 cups flour").qty == 1.5


def test_parse_no_quantity():
    p = parse_ingredient_line("Salt - to taste")
    assert p.core == "salt"
    assert p.qty is None


def test_matcher_exact_and_alias():
    m = CanonicalMatcher(
        [{"name": "yogurt", "aliases": ["curd"]}, {"name": "turmeric", "aliases": []}]
    )
    assert m.match("yogurt") == "yogurt"
    assert m.match("curd") == "yogurt"          # alias
    assert m.match("turmerics") == "turmeric"   # singularized


def test_matcher_strips_trailing_form_word():
    m = CanonicalMatcher([{"name": "turmeric", "aliases": []}])
    assert m.match("turmeric powder") == "turmeric"   # form-word stripped
    assert m.match("cinnamon powder") is None          # not in vocab -> honest miss


def test_matcher_no_head_noun_guessing():
    # "black pepper" must NOT match a canonical "pepper" via head-noun guess.
    m = CanonicalMatcher([{"name": "bell pepper", "aliases": ["pepper"]}])
    assert m.match("black pepper powder") is None


def test_cuisine_regional_and_taxonomy_child_ids():
    assert map_cuisine("Gujarati Recipes") == ("indian", "gujarati")
    assert map_cuisine("Maharashtrian Recipes") == ("indian", "marathi")  # child id
    assert map_cuisine("South Indian Recipes") == ("indian", "south_indian")
    assert map_cuisine("Thai") == ("asian", "thai")
    assert map_cuisine("Italian Recipes") == ("italian", None)


def test_cuisine_unmapped_is_null():
    assert map_cuisine("Continental") == (None, None)
    assert map_cuisine("Fusion") == (None, None)
    assert map_cuisine("") == (None, None)


def test_course_and_diet_seed():
    assert map_course("South Indian Breakfast") == ["breakfast"]
    assert map_course("Lunch") == ["lunch"]
    assert map_course("Something Odd") == ["lunch", "dinner"]  # default
    assert map_diet_seed("Vegan") == ["vegan", "vegetarian"]
    assert map_diet_seed("Non Vegeterian") == []             # source's spelling
    assert map_diet_seed("Gluten Free") == ["gluten_free"]


def test_mealdb_area():
    assert map_mealdb_area("Indian") == ("indian", None)
    assert map_mealdb_area("Chinese") == ("asian", "chinese")
    assert map_mealdb_area("British") == ("european", "british")
    # TheMealDB mixes nationalities and bare country names in the same column.
    assert map_mealdb_area("France") == map_mealdb_area("French")
    assert map_mealdb_area("India") == ("indian", None)
    assert map_mealdb_area("United States") == ("american", None)
    # No honest bucket for these — they must stay NULL rather than be mis-filed.
    assert map_mealdb_area("Australian") == (None, None)
    assert map_mealdb_area("") == (None, None)


from app.core.allergens import ALLERGEN_SET, ALLERGEN_VOCAB

_SEED = Path(__file__).resolve().parents[2] / "seed_data"
_FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "filter-options.ts"


def test_derive_keyword_backstop_flags_meat_and_shellfish():
    from scripts.ingest.pipeline import classify_and_derive
    props = {"rice": {"vegetarian": True, "vegan": True, "allergens": [],
                      "per_100g": {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}}}
    matched = [("rice", 200.0, True)]
    # Plural "Prawns" (unmatched) must still defeat the veg/vegan claim + flag shellfish.
    d = classify_and_derive(props, matched, ["Rice", "Prawns"], servings=2)
    assert "vegetarian" not in d["diet_labels"]
    assert "vegan" not in d["diet_labels"]
    assert "shellfish" in d["allergens"]
    # A genuinely veg dish keeps the labels.
    d2 = classify_and_derive(props, matched, ["Rice", "Tomatoes"], servings=2)
    assert "vegetarian" in d2["diet_labels"] and "vegan" in d2["diet_labels"]


def test_derive_title_scan_catches_meat_when_ingredient_unmatched():
    from scripts.ingest.pipeline import classify_and_derive
    props = {"rice": {"vegetarian": True, "vegan": True, "allergens": [],
                      "per_100g": {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}}}
    matched = [("rice", 200.0, True)]
    # Meat only in the TITLE (Hindi 'murgh' = chicken), not in matched ingredients.
    d = classify_and_derive(props, matched, ["Rice", "Onion"], servings=2, title="Murgh Biryani")
    assert "vegetarian" not in d["diet_labels"]
    assert "vegan" not in d["diet_labels"]


def test_seed_allergen_tokens_match_filter_vocab():
    for fname in ("ingredients.json", "recipes.json"):
        rows = json.loads((_SEED / fname).read_text())
        tokens = {a for r in rows for a in r.get("allergens", [])}
        off = tokens - ALLERGEN_SET
        assert not off, f"{fname} has off-vocab allergen tokens: {off}"


def test_frontend_allergen_vocab_matches_backend():
    """The frontend ALLERGENS list (TS) must equal backend ALLERGEN_VOCAB.

    They can't share a module across the Python/TS split, so this guards drift:
    add an allergen to one side and this test fails until both agree.
    """
    import re

    text = _FRONTEND.read_text()
    block = re.search(r"ALLERGENS[^=]*=\s*\[(.*?)\]", text, re.S)
    assert block, "could not find ALLERGENS array in filter-options.ts"
    tokens = re.findall(r'"([^"]+)"', block.group(1))
    assert set(tokens) == ALLERGEN_SET, (
        f"frontend/backend allergen vocab drift: "
        f"frontend-only={set(tokens) - ALLERGEN_SET}, backend-only={ALLERGEN_SET - set(tokens)}"
    )
