from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.jobs import (
    auto_track_top_events_job,
    predictions_job,
    refresh_tracked_events_job,
    sync_trending_events_job,
)
from app.settings import get_settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


def register_jobs() -> None:
    s = get_settings()
    scheduler.add_job(
        sync_trending_events_job,
        IntervalTrigger(minutes=s.sync_trending_interval_min),
        id="sync_trending_events",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        auto_track_top_events_job,
        IntervalTrigger(minutes=s.auto_track_interval_min),
        id="auto_track_top_events",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        refresh_tracked_events_job,
        IntervalTrigger(minutes=s.refresh_tracked_interval_min),
        id="refresh_tracked_events",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        predictions_job,
        IntervalTrigger(minutes=s.predictions_interval_min),
        id="predictions",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def start_scheduler() -> None:
    register_jobs()
    scheduler.start()
    logger.info("scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
