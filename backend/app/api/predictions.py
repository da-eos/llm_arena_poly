import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    EventPredictions,
    LLMModelRead,
    MarketWithPredictions,
    PredictionRead,
    PredictionWithModel,
)
from app.db import get_session
from app.models import Event, LLMModel, Market, Prediction
from app.services.predictor import predict_for_market

router = APIRouter(tags=["predictions"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/predictions", response_model=list[PredictionRead])
async def list_predictions(
    session: SessionDep,
    event_id: uuid.UUID | None = None,
    model_slug: str | None = None,
    limit: int = 100,
) -> list[PredictionRead]:
    stmt = select(Prediction)
    if event_id is not None:
        stmt = stmt.join(Market, Market.id == Prediction.market_id).where(
            Market.event_id == event_id
        )
    if model_slug is not None:
        stmt = stmt.join(LLMModel, LLMModel.id == Prediction.llm_model_id).where(
            LLMModel.slug == model_slug
        )
    stmt = stmt.order_by(Prediction.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [PredictionRead.model_validate(p) for p in rows]


@router.get("/events/{event_id}/predictions", response_model=EventPredictions)
async def event_predictions(event_id: uuid.UUID, session: SessionDep) -> EventPredictions:
    event = (
        await session.execute(
            select(Event)
            .options(
                selectinload(Event.markets)
                .selectinload(Market.predictions)
                .selectinload(Prediction.llm_model)
            )
            .where(Event.id == event_id)
        )
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")

    return EventPredictions(
        event_id=event.id,
        title=event.title,
        markets=[
            MarketWithPredictions(
                id=m.id,
                polymarket_id=m.polymarket_id,
                question=m.question,
                outcomes=m.outcomes,
                current_price=m.current_price,
                is_resolved=m.is_resolved,
                resolved_outcome=m.resolved_outcome,
                resolved_at=m.resolved_at,
                predictions=[
                    PredictionWithModel(
                        id=p.id,
                        market_id=p.market_id,
                        llm_model_id=p.llm_model_id,
                        predicted_probability_yes=p.predicted_probability_yes,
                        reasoning=p.reasoning,
                        confidence=p.confidence,
                        latency_ms=p.latency_ms,
                        cost_usd=p.cost_usd,
                        error=p.error,
                        created_at=p.created_at,
                        llm_model=LLMModelRead.model_validate(p.llm_model),
                    )
                    for p in m.predictions
                ],
            )
            for m in event.markets
        ],
    )


@router.post(
    "/predictions/market/{market_id}/model/{model_slug}",
    response_model=PredictionRead,
)
async def predict_one(
    market_id: uuid.UUID,
    model_slug: str,
    session: SessionDep,
    force: bool = False,
) -> PredictionRead:
    model = (
        await session.execute(select(LLMModel).where(LLMModel.slug == model_slug))
    ).scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail=f"model {model_slug} not found")
    pred = await predict_for_market(
        session, market_id=market_id, llm_model_id=model.id, force=force
    )
    if pred is None:
        raise HTTPException(status_code=409, detail="prediction skipped (resolved/disabled)")
    await session.commit()
    return PredictionRead.model_validate(pred)


@router.get("/models", response_model=list[LLMModelRead])
async def list_models(session: SessionDep) -> list[LLMModelRead]:
    rows = (
        await session.execute(select(LLMModel).order_by(LLMModel.slug))
    ).scalars().all()
    return [LLMModelRead.model_validate(m) for m in rows]
