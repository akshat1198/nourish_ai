"""Substitutions endpoint (API-02) — thin wrapper over the find_substitutions tool."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.tools import call_tool
from app.api.deps import get_session

router = APIRouter(prefix="/v1", tags=["substitutions"])


class SubstitutionsRequest(BaseModel):
    ingredient: str
    diet: Optional[str] = Field(None, description="Only return swaps that enable this diet")


@router.post("/substitutions")
def substitutions(req: SubstitutionsRequest, session: Session = Depends(get_session)):
    return call_tool(session, "find_substitutions", req.model_dump(exclude_none=True))
