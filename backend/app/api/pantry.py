"""Persistent pantry endpoints: GET/PUT /v1/pantry, plus photo intake.

Keyed by the authed identity (`get_current_user_key`): in disabled mode that's
the `X-User-Key` header; in jwt mode it's `google:{sub}` from the verified token.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.core.config import settings
from app.schemas.ingredient import IngredientSuggestion
from app.schemas.pantry import PantryReplaceIn, PantryResponse
from app.services.ingredients import resolve_names_to_suggestions
from app.services.pantry import get_pantry, replace_pantry
from app.services.pantry_image import parse_pantry_images

router = APIRouter(prefix="/v1", tags=["pantry"])

ALLOWED_PANTRY_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class PantryParseResponse(BaseModel):
    recognized: list[IngredientSuggestion] = Field(default_factory=list)
    unmatched: list[str] = Field(default_factory=list)


@router.get("/pantry", response_model=PantryResponse)
def read_pantry(
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    return PantryResponse(items=get_pantry(session, user_key))


@router.post("/pantry/parse-images", response_model=PantryParseResponse)
async def parse_pantry_photos(
    images: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    """Pantry photos → recognized pantry items (vision parse + canonical resolve).

    Does NOT mutate the pantry; the client adds the recognized items via PUT
    /pantry. Photos are read into memory, base64'd for the one vision call, and
    dropped when the request ends — nothing is stored.

    Authed, unlike the rest of the parse path: a multi-image call on the main
    model is expensive enough to be worth tying to an identity.
    """
    if not images:
        raise HTTPException(400, "No photos provided")
    if len(images) > settings.PANTRY_IMAGE_MAX_COUNT:
        raise HTTPException(400, f"Up to {settings.PANTRY_IMAGE_MAX_COUNT} photos at a time")

    # Reject a bad file rather than skipping it: a silently dropped photo reads
    # to the user as the model having missed everything on that shelf.
    payload: list[tuple[bytes, str]] = []
    for img in images:
        if img.content_type not in ALLOWED_PANTRY_IMAGE_TYPES:
            raise HTTPException(400, f"Unsupported image type: {img.filename}")
        data = await img.read()
        if not data:
            raise HTTPException(400, f"Empty file: {img.filename}")
        if len(data) > settings.PANTRY_IMAGE_MAX_BYTES:
            mb = settings.PANTRY_IMAGE_MAX_BYTES // (1024 * 1024)
            raise HTTPException(400, f"Photo is too large (max {mb}MB): {img.filename}")
        payload.append((data, img.content_type))

    names = parse_pantry_images(payload)
    if not names:
        return PantryParseResponse(recognized=[], unmatched=[])
    recognized, unmatched = resolve_names_to_suggestions(session, names)
    return PantryParseResponse(recognized=recognized, unmatched=unmatched)


@router.put("/pantry", response_model=PantryResponse)
def write_pantry(
    body: PantryReplaceIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    items, unmatched = replace_pantry(session, user_key, body.items)
    return PantryResponse(items=items, unmatched=unmatched)
