"""Shopping list endpoint (API-03) + cache metrics (RETR-04)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.shopping import ShoppingListRequest, ShoppingListResponse
from app.services.cache import cache_metrics
from app.services.shopping import build_shopping_list

router = APIRouter(prefix="/v1", tags=["shopping"])


@router.post("/shopping-list", response_model=ShoppingListResponse)
def shopping_list(req: ShoppingListRequest, session: Session = Depends(get_session)):
    return build_shopping_list(session, req.recipe_ids, req.pantry)


@router.get("/metrics/cache")
def metrics_cache():
    return cache_metrics()
