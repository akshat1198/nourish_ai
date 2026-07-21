"""Backfill ingredient canonicalization (root-cause fix for sparse mapping).

Ingestion mapped source ingredient names to canonical ones by exact name/alias
only, silently dropping the rest — so ~90% of the scraped corpus lost ingredients
(a paneer dish labelled "cheese" showed 1.9 g protein). This backfill:

  --map [--limit N]   LLM-map the top-N unmapped source names to the best EXISTING
                      canonical (cheese→paneer, sunflower oil→vegetable oil,
                      rajma→kidney beans, नमक→salt, …). Adds them as aliases in
                      ingredients.json + writes a review file. Re-runnable.
  --apply             Merge the vocab into the DB, then re-link recipe_ingredients
                      from each recipe's display list and re-derive
                      nutrition/diet/allergen. Deterministic + idempotent
                      (safe to stop/restart); search_text is untouched so
                      embeddings stay valid. Skips the 'seed' baseline.

Run from backend/ (LLM key required for --map).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.llm.client import LLMError, get_llm, is_enabled  # noqa: E402
from app.models import Recipe, RecipeIngredient  # noqa: E402
from app.services.derivation import classify_and_derive, load_props, measure_to_grams  # noqa: E402
from app.services.ingredients import normalize  # noqa: E402
from scripts.ingest.normalize import CanonicalMatcher  # noqa: E402
from scripts.ingest.pipeline import ensure_ingredients_in_db  # noqa: E402

SEED = Path(__file__).resolve().parents[1] / "seed_data"
INGREDIENTS = SEED / "ingredients.json"
BACKFILL = SEED / "ingredient_backfill.json"

BATCH = 20

_MAP_SYSTEM = (
    "You map messy source recipe-ingredient names to a fixed list of canonical "
    "ingredients. For each source name, pick the SINGLE best canonical from the "
    "provided list — the same ingredient, or an acceptable nutritional stand-in "
    "(e.g. 'sunflower oil'→'vegetable oil'). Handle Hindi/Devanagari (नमक→salt, "
    "तेल→oil→'vegetable oil', हल्दी→turmeric). In Indian recipes 'cheese' means "
    "'paneer'. Common: rajma→kidney beans, masoor dal→lentils, curd/dahi→yogurt. "
    "Return \"\" (empty) when it's NOT a real food ingredient (water, ice, ENO) or "
    "no listed canonical is a reasonable match. Only use canonicals from the list."
)


class NameMap(BaseModel):
    source: str
    canonical: str = Field("", description="An EXACT canonical from the list, or \"\"")


class NameMaps(BaseModel):
    mappings: list[NameMap] = Field(default_factory=list)


def _load() -> list[dict]:
    return json.loads(INGREDIENTS.read_text())


def _display_counter(session) -> Counter:
    counter: Counter = Counter()
    for (ings,) in session.execute(select(Recipe.ingredients)):
        for it in ings or []:
            n = (it.get("name") or "").strip()
            if n:
                counter[n] += 1
    return counter


def _llm_map(sources: list[str], canon_names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    valid = set(canon_names)
    for i in range(0, len(sources), BATCH):
        chunk = sources[i : i + BATCH]
        prompt = (
            f"{_MAP_SYSTEM}\n\nCanonical ingredients (choose only from these):\n"
            f"{', '.join(canon_names)}\n\nSource names to map:\n"
            + "\n".join(f"- {s}" for s in chunk)
        )
        try:
            res = get_llm().generate_structured(
                messages=[{"role": "user", "content": prompt}],
                schema=NameMaps,
                model=settings.LLM_MODEL_MAIN,
                max_tokens=4000,
            )
        except LLMError as e:
            print(f"  ! batch {i // BATCH} failed: {e}")
            continue
        for m in res.mappings:
            c = m.canonical.strip()
            out[m.source] = c if c in valid else ""
        print(f"  mapped batch {i // BATCH + 1}/{-(-len(sources) // BATCH)}")
    return out


def cmd_map(limit: int) -> None:
    if not is_enabled():
        print("ANTHROPIC_API_KEY not set — cannot map.")
        sys.exit(1)
    ings = _load()
    matcher = CanonicalMatcher(ings)
    with SessionLocal() as s:
        counter = _display_counter(s)
    unmapped = Counter({n: c for n, c in counter.items() if matcher.match(n) is None})
    top = [n for n, _ in unmapped.most_common(limit)]
    print(f"{len(unmapped)} distinct unmapped names; mapping the top {len(top)} "
          f"(covering {sum(unmapped[n] for n in top)} of {sum(unmapped.values())} lines)")

    canon_names = [i["name"] for i in ings]
    canon_norm = {normalize(n) for n in canon_names}
    mapping = _llm_map(top, canon_names)

    by_name = {i["name"]: i for i in ings}
    added = 0
    skipped: list[str] = []
    for src, canon in mapping.items():
        if not canon or canon not in by_name or normalize(src) in canon_norm:
            skipped.append(src)
            continue
        aliases = by_name[canon].setdefault("aliases", [])
        if normalize(src) not in {normalize(a) for a in aliases}:
            aliases.append(src)
            added += 1
    INGREDIENTS.write_text(json.dumps(ings, ensure_ascii=False, indent=2) + "\n")
    BACKFILL.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    print(f"\nAdded {added} aliases across the vocab; {len(skipped)} left unmapped.")
    print("Sample mappings:")
    for src, canon in list(mapping.items())[:30]:
        print(f"  {src!r:32} -> {canon or '(none)'}")


def cmd_apply(limit: int) -> None:
    props = load_props()
    ings = _load()
    matcher = CanonicalMatcher(ings)
    with SessionLocal() as s:
        name_to_id = ensure_ingredients_in_db(s)
        s.commit()
        q = select(Recipe).where(Recipe.source != "seed").order_by(Recipe.id)
        recipes = list(s.execute(q).scalars())
        if limit:
            recipes = recipes[:limit]
        print(f"re-linking + re-deriving {len(recipes)} recipes…")

        relinked = renutri = 0
        for n, r in enumerate(recipes, 1):
            matched_for_derive: list[tuple] = []
            new_ri: list[tuple] = []
            seen: set[int] = set()
            for line in r.ingredients or []:
                canon = matcher.match(line.get("name", ""))
                if not canon:
                    continue
                iid = name_to_id.get(canon)
                if iid is None or iid in seen:
                    continue
                seen.add(iid)
                qty, unit = line.get("qty"), line.get("unit")
                essential = line.get("essential", True)
                new_ri.append((iid, qty, unit, essential))
                measure = f"{qty if qty is not None else ''} {unit or ''}".strip()
                grams = measure_to_grams(props, canon, measure)
                matched_for_derive.append((canon, grams, essential))

            s.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id == r.id))
            for iid, qty, unit, essential in new_ri:
                s.add(RecipeIngredient(recipe_id=r.id, ingredient_id=iid,
                                       qty=qty, unit=unit, essential=essential))
            relinked += 1

            raw_names = [l.get("name", "") for l in (r.ingredients or [])]
            derived = classify_and_derive(
                props, matched_for_derive, raw_names, servings=r.servings, title=r.title
            )
            r.allergens = derived["allergens"]
            r.diet_labels = derived["diet_labels"]
            if derived["nutrition"]:  # only overwrite when we can compute it
                r.nutrition = derived["nutrition"]
                r.nutrition_estimated = True
                renutri += 1

            if n % 200 == 0:
                s.commit()
                print(f"  {n}/{len(recipes)}…")
        s.commit()
        print(f"done. re-linked={relinked}, nutrition recomputed={renutri}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", action="store_true", help="LLM-map top unmapped names to aliases")
    ap.add_argument("--apply", action="store_true", help="re-link + re-derive the corpus")
    ap.add_argument("--limit", type=int, default=200,
                    help="--map: top-N names; --apply: max recipes (0=all)")
    args = ap.parse_args()
    if args.map:
        cmd_map(args.limit)
    elif args.apply:
        cmd_apply(args.limit if args.limit != 200 else 0)
    else:
        ap.error("pass --map or --apply")


if __name__ == "__main__":
    main()
