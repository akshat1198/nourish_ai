"""Unit tests for the Stage 6 ingestion foundation (no DB, no LLM, no network)."""
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
    assert map_mealdb_area("British") == (None, None)  # unmapped
