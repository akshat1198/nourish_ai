"""Meal-plan persistence + combined shopping list.

Owner-scoped: every mutating/reading helper takes `user_key` and returns None /
False when the plan isn't the caller's, so the API can 404 without leaking that
a plan id exists.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import MealPlan, MealPlanItem, Recipe
from app.schemas.saved import (
    PlanItemOut,
    PlanOut,
    PlanSummaryOut,
)
from app.schemas.shopping import ShoppingListResponse
from app.services.pantry import get_pantry
from app.services.saved import recipe_summary
from app.services.shopping import build_shopping_list


def _owned(session: Session, user_key: str, plan_id: int) -> Optional[MealPlan]:
    plan = session.get(MealPlan, plan_id)
    return plan if plan is not None and plan.user_key == user_key else None


def list_plans(session: Session, user_key: str) -> list[PlanSummaryOut]:
    plans = (
        session.execute(
            select(MealPlan)
            .where(MealPlan.user_key == user_key)
            .order_by(MealPlan.created_at.desc())
        )
        .scalars()
        .all()
    )
    if not plans:
        return []
    counts = dict(
        session.execute(
            select(MealPlanItem.plan_id, func.count())
            .where(MealPlanItem.plan_id.in_([p.id for p in plans]))
            .group_by(MealPlanItem.plan_id)
        ).all()
    )
    return [
        PlanSummaryOut(
            id=p.id,
            name=p.name,
            item_count=counts.get(p.id, 0),
            created_at=p.created_at,
        )
        for p in plans
    ]


def create_plan(session: Session, user_key: str, name: str) -> MealPlan:
    plan = MealPlan(user_key=user_key, name=name)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def get_plan(session: Session, user_key: str, plan_id: int) -> Optional[PlanOut]:
    plan = _owned(session, user_key, plan_id)
    if plan is None:
        return None
    rows = session.execute(
        select(MealPlanItem, Recipe)
        .join(Recipe, Recipe.id == MealPlanItem.recipe_id)
        .where(MealPlanItem.plan_id == plan_id)
        .order_by(MealPlanItem.created_at.asc())
    ).all()
    return PlanOut(
        id=plan.id,
        name=plan.name,
        created_at=plan.created_at,
        items=[PlanItemOut(recipe=recipe_summary(r), slot=mi.slot) for mi, r in rows],
    )


def delete_plan(session: Session, user_key: str, plan_id: int) -> bool:
    plan = _owned(session, user_key, plan_id)
    if plan is None:
        return False
    session.delete(plan)
    session.commit()
    return True


def add_item(
    session: Session, user_key: str, plan_id: int, recipe_id: int, slot: Optional[str]
) -> bool:
    if _owned(session, user_key, plan_id) is None:
        return False
    # Re-adding a recipe updates its slot rather than erroring (unique on pair).
    session.execute(
        pg_insert(MealPlanItem)
        .values(plan_id=plan_id, recipe_id=recipe_id, slot=slot)
        .on_conflict_do_update(constraint="uq_plan_recipe", set_={"slot": slot})
    )
    session.commit()
    return True


def remove_item(session: Session, user_key: str, plan_id: int, recipe_id: int) -> bool:
    if _owned(session, user_key, plan_id) is None:
        return False
    session.execute(
        delete(MealPlanItem).where(
            MealPlanItem.plan_id == plan_id, MealPlanItem.recipe_id == recipe_id
        )
    )
    session.commit()
    return True


def plan_shopping_list(
    session: Session, user_key: str, plan_id: int
) -> Optional[ShoppingListResponse]:
    """Combined shopping list over the plan's recipes, minus the user's pantry."""
    if _owned(session, user_key, plan_id) is None:
        return None
    recipe_ids = list(
        session.execute(
            select(MealPlanItem.recipe_id).where(MealPlanItem.plan_id == plan_id)
        ).scalars()
    )
    pantry = [i.ingredient for i in get_pantry(session, user_key)]
    return build_shopping_list(session, recipe_ids, pantry)
