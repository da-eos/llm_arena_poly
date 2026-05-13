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
    markets_count: int = 0
    predictions_count: int = 0


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


class LLMModelRead(_ORMModel):
    id: uuid.UUID
    slug: str
    provider: str
    display_name: str
    model_id_at_provider: str
    is_enabled: bool


class PredictionRead(_ORMModel):
    id: uuid.UUID
    market_id: uuid.UUID
    llm_model_id: uuid.UUID
    predicted_probability_yes: float
    reasoning: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    cost_usd: float | None = None
    error: str | None = None
    created_at: datetime


class PredictionWithModel(PredictionRead):
    llm_model: LLMModelRead


class MarketWithPredictions(MarketRead):
    predictions: list[PredictionWithModel] = []


class EventPredictions(BaseModel):
    event_id: uuid.UUID
    title: str
    slug: str | None = None
    polymarket_id: str
    end_date: datetime | None = None
    markets: list[MarketWithPredictions]


class PredictRunResult(BaseModel):
    total: int
    ok: int
    error: int
    skipped: int
    fail: int
