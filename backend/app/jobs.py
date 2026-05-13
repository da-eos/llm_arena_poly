"""APScheduler jobs.

Each job opens its own DB session (the scheduler runs outside a request).
Errors are caught and logged so a single failure doesn't kill the scheduler.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.clients.polymarket import PolymarketClient, PolymarketError
from app.db import async_session_factory
from app.models import Event, Market
from app.services.ingestion import refresh_event, sync_trending_events
from app.services.predictor import run_predictions_for_tracked
from app.settings import get_settings

logger = logging.getLogger(__name__)


async def sync_trending_events_job() -> None:
    logger.info("job: sync_trending_events start")
    try:
        async with async_session_factory() as session:
            counts = await sync_trending_events(session)
        logger.info("job: sync_trending_events ok %s", counts)
    except Exception:
        logger.exception("job: sync_trending_events failed")


async def auto_track_top_events_job(top_n: int | None = None) -> None:
    """Auto-track events that resolve soon and have deep liquidity.

    Filter:
      - not yet tracked
      - end_date in the future and within `auto_track_max_days_to_end`
      - liquidity >= `auto_track_min_liquidity`
    Rank by liquidity desc, take top-N.
    """
    s = get_settings()
    top_n = top_n if top_n is not None else s.auto_track_top_n
    logger.info("job: auto_track_top_events start")
    try:
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            horizon = now + timedelta(days=s.auto_track_max_days_to_end)
            stmt = (
                select(Event)
                .where(Event.is_tracked.is_(False))
                .where(Event.end_date.is_not(None))
                .where(Event.end_date > now)
                .where(Event.end_date <= horizon)
                .where(Event.liquidity.is_not(None))
                .where(Event.liquidity >= s.auto_track_min_liquidity)
                .order_by(Event.liquidity.desc())
                .limit(top_n)
            )
            rows = (await session.execute(stmt)).scalars().all()
            ids = [e.id for e in rows]
            if not ids:
                logger.info(
                    "job: auto_track_top_events nothing matched "
                    "(horizon=%dd, min_liquidity=%.0f)",
                    s.auto_track_max_days_to_end, s.auto_track_min_liquidity,
                )
                return
            await session.execute(
                update(Event).where(Event.id.in_(ids)).values(is_tracked=True)
            )
            await session.commit()
            logger.info(
                "job: auto_track_top_events tracked %d events (horizon=%dd, top_n=%d)",
                len(ids), s.auto_track_max_days_to_end, top_n,
            )
    except Exception:
        logger.exception("job: auto_track_top_events failed")


async def predictions_job() -> None:
    logger.info("job: predictions start")
    try:
        counts = await run_predictions_for_tracked()
        logger.info("job: predictions done %s", counts)
    except Exception:
        logger.exception("job: predictions failed")


async def refresh_tracked_events_job() -> None:
    """Re-fetch tracked events; log newly-resolved markets (scoring lands in Phase 6)."""
    logger.info("job: refresh_tracked_events start")
    try:
        async with async_session_factory() as session:
            tracked = (
                await session.execute(select(Event).where(Event.is_tracked.is_(True)))
            ).scalars().all()
            if not tracked:
                logger.info("job: refresh_tracked_events no tracked events")
                return

            # Snapshot previously-unresolved markets per event for delta detection.
            prev_unresolved: dict[str, set[str]] = {}
            for ev in tracked:
                m_rows = (
                    await session.execute(
                        select(Market).where(
                            Market.event_id == ev.id, Market.is_resolved.is_(False)
                        )
                    )
                ).scalars().all()
                prev_unresolved[ev.polymarket_id] = {m.polymarket_id for m in m_rows}

            async with PolymarketClient() as client:
                refreshed = 0
                newly_resolved_total = 0
                for ev in tracked:
                    try:
                        await refresh_event(session, ev.polymarket_id, client=client)
                        refreshed += 1
                    except PolymarketError as exc:
                        logger.warning(
                            "job: refresh_tracked_events event=%s error=%s",
                            ev.polymarket_id, exc,
                        )
                        continue
                    # Find markets that flipped to resolved.
                    m_rows = (
                        await session.execute(
                            select(Market).where(
                                Market.event_id == ev.id, Market.is_resolved.is_(True)
                            )
                        )
                    ).scalars().all()
                    flipped = [
                        m for m in m_rows if m.polymarket_id in prev_unresolved[ev.polymarket_id]
                    ]
                    if flipped:
                        newly_resolved_total += len(flipped)
                        for m in flipped:
                            logger.info(
                                "market resolved: event=%s market=%s outcome=%s "
                                "(TODO: score in phase-6)",
                                ev.polymarket_id, m.polymarket_id, m.resolved_outcome,
                            )
            await session.commit()
            logger.info(
                "job: refresh_tracked_events refreshed=%d newly_resolved=%d",
                refreshed, newly_resolved_total,
            )
    except Exception:
        logger.exception("job: refresh_tracked_events failed")
