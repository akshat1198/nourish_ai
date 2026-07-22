"""Meal-plan endpoints. Owner-scoped; non-owner access → 404."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.models import Recipe
from app.schemas.saved import (
    PlanCreateIn,
    PlanItemIn,
    PlanListOut,
    PlanOut,
)
from app.schemas.shopping import ShoppingListResponse
from app.services.plans import (
    add_item,
    create_plan,
    delete_plan,
    get_plan,
    list_plans,
    plan_shopping_list,
    remove_item,
)

router = APIRouter(prefix="/v1", tags=["plans"])


@router.get("/plans", response_model=PlanListOut)
def get_plans(
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    return PlanListOut(plans=list_plans(session, user_key))


@router.post("/plans", response_model=PlanOut)
def post_plan(
    body: PlanCreateIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    plan = create_plan(session, user_key, body.name)
    return PlanOut(id=plan.id, name=plan.name, created_at=plan.created_at, items=[])


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_one_plan(
    plan_id: int,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    plan = get_plan(session, user_key, plan_id)
    if plan is None:
        raise HTTPException(404, "plan not found")
    return plan


@router.delete("/plans/{plan_id}")
def remove_plan(
    plan_id: int,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    if not delete_plan(session, user_key, plan_id):
        raise HTTPException(404, "plan not found")
    return {"ok": True}


@router.post("/plans/{plan_id}/items", response_model=PlanOut)
def add_plan_item(
    plan_id: int,
    body: PlanItemIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    if session.get(Recipe, body.recipe_id) is None:
        raise HTTPException(404, "recipe not found")
    if not add_item(session, user_key, plan_id, body.recipe_id, body.slot):
        raise HTTPException(404, "plan not found")
    return get_plan(session, user_key, plan_id)


@router.delete("/plans/{plan_id}/items/{recipe_id}", response_model=PlanOut)
def remove_plan_item(
    plan_id: int,
    recipe_id: int,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    if not remove_item(session, user_key, plan_id, recipe_id):
        raise HTTPException(404, "plan not found")
    return get_plan(session, user_key, plan_id)


@router.get("/plans/{plan_id}/shopping-list", response_model=ShoppingListResponse)
def plan_shopping(
    plan_id: int,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    result = plan_shopping_list(session, user_key, plan_id)
    if result is None:
        raise HTTPException(404, "plan not found")
    return result
