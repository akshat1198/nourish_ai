"""Shared diet/allergen derivation — the validator the modify endpoint re-runs
after a swap. Mostly pure with props built inline; the DB-backed tests cover
the ingredient vocabulary being readable and extendable at runtime."""
from app.models import Ingredient
from app.services.derivation import (
    _seed_props,
    classify_and_derive,
    ingredient_columns,
    load_props,
    measure_to_grams,
)
from app.tests.conftest import requires_db

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


def test_load_props_falls_back_to_the_seed_file_without_a_session():
    props = load_props()
    assert "paneer" in props and "tofu" in props
    assert props["paneer"]["allergens"]  # non-empty (dairy)


@requires_db
def test_db_props_match_the_seed_file(session):
    # The migration backfilled from the seed file; derivation must read the same
    # values through either path or nutrition would shift under the refactor.
    seed, db = _seed_props(), load_props(session)
    assert set(seed) <= set(db)
    for name, want in seed.items():
        got = db[name]
        assert bool(want.get("vegan")) == got["vegan"], name
        assert bool(want.get("vegetarian")) == got["vegetarian"], name
        assert sorted(want.get("allergens") or []) == sorted(got["allergens"]), name


@requires_db
def test_seeded_ingredient_carries_every_property_derivation_reads(session):
    # The seeder and importer both build rows through ingredient_columns. If a
    # property is added to the seed file but not to that mapping, rows come out
    # with NULLs that read as "not vegan, no nutrition" instead of missing data.
    spec = _seed_props()["paneer"]
    session.add(Ingredient(**{**ingredient_columns(spec), "name": "test-paneer-copy"}))
    session.flush()
    try:
        got = load_props(session)["test-paneer-copy"]
        assert got["vegetarian"] is True and got["vegan"] is False
        assert "dairy" in got["allergens"]
        assert got["per_100g"].get("protein_g")
        assert got["grams_per_piece"], "gram weights must survive seeding"
    finally:
        session.rollback()


@requires_db
def test_an_ingredient_added_at_runtime_is_immediately_usable(session):
    # The point of moving properties into the table: a vocabulary entry created
    # while the app is running must carry nutrition and diet flags right away.
    # An lru_cache here would serve a snapshot taken before it existed.
    session.add(
        Ingredient(
            name="test-galangal", category="spice", aliases=[],
            vegetarian=True, vegan=True, allergens=[],
            per_100g={"calories": 71, "protein_g": 1.0, "carbs_g": 15.0, "fat_g": 0.5},
            default_unit="g", grams_per_unit=1, grams_per_piece=30,
        )
    )
    session.flush()
    try:
        props = load_props(session)
        assert "test-galangal" in props, "a new ingredient must appear without a restart"
        assert props["test-galangal"]["per_100g"]["protein_g"] == 1.0

        derived = classify_and_derive(
            props,
            [("test-galangal", 100.0, True), ("rice", 200.0, True)],
            ["test-galangal", "rice"],
            servings=2,
        )
        assert "vegan" in derived["diet_labels"]
        assert derived["nutrition"], "a new ingredient must contribute nutrition"
    finally:
        session.rollback()


# --------------------------------------------------------------------------- #
# Plant compounds vs real dairy
# --------------------------------------------------------------------------- #
_COCONUT_MILK = {"vegetarian": True, "vegan": True, "allergens": [],
                 "per_100g": {"calories": 230, "protein_g": 2.3, "carbs_g": 6, "fat_g": 24}}


def test_coconut_milk_does_not_make_a_recipe_non_vegan():
    # "coconut milk" contains the word "milk", and the keyword backstop split on
    # words — 386 recipes carried a dairy allergen for it and 341 lost vegan.
    props = {"coconut milk": _COCONUT_MILK, "rice": _RICE}
    d = classify_and_derive(
        props,
        [("coconut milk", 200.0, True), ("rice", 200.0, True)],
        ["coconut milk", "rice"],
        servings=2,
        title="Coconut Milk Rice",
    )
    assert "vegan" in d["diet_labels"]
    assert "dairy" not in d["allergens"]


def test_real_dairy_is_still_caught_alongside_a_plant_compound():
    # Only the qualified occurrence is neutralized; ordinary milk still trips.
    props = {"coconut milk": _COCONUT_MILK, "rice": _RICE}
    d = classify_and_derive(
        props, [("rice", 200.0, True)], ["coconut milk", "whole milk"], servings=2
    )
    assert "vegan" not in d["diet_labels"]
    assert "dairy" in d["allergens"]


def test_peanut_butter_keeps_its_peanut_allergen():
    # Blanking the whole phrase to kill the dairy reading also erased the nut
    # signal, which would have dropped peanuts from 257 recipes.
    props = {"rice": _RICE}
    d = classify_and_derive(
        props, [("rice", 200.0, True)], ["peanut butter", "rice"], servings=2
    )
    assert "peanuts" in d["allergens"]
    assert "dairy" not in d["allergens"]


def test_buttermilk_is_dairy():
    # One word, so neither "butter" nor "milk" matched it before.
    props = {"rice": _RICE}
    d = classify_and_derive(props, [("rice", 200.0, True)], ["buttermilk"], servings=2)
    assert "dairy" in d["allergens"]
    assert "vegan" not in d["diet_labels"]


def test_a_bare_count_is_pieces_not_cups():
    # grams_per_piece held the CUP weight for bulk items, so "10 peanuts"
    # resolved to ten cups: 1,460 g and a 2,381 kcal stuffed bitter gourd.
    props = {"peanuts": {"grams_per_piece": 0.5, "grams_per_cup": 146}}
    assert measure_to_grams(props, "peanuts", "10") == 5.0
    assert measure_to_grams(props, "peanuts", "1 cup") == 146.0


def test_a_line_with_no_measure_is_a_trace_not_a_whole_piece():
    # "Salt - to taste" reaches derivation as an empty measure: ingestion splits
    # on " - " and drops the qualifier. Reading the absent quantity as 1 priced
    # it as one whole piece of salt.
    props = {"salt": {"category": "spice", "grams_per_piece": 6.0}}
    grams = measure_to_grams(props, "salt", "")
    assert grams < 2.0
    assert grams != 6.0, "an absent quantity must not be read as one piece"


def test_trace_amounts_scale_by_category():
    # Same piece weight, different category: spices are pinches, but a bare
    # pantry line is oil or sugar and carries real calories.
    props = {
        "cumin": {"category": "spice", "grams_per_piece": 6.0},
        "vegetable oil": {"category": "pantry", "grams_per_piece": 6.0},
    }
    assert measure_to_grams(props, "cumin", "") < measure_to_grams(props, "vegetable oil", "")


def test_an_explicit_quantity_is_unaffected_by_the_trace_path():
    # Guards the _parse_qty change: only a measure with no digits at all may
    # take the trace path. "1" is a real count and must stay one piece.
    props = {"onion": {"category": "vegetable", "grams_per_piece": 110.0}}
    assert measure_to_grams(props, "onion", "1") == 110.0
    assert measure_to_grams(props, "onion", "2") == 220.0


def test_qualifier_measures_resolve_to_a_trace():
    props = {"coriander": {"category": "herb", "grams_per_piece": 20.0}}
    for measure in ("to taste", "a pinch", "a handful", "for garnish", "as needed"):
        assert measure_to_grams(props, "coriander", measure) <= 1.0, measure


def test_props_without_a_category_still_resolve():
    # Inline props in tests and any runtime vocabulary may omit category.
    assert measure_to_grams({"mystery": {}}, "mystery", "") > 0


def test_kilograms_of_food_on_one_plate_is_not_trusted():
    # "12" cauliflower means florets; read as twelve whole heads it is 7 kg for
    # two servings. The macro ceilings cannot catch this — cauliflower is 25
    # kcal/100 g, so the calories stay in range while the protein does not.
    props = {
        "cauliflower": {"category": "vegetable", "grams_per_piece": 600.0,
                        "per_100g": {"calories": 25, "protein_g": 1.9,
                                     "carbs_g": 5.0, "fat_g": 0.3}},
        "onion": {"category": "vegetable", "grams_per_piece": 110.0,
                  "per_100g": {"calories": 40, "protein_g": 1.1,
                               "carbs_g": 9.3, "fat_g": 0.1}},
    }
    items = [("cauliflower", 7200.0, True), ("onion", 110.0, False)]
    d = classify_and_derive(props, items, ["cauliflower", "onion"], servings=2)
    assert d["nutrition"] == {}, "kilograms per serving is a parse error, not a big dinner"

    # A normal plate of the same dish still reports.
    ok = classify_and_derive(
        props, [("cauliflower", 600.0, True), ("onion", 110.0, False)],
        ["cauliflower", "onion"], servings=2,
    )
    assert ok["nutrition"]["calories"] > 0


def test_litres_are_not_read_as_grams():
    # The litre branch shared the millilitre path and returned grams 1:1.
    props = {"milk": {"category": "dairy"}}
    assert measure_to_grams(props, "milk", "2 litre") == 2000.0
    assert measure_to_grams(props, "milk", "200 ml") == 200.0
