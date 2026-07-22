"""Online analytics endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.schemas.event import EventIn, ExperimentSummaryOut
from app.services.events import experiment_summary, record_event

router = APIRouter(prefix="/v1", tags=["events"])


@router.post("/events")
def post_event(
    body: EventIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    record_event(session, user_key, body)
    return {"ok": True}


@router.get("/experiments/{name}/summary", response_model=ExperimentSummaryOut)
def get_experiment_summary(name: str, session: Session = Depends(get_session)):
    return experiment_summary(session, name)
