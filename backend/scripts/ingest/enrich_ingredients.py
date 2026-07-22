"""6.2b — grow the canonical vocabulary with haiku (cost-gated).

Feeds the top-N unmatched cores (from analyze.py) to Claude Haiku in batches and
gets back, per core: alias-of-existing / new-canonical (with nutrition) / skip.
Writes reviewable JSON; merge_ingredients.py folds it into ingredients.json.

Run from backend/ (needs ANTHROPIC_API_KEY):
  ../.venv/bin/python -m scripts.ingest.enrich_ingredients --sample      # 1 batch, print cost projection
  ../.venv/bin/python -m scripts.ingest.enrich_ingredients --limit 400   # full run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings  # noqa: E402
from app.core.allergens import ALLERGEN_VOCAB  # noqa: E402
from app.llm.client import get_llm  # noqa: E402

SEED = Path(__file__).resolve().parents[2] / "seed_data"
CATEGORIES = ["protein", "grain", "starch", "vegetable", "herb", "fruit",
              "dairy", "pantry", "sauce", "spice"]
ALLERGENS = list(ALLERGEN_VOCAB)
# Rough Haiku 4.5 pricing (USD per token) for the cost projection only.
PRICE_IN, PRICE_OUT = 1.0 / 1_000_000, 5.0 / 1_000_000


class Per100g(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class Enriched(BaseModel):
    core: str
    decision: Literal["alias", "new", "skip"]
    alias_of: Optional[str] = None       # exact existing canonical name (if alias)
    name: Optional[str] = None           # canonical name (if new)
    category: Optional[str] = None
    aliases: List[str] = []
    allergens: List[str] = []
    vegan: Optional[bool] = None
    vegetarian: Optional[bool] = None
    default_unit: Optional[str] = "g"
    grams_per_unit: Optional[float] = 1.0
    per_100g: Optional[Per100g] = None


class Batch(BaseModel):
    items: List[Enriched]


def _prompt(existing_names: list[str], cores: list[str]) -> list[dict]:
    system = (
        "You normalize raw recipe ingredient phrases into a canonical food "
        "database (Indian + world cuisine). For each phrase choose ONE:\n"
        "- alias: it's a form/variant/spelling of an EXISTING canonical -> set "
        "decision='alias', alias_of=<exact existing name>. Prefer this whenever "
        "reasonable (e.g. 'coriander leaves'->cilantro, 'curd'->yogurt, "
        "'badam'->almonds, 'wheat flour'->flour, 'green chillies'->green chili).\n"
        "- new: a genuinely new canonical -> decision='new' with name (lowercase "
        f"singular), category in {CATEGORIES}, aliases (other spellings incl. any "
        "Hindi/regional or transliterations), allergens (subset of "
        f"{ALLERGENS}), vegan, vegetarian, per_100g nutrition (calories, "
        "protein_g, carbs_g, fat_g — realistic per 100g), default_unit, "
        "grams_per_unit.\n"
        "- skip: not a real trackable ingredient (e.g. 'water', 'to taste', 'as "
        "required', 'oil' if too generic) -> decision='skip'.\n"
        "Echo the input phrase in 'core'. Be accurate on allergens/diet: ghee & "
        "paneer are dairy (vegetarian, not vegan); nuts set 'nuts'; sesame sets "
        "'sesame'."
    )
    user = (
        f"EXISTING canonical ingredients ({len(existing_names)}):\n"
        + ", ".join(existing_names)
        + "\n\nClassify each of these ingredient phrases:\n"
        + "\n".join(f"- {c}" for c in cores)
    )
    return [{"role": "user", "content": f"{system}\n\n{user}"}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=400, help="top-N unmatched cores")
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--sample", action="store_true", help="1 batch only, print cost projection")
    args = ap.parse_args()

    if not settings.ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set (needed for 6.2b enrichment).")

    existing = json.load(open(SEED / "ingredients.json"))
    existing_names = [i["name"] for i in existing]
    existing_set = {n.lower() for n in existing_names}
    cores = [c["core"] for c in json.load(open(SEED / "unmatched_cores.json"))][: args.limit]

    client = get_llm().raw()
    batches = [cores[i:i + args.batch] for i in range(0, len(cores), args.batch)]
    if args.sample:
        batches = batches[:1]

    results: list[Enriched] = []
    tok_in = tok_out = 0
    import anthropic
    for bi, batch in enumerate(batches):
        try:
            resp = client.messages.parse(
                model=settings.LLM_MODEL_FAST,
                max_tokens=4096,
                messages=_prompt(existing_names, batch),
                output_format=Batch,
            )
        except anthropic.APIError as e:
            print(f"  batch {bi} failed: {e}")
            continue
        tok_in += resp.usage.input_tokens
        tok_out += resp.usage.output_tokens
        if resp.parsed_output:
            results.extend(resp.parsed_output.items)
        print(f"  batch {bi+1}/{len(batches)}: {len(batch)} cores "
              f"(in={resp.usage.input_tokens} out={resp.usage.output_tokens})")

    n_alias = sum(1 for r in results if r.decision == "alias")
    n_new = sum(1 for r in results if r.decision == "new")
    n_skip = sum(1 for r in results if r.decision == "skip")
    cost = tok_in * PRICE_IN + tok_out * PRICE_OUT
    print(f"\nclassified {len(results)}: alias={n_alias} new={n_new} skip={n_skip}")
    print(f"tokens: in={tok_in} out={tok_out}  cost≈${cost:.4f}")

    if args.sample:
        full_cost = cost * (len(cores) / max(1, len(batches[0])) / (len(cores) / args.batch))
        proj = cost * ((len(cores) / args.batch) / len(batches))
        print(f"\nPROJECTED full run ({len(cores)} cores, "
              f"{-(-len(cores)//args.batch)} batches): ≈${proj:.3f}")
        return

    out = SEED / "ingredients_enriched.json"
    out.write_text(json.dumps([r.model_dump() for r in results], ensure_ascii=False, indent=1))
    # Sanity: aliases must point at a real existing canonical.
    bad = [r.core for r in results if r.decision == "alias" and (r.alias_of or "").lower() not in existing_set]
    if bad:
        print(f"WARNING: {len(bad)} aliases point at unknown canonical (first 5): {bad[:5]}")
    print(f"wrote {len(results)} entries -> {out}")


if __name__ == "__main__":
    main()
