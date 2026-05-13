"""APScheduler jobs.

Each job opens its own DB session (the scheduler runs outside a request).
Errors are caught and logged so a single failure doesn't kill the scheduler.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.clients.polymarket import PolymarketClient, PolymarketError
from app.db import async_session_factory
from app.models import Event, Market
from app.services.ingestion import refresh_event, sync_trending_events

logger = logging.getLogger(__name__)


async def sync_trending_events_job() -> None:
    logger.info("job: sync_trending_events start")
    try:
        async with async_session_factory() as session:
            counts = await sync_trending_events(session)
        logger.info("job: sync_trending_events ok %s", counts)
    except Exception:
        logger.exception("job: sync_trending_events failed")


async def auto_track_top_events_job(top_n: int = 10) -> None:
    """Auto-track top-N events by volume that aren't tracked yet and end in future."""
    logger.info("job: auto_track_top_events start")
    try:
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            stmt = (
                select(Event)
                .where(Event.is_tracked.is_(False))
                .where((Event.end_date.is_(None)) | (Event.end_date > now))
                .order_by(Event.volume.desc().nullslast())
                .limit(top_n)
            )
            rows = (await session.execute(stmt)).scalars().all()
            ids = [e.id for e in rows]
            if not ids:
                logger.info("job: auto_track_top_events nothing to track")
                return
            await session.execute(
                update(Event).where(Event.id.in_(ids)).values(is_tracked=True)
            )
            await session.commit()
            logger.info("job: auto_track_top_events tracked %d events", len(ids))
    except Exception:
        logger.exception("job: auto_track_top_events failed")


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
