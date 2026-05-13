from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import PredictRunResult, SyncResult
from app.db import get_session
from app.jobs import (
    auto_track_top_events_job,
    predictions_job,
    refresh_tracked_events_job,
    sync_trending_events_job,
)
from app.llm.base import ProviderDisabledError, ProviderError
from app.llm.registry import get_provider, provider_status
from app.models import LLMProviderEnum
from app.scheduler import scheduler
from app.services.ingestion import sync_trending_events
from app.services.predictor import run_predictions_for_tracked

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class JobInfo(BaseModel):
    id: str
    name: str
    next_run_time: datetime | None
    trigger: str


class JobsList(BaseModel):
    items: list[JobInfo]


@router.post("/sync/polymarket", response_model=SyncResult)
async def sync_polymarket(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    min_volume: float = Query(default=10_000.0, ge=0),
) -> SyncResult:
    counts = await sync_trending_events(session, limit=limit, min_volume=min_volume)
    return SyncResult(**counts)


@router.get("/jobs", response_model=JobsList)
async def list_jobs() -> JobsList:
    items = [
        JobInfo(
            id=j.id,
            name=j.name or j.id,
            next_run_time=j.next_run_time,
            trigger=str(j.trigger),
        )
        for j in scheduler.get_jobs()
    ]
    return JobsList(items=items)


class TestProviderRequest(BaseModel):
    provider: LLMProviderEnum
    model_id: str
    prompt: str


class TestProviderResponse(BaseModel):
    probability_yes: float
    reasoning: str
    confidence: float | None = None
    latency_ms: int
    cost_usd: float | None = None


@router.post("/predict-now", response_model=PredictRunResult)
async def predict_now(force: bool = False) -> PredictRunResult:
    counts = await run_predictions_for_tracked(force=force)
    return PredictRunResult(**counts)


@router.get("/providers")
async def list_providers() -> dict[str, bool]:
    return provider_status()


@router.post("/test-provider", response_model=TestProviderResponse)
async def test_provider(req: TestProviderRequest) -> TestProviderResponse:
    provider = get_provider(req.provider)
    try:
        result = await provider.predict(req.prompt, req.model_id)
    except ProviderDisabledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TestProviderResponse(
        probability_yes=result.probability_yes,
        reasoning=result.reasoning,
        confidence=result.confidence,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
    )


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str) -> dict[str, str]:
    """Force-run a registered scheduler job once (for debugging)."""
    handlers = {
        "sync_trending_events": sync_trending_events_job,
        "auto_track_top_events": auto_track_top_events_job,
        "refresh_tracked_events": refresh_tracked_events_job,
        "predictions": predictions_job,
    }
    fn = handlers.get(job_id)
    if fn is None:
        raise HTTPException(status_code=404, detail="unknown job")
    await fn()
    return {"status": "ok", "job": job_id}
