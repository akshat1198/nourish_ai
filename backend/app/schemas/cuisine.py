"""Schema for GET /v1/cuisines — the authored taxonomy annotated with live counts."""
from __future__ import annotations

from pydantic import BaseModel


class CuisineCount(BaseModel):
    id: str
    label: str
    count: int                      # recipes under this node (top-level = all its regions)
    children: list["CuisineCount"] = []
