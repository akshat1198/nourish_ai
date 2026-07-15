"""Shared eval utilities: case loading, title resolution, retrieval metrics."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Recipe

EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "seed_data" / "eval"
QUERIES_PATH = EVAL_DIR / "queries.jsonl"
QUERIES_ADVERSARIAL_PATH = EVAL_DIR / "queries_adversarial.jsonl"
QUERIES_FUZZY_PATH = EVAL_DIR / "fuzzy_queries.jsonl"
QUERIES_REGIONAL_PATH = EVAL_DIR / "queries_regional.jsonl"  # Stage 6.3 regional-Indian

# Named suites the agent eval can run (--suite).
SUITES = {"gold": QUERIES_PATH, "adversarial": QUERIES_ADVERSARIAL_PATH}


@dataclass
class EvalCase:
    name: str
    pantry: list[str]
    diet: str | None
    exclude_allergens: list[str]
    max_time_minutes: int | None
    relevant_titles: list[str]
    # Adversarial fields (Stage 4.4): retrieval can't hard-filter a disliked
    # ingredient, but the validator flags it — so these drive the repair loop.
    disliked_ingredients: list[str] = field(default_factory=list)
    question: str | None = None
    # Stage 6.3: regional-cuisine + meal-type gold cases exercise those filters.
    cuisines: list[str] = field(default_factory=list)
    meal_type: str | None = None


def load_cases(path: Path = QUERIES_PATH) -> list[EvalCase]:
    cases = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        cases.append(
            EvalCase(
                name=d["name"],
                pantry=d["pantry"],
                diet=d.get("diet"),
                exclude_allergens=d.get("exclude_allergens", []),
                max_time_minutes=d.get("max_time_minutes"),
                relevant_titles=d.get("relevant_titles", []),
                disliked_ingredients=d.get("disliked_ingredients", []),
                question=d.get("question"),
                cuisines=d.get("cuisines", []),
                meal_type=d.get("meal_type"),
            )
        )
    return cases


def title_id_map(session: Session) -> dict[str, int]:
    rows = session.execute(select(Recipe.title, Recipe.id)).all()
    return {title: rid for title, rid in rows}


@dataclass
class Metrics:
    n: int = 0
    hit5: int = 0
    hit10: int = 0
    mrr_sum: float = 0.0
    constraint_violations: int = 0
    missing_gold: list[str] = field(default_factory=list)  # cases with unresolved titles

    def add_case(self, ranked_ids: list[int], relevant_ids: set[int]):
        self.n += 1
        top5, top10 = ranked_ids[:5], ranked_ids[:10]
        if relevant_ids & set(top5):
            self.hit5 += 1
        if relevant_ids & set(top10):
            self.hit10 += 1
        for rank, rid in enumerate(top10, start=1):
            if rid in relevant_ids:
                self.mrr_sum += 1.0 / rank
                break

    def summary(self) -> dict:
        return {
            "cases": self.n,
            "hit@5": round(self.hit5 / self.n, 4) if self.n else 0.0,
            "hit@10": round(self.hit10 / self.n, 4) if self.n else 0.0,
            "MRR": round(self.mrr_sum / self.n, 4) if self.n else 0.0,
            "constraint_violations": self.constraint_violations,
        }


def count_violations(recipe, case: EvalCase) -> int:
    """Hard-constraint violations for a single returned recipe."""
    v = 0
    if case.diet and case.diet not in recipe.diet_labels:
        v += 1
    if set(case.exclude_allergens) & set(recipe.allergens):
        v += 1
    if case.max_time_minutes is not None and recipe.time_minutes > case.max_time_minutes:
        v += 1
    return v
