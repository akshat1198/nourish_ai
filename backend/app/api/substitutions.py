"""Substitutions endpoint (API-02) — curated table swaps + LLM suggestions (WS4).

The curated `substitutions` table is small and high-confidence; the LLM fills in
the long tail (greek yogurt → dahi, sunflower → avocado oil, …). Curated swaps
lead; LLM suggestions follow, de-duped by name. Fails open to table-only when
the assistant isn't configured."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.tools import call_tool
from app.api.deps import get_session
from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.schemas.llm import SuggestedSwaps
from app.services.ingredients import normalize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["substitutions"])

MAX_SUGGESTIONS = 8

_SUGGEST_SYSTEM = (
    "You suggest realistic, common cooking substitutes for ONE ingredient. Give "
    "3-6 options a home cook would actually use, most typical first. For each: a "
    "quantity ratio (original:substitute), a short note (<=12 words), and any "
    "diets it enables. Do NOT repeat the original ingredient."
)


class SubstitutionsRequest(BaseModel):
    ingredient: str
    diet: Optional[str] = Field(None, description="Only return swaps that enable this diet")


def _llm_suggestions(ingredient: str, diet: Optional[str]) -> list[dict]:
    """LLM-proposed swaps for `ingredient` (fail-open to [])."""
    if not is_enabled():
        return []
    ask = f'Ingredient: "{ingredient}".'
    if diet:
        ask += f" Only suggest swaps that make a recipe {diet}."
    try:
        result = get_llm().generate_structured(
            messages=[{"role": "user", "content": f"{_SUGGEST_SYSTEM}\n\n{ask}"}],
            schema=SuggestedSwaps,
            model=settings.LLM_MODEL_MAIN,
            max_tokens=700,
        )
    except LLMError as e:
        logger.warning("substitution suggestions unavailable: %s", e)
        return []
    return [
        {
            "use": s.use,
            "ratio": s.ratio,
            "note": s.note,
            "enables_diets": s.enables_diets,
            "confidence": None,
            "source": "suggested",
        }
        for s in result.substitutes
    ]


@router.post("/substitutions")
def substitutions(req: SubstitutionsRequest, session: Session = Depends(get_session)):
    result = call_tool(session, "find_substitutions", req.model_dump(exclude_none=True))
    ingredient = result.get("ingredient", req.ingredient)
    merged: list[dict] = []
    seen: set[str] = {normalize(req.ingredient)}

    for s in result.get("substitutes", []):
        merged.append({**s, "note": s.get("note", ""), "source": "curated"})
        seen.add(normalize(s["use"]))

    for s in _llm_suggestions(ingredient, req.diet):
        if normalize(s["use"]) in seen:
            continue
        seen.add(normalize(s["use"]))
        merged.append(s)

    return {"ingredient": ingredient, "substitutes": merged[:MAX_SUGGESTIONS]}
