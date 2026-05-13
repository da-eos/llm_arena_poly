"""Pydantic response schemas for the public API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MarketRead(_ORMModel):
    id: uuid.UUID
    polymarket_id: str
    question: str
    outcomes: list[str] | None = None
    current_price: float | None = None
    is_resolved: bool
    resolved_outcome: str | None = None
    resolved_at: datetime | None = None


class EventRead(_ORMModel):
    id: uuid.UUID
    polymarket_id: str
    slug: str | None = None
    title: str
    description: str | None = None
    category: str | None = None
    volume: float | None = None
    liquidity: float | None = None
    end_date: datetime | None = None
    is_tracked: bool
    created_at: datetime
    updated_at: datetime


class EventDetail(EventRead):
    markets: list[MarketRead] = []


class EventList(BaseModel):
    items: list[EventRead]
    total: int
    limit: int
    offset: int


class SyncResult(BaseModel):
    events: int
    markets: int


class OkResponse(BaseModel):
    ok: bool = True
