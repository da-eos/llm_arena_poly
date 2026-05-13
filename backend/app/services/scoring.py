"""Scoring of resolved markets.

For each prediction on a resolved market we compute:
- Brier score: (p - o)^2, lower is better
- log loss with clipping: -[o*log(p) + (1-o)*log(1-p)], lower is better
- demo P&L (`pnl_demo`): the model picks the side where its prob deviates from
  market price most, stakes $100, and either wins `stake * (1/price - 1)` or
  loses `stake`
"""
from __future__ import annotations

import logging
import math
import uuid

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import async_session_factory
from app.models import Event, LLMModel, Market, Prediction, Score

logger = logging.getLogger(__name__)

EPS = 1e-6


def brier_score(p_yes: float, outcome: bool) -> float:
    o = 1.0 if outcome else 0.0
    return (p_yes - o) ** 2


def log_loss(p_yes: float, outcome: bool) -> float:
    p = min(max(p_yes, EPS), 1.0 - EPS)
    if outcome:
        return -math.log(p)
    return -math.log(1.0 - p)


def pnl_demo(
    p_yes: float,
    market_price: float | None,
    outcome: bool,
    stake: float = 100.0,
) -> float:
    """Pick the side where the model's probability diverges from market most,
    stake `stake` at that side's price. Return profit or loss.
    """
    if market_price is None or market_price <= 0 or market_price >= 1:
        # Can't bet — degenerate price or missing. Return 0.
        return 0.0

    # Choice of side: YES if model thinks YES is undervalued (p_yes > market),
    # else NO. Magnitude of edge is the same for both sides in absolute terms;
    # the sign is what matters.
    if p_yes >= market_price:
        side_yes = True
        price = market_price
    else:
        side_yes = False
        price = 1.0 - market_price

    won = (side_yes and outcome) or ((not side_yes) and (not outcome))
    if won:
        return stake * (1.0 / price - 1.0)
    return -stake


def _outcome_is_yes(resolved_outcome: str | None) -> bool | None:
    """Map Polymarket's resolved_outcome string to a YES boolean for binary markets.

    Returns None when we can't determine (non-binary, missing, ambiguous).
    """
    if resolved_outcome is None:
        return None
    s = resolved_outcome.strip().lower()
    if s == "yes":
        return True
    if s == "no":
        return False
    return None


async def score_resolved_market(
    session: AsyncSession, market_id: uuid.UUID
) -> dict[str, int]:
    """Compute (or overwrite) Score rows for every prediction on this market.

    Caller is responsible for committing the session.
    """
    market = (
        await session.execute(
            select(Market)
            .options(selectinload(Market.predictions))
            .where(Market.id == market_id)
        )
    ).scalar_one_or_none()
    if market is None:
        return {"scored": 0, "skipped": 0}
    if not market.is_resolved:
        return {"scored": 0, "skipped": 0}

    outcome = _outcome_is_yes(market.resolved_outcome)
    if outcome is None:
        logger.info(
            "scoring: market %s resolved but outcome=%r not binary-mappable",
            market.polymarket_id, market.resolved_outcome,
        )
        return {"scored": 0, "skipped": len(market.predictions)}

    scored = 0
    skipped = 0
    for pred in market.predictions:
        if pred.error is not None:
            skipped += 1
            continue
        p = max(0.0, min(1.0, pred.predicted_probability_yes))
        brier = brier_score(p, outcome)
        ll = log_loss(p, outcome)
        pnl = pnl_demo(p, market.current_price, outcome)
        was_correct = (p >= 0.5) == outcome

        existing = (
            await session.execute(select(Score).where(Score.prediction_id == pred.id))
        ).scalar_one_or_none()
        if existing is None:
            existing = Score(
                prediction_id=pred.id,
                brier_score=brier,
                log_loss=ll,
                pnl_demo_usd=pnl,
                was_correct=was_correct,
            )
            session.add(existing)
        else:
            existing.brier_score = brier
            existing.log_loss = ll
            existing.pnl_demo_usd = pnl
            existing.was_correct = was_correct
        scored += 1

    await session.flush()
    return {"scored": scored, "skipped": skipped}


async def score_all_resolved() -> dict[str, int]:
    """Walk all resolved markets and (re)compute their scores. Useful for backfills."""
    totals = {"markets": 0, "scored": 0, "skipped": 0}
    async with async_session_factory() as session:
        market_ids = (
            await session.execute(
                select(Market.id).where(Market.is_resolved.is_(True))
            )
        ).scalars().all()
        for mid in market_ids:
            res = await score_resolved_market(session, mid)
            totals["markets"] += 1
            totals["scored"] += res["scored"]
            totals["skipped"] += res["skipped"]
        await session.commit()
    return totals


async def leaderboard_rows(
    *, category: str | None = None
) -> list[dict[str, object]]:
    """Per-model aggregates over all scored predictions.

    `category` filters by `events.category` (since predictions live on markets
    which live on events).
    """
    async with async_session_factory() as session:
        stmt = (
            select(
                LLMModel.slug,
                LLMModel.display_name,
                LLMModel.provider,
                func.count(Score.id).label("n"),
                func.avg(Score.brier_score).label("avg_brier"),
                func.avg(Score.log_loss).label("avg_log_loss"),
                func.sum(Score.pnl_demo_usd).label("total_pnl"),
                func.sum(cast(Score.was_correct, Integer)).label("correct"),
            )
            .join(Prediction, Prediction.id == Score.prediction_id)
            .join(LLMModel, LLMModel.id == Prediction.llm_model_id)
            .join(Market, Market.id == Prediction.market_id)
            .join(Event, Event.id == Market.event_id)
            .group_by(LLMModel.id)
        )
        if category is not None:
            stmt = stmt.where(Event.category == category)
        rows = (await session.execute(stmt)).all()

    return [
        {
            "slug": r.slug,
            "display_name": r.display_name,
            "provider": r.provider.value if hasattr(r.provider, "value") else r.provider,
            "n": int(r.n or 0),
            "avg_brier": float(r.avg_brier) if r.avg_brier is not None else None,
            "avg_log_loss": float(r.avg_log_loss) if r.avg_log_loss is not None else None,
            "total_pnl": float(r.total_pnl) if r.total_pnl is not None else 0.0,
            "accuracy": (float(r.correct) / r.n) if r.n else None,
        }
        for r in rows
    ]


async def model_history(slug: str) -> list[dict[str, object]]:
    """All scored predictions for a model, oldest first, with cumulative PnL."""
    async with async_session_factory() as session:
        model = (
            await session.execute(select(LLMModel).where(LLMModel.slug == slug))
        ).scalar_one_or_none()
        if model is None:
            return []

        stmt = (
            select(Score, Prediction, Market, Event)
            .join(Prediction, Prediction.id == Score.prediction_id)
            .join(Market, Market.id == Prediction.market_id)
            .join(Event, Event.id == Market.event_id)
            .where(Prediction.llm_model_id == model.id)
            .order_by(Score.created_at.asc())
        )
        rows = (await session.execute(stmt)).all()

    cum = 0.0
    out: list[dict[str, object]] = []
    for score, pred, market, event in rows:
        cum += score.pnl_demo_usd
        out.append({
            "score_id": str(score.id),
            "prediction_id": str(pred.id),
            "market_id": str(market.id),
            "event_id": str(event.id),
            "event_title": event.title,
            "market_question": market.question,
            "resolved_outcome": market.resolved_outcome,
            "predicted_probability_yes": pred.predicted_probability_yes,
            "market_price": market.current_price,
            "brier_score": score.brier_score,
            "log_loss": score.log_loss,
            "pnl_demo_usd": score.pnl_demo_usd,
            "cum_pnl_usd": cum,
            "was_correct": score.was_correct,
            "created_at": score.created_at.isoformat(),
        })
    return out
