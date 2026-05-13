"""Prediction engine: orchestrates LLM calls and persists results.

`predict_for_market` makes a single (market, model) prediction.
`run_predictions_for_tracked` fans out across all tracked markets × enabled
models, with bounded concurrency.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import async_session_factory
from app.llm.base import (
    LLMProvider,
    PredictionResult,
    ProviderDisabledError,
    ProviderError,
    ProviderResponseError,
)
from app.llm.registry import get_provider
from app.models import Event, LLMModel, Market, Prediction
from app.services.prompting import build_prompt

logger = logging.getLogger(__name__)

# Limits concurrent in-flight LLM requests across the whole process.
MAX_CONCURRENT_LLM_CALLS = 5
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)


async def _get_existing(
    session: AsyncSession, market_id: uuid.UUID, llm_model_id: uuid.UUID
) -> Prediction | None:
    res = await session.execute(
        select(Prediction).where(
            Prediction.market_id == market_id,
            Prediction.llm_model_id == llm_model_id,
        )
    )
    return res.scalar_one_or_none()


async def _save_prediction(
    session: AsyncSession,
    *,
    market: Market,
    model: LLMModel,
    prompt: str,
    result: PredictionResult | None,
    error: str | None,
) -> Prediction:
    existing = await _get_existing(session, market.id, model.id)
    if existing is None:
        existing = Prediction(market_id=market.id, llm_model_id=model.id, predicted_probability_yes=0.0)
        session.add(existing)

    existing.prompt_used = prompt
    if result is not None:
        existing.predicted_probability_yes = result.probability_yes
        existing.reasoning = result.reasoning
        existing.confidence = result.confidence
        existing.raw_response = result.raw_response
        existing.latency_ms = result.latency_ms
        existing.cost_usd = result.cost_usd
        existing.error = None
    else:
        existing.error = error
        # Keep an obviously bogus probability so it won't accidentally score.
        existing.predicted_probability_yes = 0.5
        existing.reasoning = None
        existing.confidence = None
        existing.raw_response = None
        existing.latency_ms = None
        existing.cost_usd = None

    await session.flush()
    return existing


async def predict_for_market(
    session: AsyncSession,
    *,
    market_id: uuid.UUID,
    llm_model_id: uuid.UUID,
    force: bool = False,
) -> Prediction | None:
    """Run a single (market, model) prediction. Returns the Prediction row or None if skipped."""
    market = (
        await session.execute(
            select(Market).options(selectinload(Market.event)).where(Market.id == market_id)
        )
    ).scalar_one_or_none()
    if market is None:
        raise ValueError(f"market {market_id} not found")
    if market.is_resolved:
        logger.info("skip predict: market %s already resolved", market.polymarket_id)
        return None

    model = (
        await session.execute(select(LLMModel).where(LLMModel.id == llm_model_id))
    ).scalar_one_or_none()
    if model is None:
        raise ValueError(f"llm_model {llm_model_id} not found")
    if not model.is_enabled:
        logger.info("skip predict: model %s disabled", model.slug)
        return None

    if not force:
        existing = await _get_existing(session, market.id, model.id)
        if existing is not None and existing.error is None:
            return existing  # already have a successful prediction

    event = market.event
    prompt = build_prompt(event, market)
    provider = get_provider(model.provider)

    result: PredictionResult | None = None
    error: str | None = None
    try:
        result = await provider.predict(prompt, model.model_id_at_provider)
    except ProviderDisabledError as exc:
        error = f"disabled: {exc}"
        logger.warning("provider disabled: %s", exc)
    except ProviderResponseError as exc:
        error = f"bad_response: {exc}"
        logger.warning("bad response from %s on market %s: %s", model.slug, market.polymarket_id, exc)
    except ProviderError as exc:
        error = f"provider_error: {exc}"
        logger.warning("provider error %s on market %s: %s", model.slug, market.polymarket_id, exc)
    except Exception as exc:  # noqa: BLE001
        error = f"unexpected: {exc!r}"
        logger.exception("unexpected error predicting %s on %s", model.slug, market.polymarket_id)

    pred = await _save_prediction(
        session, market=market, model=model, prompt=prompt, result=result, error=error
    )
    return pred


async def _predict_pair(
    market_id: uuid.UUID, llm_model_id: uuid.UUID, force: bool
) -> dict[str, Any]:
    """Run a single prediction in its own session — safe to gather in parallel.

    The semaphore gates the entire task so we don't open a DB session until
    we're ready to actually do work (otherwise we'd exhaust the pool).
    """
    async with _semaphore, async_session_factory() as session:
        try:
            pred = await predict_for_market(
                session, market_id=market_id, llm_model_id=llm_model_id, force=force
            )
            await session.commit()
            if pred is None:
                return {"market_id": str(market_id), "model_id": str(llm_model_id), "status": "skipped"}
            return {
                "market_id": str(market_id),
                "model_id": str(llm_model_id),
                "status": "ok" if pred.error is None else "error",
                "error": pred.error,
            }
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.exception("predict_pair failed")
            return {
                "market_id": str(market_id),
                "model_id": str(llm_model_id),
                "status": "fail",
                "error": repr(exc),
            }


async def run_predictions_for_tracked(*, force: bool = False) -> dict[str, int]:
    """For each tracked, unresolved market × enabled model — make a prediction
    (if not present). Returns aggregate counts.
    """
    async with async_session_factory() as session:
        markets = (
            await session.execute(
                select(Market)
                .join(Event, Event.id == Market.event_id)
                .where(Event.is_tracked.is_(True))
                .where(Market.is_resolved.is_(False))
            )
        ).scalars().all()
        models = (
            await session.execute(select(LLMModel).where(LLMModel.is_enabled.is_(True)))
        ).scalars().all()

        market_ids = [m.id for m in markets]
        model_ids = [m.id for m in models]

    pairs: list[tuple[uuid.UUID, uuid.UUID]] = [
        (mk, md) for mk in market_ids for md in model_ids
    ]
    logger.info(
        "predictions: %d markets × %d models = %d pairs (force=%s)",
        len(market_ids), len(model_ids), len(pairs), force,
    )

    tasks = [_predict_pair(mk, md, force) for mk, md in pairs]
    results = await asyncio.gather(*tasks) if tasks else []

    counts = {"total": len(results), "ok": 0, "error": 0, "skipped": 0, "fail": 0}
    for r in results:
        counts[r.get("status", "fail")] = counts.get(r.get("status", "fail"), 0) + 1
    logger.info("predictions done: %s", counts)
    return counts
