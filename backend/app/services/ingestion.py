"""Polymarket → DB ingestion.

`sync_trending_events`: pulls trending events from Gamma API and upserts them
plus their nested markets. Newly created events get `is_tracked=False` by
default — auto-tracking happens later via the scheduler (Phase 3).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.polymarket import PolymarketClient
from app.models import Event, Market

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    # Python's fromisoformat doesn't accept the 'Z' suffix prior to 3.11; we
    # normalize it anyway so behavior is consistent.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_outcomes(raw: Any) -> list[str] | None:
    """Polymarket returns outcomes as a JSON-encoded string."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(decoded, list):
            return [str(x) for x in decoded]
    return None


def _parse_prices(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if isinstance(raw, list):
        out: list[float] = []
        for x in raw:
            f = _parse_float(x)
            if f is None:
                return None
            out.append(f)
        return out
    return None


def _yes_price(prices: list[float] | None, outcomes: list[str] | None) -> float | None:
    """Return the price of the 'Yes' outcome, defaulting to prices[0]."""
    if not prices:
        return None
    if outcomes:
        for i, name in enumerate(outcomes):
            if name.strip().lower() == "yes" and i < len(prices):
                return prices[i]
    return prices[0]


def _resolved_outcome(
    is_resolved: bool,
    prices: list[float] | None,
    outcomes: list[str] | None,
) -> str | None:
    if not is_resolved or not prices or not outcomes:
        return None
    # Polymarket closes a market with the winning outcome at ~1.0
    max_i = max(range(len(prices)), key=lambda i: prices[i])
    if prices[max_i] >= 0.9 and max_i < len(outcomes):
        return outcomes[max_i]
    return None


def _apply_event_fields(event: Event, raw: dict[str, Any]) -> None:
    event.slug = raw.get("slug") or event.slug
    event.title = raw.get("title") or event.title or ""
    event.description = raw.get("description")
    event.category = raw.get("category")
    event.volume = _parse_float(raw.get("volume"))
    event.liquidity = _parse_float(raw.get("liquidity"))
    event.end_date = _parse_dt(raw.get("endDate"))
    event.raw = raw


def _apply_market_fields(market: Market, raw: dict[str, Any]) -> None:
    outcomes = _parse_outcomes(raw.get("outcomes"))
    prices = _parse_prices(raw.get("outcomePrices"))
    is_resolved = bool(raw.get("closed"))

    market.question = raw.get("question") or market.question or ""
    market.outcomes = outcomes
    market.current_price = _yes_price(prices, outcomes)

    # Don't un-resolve a previously-resolved market.
    if is_resolved and not market.is_resolved:
        market.is_resolved = True
        market.resolved_outcome = _resolved_outcome(True, prices, outcomes)
        market.resolved_at = _parse_dt(raw.get("closedTime")) or datetime.utcnow()
    elif is_resolved and market.is_resolved and not market.resolved_outcome:
        market.resolved_outcome = _resolved_outcome(True, prices, outcomes)

    market.raw = raw


async def upsert_event(session: AsyncSession, raw: dict[str, Any]) -> Event:
    """Insert or update a single event (with its markets). Caller commits."""
    polymarket_id = str(raw.get("id"))
    if not polymarket_id or polymarket_id == "None":
        raise ValueError("event missing id")

    result = await session.execute(
        select(Event).where(Event.polymarket_id == polymarket_id)
    )
    event = result.scalar_one_or_none()

    if event is None:
        event = Event(polymarket_id=polymarket_id, title=raw.get("title") or "")
        session.add(event)

    _apply_event_fields(event, raw)
    await session.flush()  # ensure event.id

    # Markets
    existing_q = await session.execute(
        select(Market).where(Market.event_id == event.id)
    )
    existing: dict[str, Market] = {m.polymarket_id: m for m in existing_q.scalars()}

    for m_raw in raw.get("markets") or []:
        m_id = str(m_raw.get("id"))
        if not m_id or m_id == "None":
            continue
        market = existing.get(m_id)
        if market is None:
            market = Market(
                event_id=event.id,
                polymarket_id=m_id,
                question=m_raw.get("question") or "",
            )
            session.add(market)
        _apply_market_fields(market, m_raw)

    return event


async def sync_trending_events(
    session: AsyncSession,
    *,
    limit: int = 50,
    min_volume: float = 10_000.0,
    client: PolymarketClient | None = None,
) -> dict[str, int]:
    """Pull trending events and upsert them. Returns counts."""
    own_client = client is None
    if client is None:
        client = PolymarketClient()
    try:
        events = await client.fetch_trending_events(limit=limit, min_volume=min_volume)
    finally:
        if own_client:
            await client.close()

    upserted = 0
    markets_seen = 0
    for raw in events:
        await upsert_event(session, raw)
        upserted += 1
        markets_seen += len(raw.get("markets") or [])

    await session.commit()
    logger.info("polymarket sync: %d events upserted, %d markets seen", upserted, markets_seen)
    return {"events": upserted, "markets": markets_seen}


async def refresh_event(
    session: AsyncSession,
    polymarket_id: str,
    *,
    client: PolymarketClient | None = None,
) -> Event:
    """Re-fetch one event by id and upsert. Caller may commit."""
    own_client = client is None
    if client is None:
        client = PolymarketClient()
    try:
        raw = await client.fetch_event_by_id(polymarket_id)
    finally:
        if own_client:
            await client.close()
    return await upsert_event(session, raw)
