"""Persistent pantry endpoints (Stage 5): GET/PUT /v1/pantry.

Keyed by the authed identity (`get_current_user_key`): in disabled mode that's
the `X-User-Key` header; in jwt mode it's `google:{sub}` from the verified token.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.schemas.pantry import PantryReplaceIn, PantryResponse
from app.services.pantry import get_pantry, replace_pantry

router = APIRouter(prefix="/v1", tags=["pantry"])


@router.get("/pantry", response_model=PantryResponse)
def read_pantry(
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    return PantryResponse(items=get_pantry(session, user_key))


@router.put("/pantry", response_model=PantryResponse)
def write_pantry(
    body: PantryReplaceIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    items, unmatched = replace_pantry(session, user_key, body.items)
    return PantryResponse(items=items, unmatched=unmatched)
