"""Photo-based pantry parsing.

Turns photos of a fridge, shelf, or counter into ["spinach", "eggs", "cheddar"]
using the vision-capable model. Every photo in a batch goes into a single call
so the model can merge an item that appears in more than one shot, rather than
us de-duplicating names it phrased differently each time.

Fail-open, like `pantry_text`: if the LLM is disabled or errors, returns an
empty list and logs — the caller degrades to "nothing recognised" instead of
failing the request.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.llm.client import LLMError, build_image_message, get_llm, is_enabled
from app.schemas.llm import ParsedPantry

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are looking at photos of someone's fridge, freezer, pantry shelf, or "
    "kitchen counter. List every distinct food ingredient you can see across "
    "ALL of the photos. Return bare ingredient names: lowercase, singular, no "
    "quantities, no brand names (\"2 cartons of Horizon whole milk\" -> "
    "\"milk\"). For packaged items read the label for the food it contains, "
    "not the brand. If the same item appears in more than one photo, list it "
    "once. Ignore non-food objects, empty containers, and packaging you can't "
    "read. If no food is visible, return an empty list."
)


def parse_pantry_images(images: list[tuple[bytes, str]]) -> list[str]:
    """Ingredient names read off (raw_bytes, media_type) photo pairs."""
    if not images or not is_enabled():
        return []
    try:
        result = get_llm().generate_structured(
            messages=[build_image_message(_SYSTEM, images)],
            schema=ParsedPantry,
            # Vision over several photos is a real reasoning task, unlike the
            # one-line text parse the fast model handles.
            model=settings.LLM_MODEL_MAIN,
            timeout=settings.PANTRY_IMAGE_TIMEOUT_SECONDS,
        )
    except LLMError as e:
        logger.warning("pantry_image parse failed, nothing recognised: %s", e)
        return []
    return [i.strip() for i in result.items if i and i.strip()]
