"""Dry-run analysis for Archana's ingestion (6.2). No writes, no LLM.

Reports: ingredient match rate with the real parser/matcher, taxonomy-mapping
coverage, and the frequency-ranked unmatched cores that 6.2b will enrich.

Run from backend/:  ../.venv/bin/python -m scripts.ingest.analyze [csv_path]
"""
from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ingest.normalize import CanonicalMatcher, parse_ingredient_line  # noqa: E402
from scripts.ingest.taxonomy_maps import (  # noqa: E402
    map_cuisine,
    map_course,
    map_diet_seed,
)

csv.field_size_limit(10**7)
CSV = sys.argv[1] if len(sys.argv) > 1 else "/Applications/NourishAI/nourish_ai/archana_dataset.csv"
INGJSON = Path(__file__).resolve().parents[2] / "seed_data" / "ingredients.json"


def main() -> None:
    matcher = CanonicalMatcher(json.load(open(INGJSON)))
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))

    line_total = line_matched = 0
    unmatched = collections.Counter()
    per_recipe = []
    cuisine_hit = region_hit = 0

    for r in rows:
        field = (r.get("TranslatedIngredients") or "").strip()
        lines = [x for x in field.split(",") if x.strip()]
        if not lines:
            continue
        m = 0
        for ln in lines:
            core = parse_ingredient_line(ln).core
            if not core:
                continue
            line_total += 1
            if matcher.match(core):
                line_matched += 1
                m += 1
            else:
                unmatched[core] += 1
        per_recipe.append(m / len(lines))
        top, region = map_cuisine(r.get("Cuisine", ""))
        cuisine_hit += top is not None
        region_hit += region is not None

    n = len(per_recipe)
    print(f"recipes: {n}   ingredient lines: {line_total}")
    print(f"lines matched: {line_matched} ({100*line_matched/line_total:.1f}%)")
    print(f"mean per-recipe match: {100*sum(per_recipe)/n:.1f}%")
    print(f"recipes >=70% matched: {sum(1 for p in per_recipe if p>=.7)} "
          f"({100*sum(1 for p in per_recipe if p>=.7)/n:.0f}%)")
    print(f"cuisine mapped (non-null): {cuisine_hit} ({100*cuisine_hit/n:.0f}%);  "
          f"with region: {region_hit} ({100*region_hit/n:.0f}%)")

    print(f"\ndistinct unmatched cores: {len(unmatched)}; "
          f"total unmatched volume: {sum(unmatched.values())}")
    for N in (150, 300, 500):
        covered = sum(c for _, c in unmatched.most_common(N))
        print(f"  top {N} distinct cover {100*covered/sum(unmatched.values()):.0f}% of miss volume")

    # Emit the ranked unmatched list for the 6.2b enrichment step.
    out = Path(__file__).resolve().parents[2] / "seed_data" / "unmatched_cores.json"
    ranked = [{"core": c, "count": ct} for c, ct in unmatched.most_common()]
    out.write_text(json.dumps(ranked, ensure_ascii=False, indent=0))
    print(f"\nwrote {len(ranked)} ranked unmatched cores -> {out}")


if __name__ == "__main__":
    main()
