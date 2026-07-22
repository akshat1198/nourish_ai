"""Admin observability endpoint. Read-only; gated by require_admin."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.api.deps import get_session
from app.services.metrics import admin_metrics

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/metrics")
def get_metrics(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
):
    return admin_metrics(session)
