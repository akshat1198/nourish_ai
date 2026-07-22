"""Online analytics: event capture + per-variant experiment summary (Stage 13).

There's a single active experiment at a time (Stage 13.2's EXPERIMENT_NAME), so
events don't carry an experiment column — `experiment_summary` aggregates over
every event carrying a non-null `variant` and echoes the requested name back
for labeling. Simplest correct thing per the current one-experiment model.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event
from app.schemas.event import EventIn, ExperimentSummaryOut, VariantStat


def record_event(session: Session, user_key: str, body: EventIn) -> None:
    session.add(
        Event(
            user_key=user_key,
            session_id=body.session_id,
            name=body.name,
            recipe_id=body.recipe_id,
            variant=body.variant,
            props=body.props,
        )
    )
    session.commit()


def experiment_summary(session: Session, name: str) -> ExperimentSummaryOut:
    rows = session.execute(
        select(Event.variant, Event.name).where(Event.variant.isnot(None))
    ).all()

    by_variant: dict[str, dict[str, int]] = {}
    for variant, event_name in rows:
        counts = by_variant.setdefault(variant, {})
        counts[event_name] = counts.get(event_name, 0) + 1

    variants = [
        VariantStat(variant=v, count=sum(counts.values()), by_name=counts)
        for v, counts in sorted(by_variant.items())
    ]
    return ExperimentSummaryOut(
        experiment=name, total=len(rows), variants=variants
    )
