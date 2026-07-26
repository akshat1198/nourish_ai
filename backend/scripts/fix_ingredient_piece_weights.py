"""Give every ingredient a weight for a bare, unit-less quantity.

`grams_per_unit` means "grams per the ingredient's default_unit", and for the
211 entries whose default_unit is "g"/"ml" that value is 1 — correct as
grams-per-gram, useless as a fallback. But a third of the corpus's ingredient
lines carry no unit at all ("3 chicken breast", "1 onion"), and
measure_to_grams falls back to grams_per_unit for those, so three chicken
breasts resolved to 3 g instead of ~510 g. Every recipe with a piece-counted
protein or vegetable therefore reported a fraction of its real nutrition.

This adds `grams_per_piece`: what one bare unit of this ingredient weighs.
For countable things that is one piece (a chicken breast, an onion). For bulk
things a bare number in a recipe overwhelmingly means one cup, so it is the
cup weight — which also fixes solids being measured as 240 g/cup like water
(rice is ~185 g, flour ~120 g).

Values are hand-authored from standard food references. They are estimates:
nutrition here is explicitly an estimate (`nutrition_estimated`), and being
within ~10% is the difference between a usable filter and a useless one.

Run from backend/:
  ../.venv/bin/python -m scripts.fix_ingredient_piece_weights --dry
  ../.venv/bin/python -m scripts.fix_ingredient_piece_weights
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "seed_data" / "ingredients.json"

# One bare unit, in grams. Countable -> one piece; bulk -> one cup.
PIECE_GRAMS: dict[str, float] = {
    # --- protein: cuts and blocks are counted by the piece ---------------
    "chicken breast": 170, "chicken thigh": 110, "beef sirloin": 200,
    "pork loin": 180, "mutton": 150, "turkey": 150, "salmon": 150,
    "cod": 140, "tuna": 140, "shrimp": 15, "tofu": 400, "tempeh": 200,
    "paneer": 200, "egg yolk": 17,
    # legumes are bulk (one cup, dry)
    "lentils": 200, "chickpeas": 200, "black beans": 200, "kidney beans": 200,
    "black chickpeas": 200, "black eyed peas": 200, "urad dal": 200,
    "moong dal": 200, "arhar dal": 200, "roasted lentils": 200,
    "soy chunks": 60, "pistachios": 125,
    # --- vegetables ------------------------------------------------------
    "broccoli": 350, "cabbage": 900, "cauliflower": 600, "corn": 100,
    "ginger": 30, "green chili": 5, "leek": 90, "lettuce": 300,
    "mushroom": 20, "okra": 10, "pearl onion": 10, "radish": 50,
    "shallot": 30, "beetroot": 120, "bitter melon": 100, "bottle gourd": 500,
    "pumpkin": 500, "drumstick": 40, "baby corn": 10, "tindora": 15,
    "cluster beans": 5, "peas": 145, "spinach": 100, "kale": 65,
    "amaranth leaves": 100, "drumstick leaves": 50, "mung sprouts": 105,
    "sun dried tomatoes": 3, "pickled jalapeños": 5,
    # --- starch ----------------------------------------------------------
    "potatoes": 150, "sweet potato": 150, "elephant yam": 200, "sabudana": 180,
    # --- fruit -----------------------------------------------------------
    "apple": 180, "orange": 130, "mango": 200, "raw banana": 120, "kiwi": 75,
    "papaya": 500, "pineapple": 900, "watermelon": 280, "coconut": 400,
    "strawberry": 12, "blueberries": 150, "cranberries": 110, "raisins": 145,
    "date": 8, "dried figs": 20, "apricots": 35, "amla": 10, "jackfruit": 150,
    "kokum": 2, "pomegranate arils": 175, "mango pulp": 240, "orange juice": 240,
    # --- dairy -----------------------------------------------------------
    "butter": 113, "cheddar": 110, "mozzarella": 110, "parmesan": 100,
    "feta": 150, "cream cheese": 230, "ricotta": 250, "greek yogurt": 245,
    "ghee": 13, "khoya": 100, "condensed milk": 306,
    "processed cheese spread": 20, "milk": 240, "heavy cream": 240,
    "buttermilk": 245,
    # --- grain: a bare number means a cup --------------------------------
    "rice": 185, "basmati rice": 185, "brown rice": 190, "arborio rice": 200,
    "matta rice": 190, "idli rice": 185, "flour": 120, "vivatta maida": 120,
    "rice flour": 158, "chickpea flour": 92, "bajra flour": 120,
    "ragi flour": 120, "cornmeal flour": 122, "semolina": 167, "oats": 90,
    "quinoa": 170, "couscous": 173, "pasta": 100, "egg noodles": 100,
    "rice noodles": 100, "hakka noodles": 100, "vermicelli": 80, "poha": 80,
    "puffed rice": 15, "muesli": 85, "rye": 130, "barnyard millet": 180,
    "green moong dal": 200, "chana dal": 200, "idli dosa batter": 240,
    # --- pantry ----------------------------------------------------------
    "almonds": 143, "cashews": 137, "peanuts": 146, "walnuts": 117,
    "chia seeds": 12, "flax seeds": 10, "flax seed powder": 10,
    "melon seeds": 10, "sunflower seeds": 12, "fox nuts": 10,
    "desiccated coconut": 80, "chicken broth": 240, "vegetable broth": 240,
    "coconut milk": 240, "canned tomatoes": 400, "black olives": 135,
    "chocolate chips": 170, "dark chocolate": 100, "cocoa powder": 85,
    "icing sugar": 120, "jaggery": 20, "palm sugar": 15, "tamarind": 20,
    "vanilla extract": 4, "rose water": 5, "apple cider vinegar": 15,
    "mustard oil": 14, "coconut oil": 14, "ginger garlic paste": 15,
    "green chilli paste": 15, "boondi": 30, "sev": 30, "baking powder": 4,
    "baking soda": 4, "active dry yeast": 7, "custard powder": 8,
    "black salt": 6,
    # --- sauces: a bare number means a tablespoon ------------------------
    "dijon mustard": 15, "fish sauce": 18, "green chilli sauce": 15,
    "green chutney": 30, "roasted tomato pasta sauce": 240, "sriracha": 15,
    "sweet chutney": 30, "tomato ketchup": 17, "tomato puree": 240,
    # --- herbs: a bare number means a handful/sprig ----------------------
    "basil": 5, "bay leaf": 0.2, "cilantro": 5, "curry leaves": 1, "dill": 5,
    "dried rose petals": 1, "kasuri methi": 2, "methi leaves": 20, "mint": 5,
    "mixed herbs": 2, "parsley": 5, "rosemary": 2,
    # --- spices: a bare number means a teaspoon; whole spices, a piece ---
    "ajwain": 3, "amchur": 3, "anardana powder": 3, "asafoetida": 1,
    "black cardamom": 1, "cardamom": 0.5, "chaat masala": 3, "cinnamon": 3,
    "cinnamon stick": 2, "clove": 0.1, "coriander powder": 3,
    "dry ginger powder": 3, "dry red chilli": 1, "fennel seeds": 3,
    "fenugreek": 3, "fenugreek seeds": 3, "garam masala": 3, "goda masala": 3,
    "kalonji": 3, "kashmiri red chilli powder": 3, "mace": 1,
    "mustard seeds": 3, "nutmeg powder": 2, "panch phoran": 3,
    "pav bhaji masala": 3, "poppy seeds": 3, "rasam powder": 3,
    "red chili powder": 3, "red chilli powder": 3, "sambar powder": 3,
    "sesame seeds": 3, "star anise": 1, "stone flower": 1, "turmeric": 3,
    "white pepper": 2,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    data = json.loads(SEED.read_text())
    known = {i["name"] for i in data}

    unknown = sorted(set(PIECE_GRAMS) - known)
    if unknown:
        print(f"WARNING: {len(unknown)} names not in the vocabulary: {unknown}")

    updated = 0
    missing: list[str] = []
    for ing in data:
        name = ing["name"]
        if name in PIECE_GRAMS:
            ing["grams_per_piece"] = PIECE_GRAMS[name]
            updated += 1
        elif ing.get("grams_per_unit"):
            # default_unit is already a real unit (unit/tbsp/tsp/cup/slice/
            # clove/stalk), so its grams_per_unit IS the bare-unit weight.
            ing["grams_per_piece"] = ing["grams_per_unit"]
            updated += 1
        else:
            missing.append(name)

    print(f"grams_per_piece set on {updated}/{len(data)} ingredients")
    if missing:
        print(f"no weight for {len(missing)}: {missing}")

    if not args.dry:
        SEED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {SEED}")
    else:
        print("(dry run, nothing written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
