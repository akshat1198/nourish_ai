"""Split each ingredient's cup weight from its single-piece weight.

`grams_per_piece` was seeded with the CUP weight for bulk items, on the
assumption that a bare number means a cup ("2 rice" -> 2 cups). That holds for
grains and flours but not for anything countable and small: a recipe asking for
10 peanuts resolved to ten cups, 1,460 g, and pushed one dish to 2,381 kcal a
serving.

So: `grams_per_cup` is the cup weight, `grams_per_piece` is one piece. They stay
equal wherever a bare number really does mean a cup.

Run from backend/:
  ../.venv/bin/python -m scripts.fix_piece_vs_cup_weights --dry
  ../.venv/bin/python -m scripts.fix_piece_vs_cup_weights
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "seed_data" / "ingredients.json"

# name -> weight of ONE piece, for things a recipe counts individually. Their
# existing grams_per_piece (a cup weight) becomes grams_per_cup.
PIECE_GRAMS: dict[str, float] = {
    # nuts and seeds — counted by the nut far more often than by the cup
    "peanuts": 0.5, "almonds": 1.2, "cashews": 1.5, "walnuts": 2.5,
    "pistachios": 0.7, "fox nuts": 0.3,
    # dried and fresh fruit
    "raisins": 0.5, "cranberries": 0.4, "blueberries": 0.5, "strawberry": 12,
    "dried figs": 20, "apricots": 35, "date": 8, "pomegranate arils": 0.3,
    # small savoury items
    "black olives": 4, "chocolate chips": 0.5, "baby corn": 10,
    "cluster beans": 5, "sun dried tomatoes": 3, "pickled jalapeños": 5,
    "green chili": 5, "pearl onion": 10, "okra": 10, "mushroom": 20,
    "shrimp": 15, "curry leaves": 0.1, "dry red chilli": 1, "cardamom": 0.5,
    "clove": 0.1, "star anise": 1, "bay leaf": 0.2, "cinnamon stick": 2,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    data = json.loads(SEED.read_text())
    known = {i["name"] for i in data}
    unknown = sorted(set(PIECE_GRAMS) - known)
    if unknown:
        print(f"WARNING: not in vocabulary: {unknown}")

    split = 0
    for ing in data:
        # Whatever grams_per_piece held was the cup weight for bulk items and
        # the piece weight for countable ones; either way it is the right cup
        # figure for the cup path, which previously read the same field.
        ing["grams_per_cup"] = ing.get("grams_per_piece")
        piece = PIECE_GRAMS.get(ing["name"])
        if piece is not None:
            ing["grams_per_piece"] = piece
            split += 1

    print(f"{split} ingredients now have a piece weight distinct from their cup weight")
    if args.dry:
        print("(dry run, nothing written)")
        return 0
    SEED.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {SEED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
