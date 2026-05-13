"""Prompt builder for prediction markets.

We deliberately do NOT show the model the current Polymarket price — we want
the model's independent probability estimate, not a reflection of consensus.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import Event, Market


def _format_end_date(end: datetime | None) -> str:
    if not end:
        return "unspecified"
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = end - now
    days = delta.days
    when = end.strftime("%Y-%m-%d")
    if days <= 0:
        return f"{when} (already past)"
    return f"{when} (in {days} day{'s' if days != 1 else ''})"


def build_prompt(event: Event, market: Market) -> str:
    outcomes = market.outcomes or ["Yes", "No"]
    outcomes_line = ", ".join(outcomes)

    description = (event.description or "").strip()
    if len(description) > 1500:
        description = description[:1500] + "…"

    parts = [
        "You are a calibrated forecaster.",
        f"Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.",
        "",
        f"Event: {event.title}",
    ]
    if event.category:
        parts.append(f"Category: {event.category}")
    parts += [
        f"Event resolution date: {_format_end_date(event.end_date)}",
        "",
        f"Question: {market.question}",
        f"Possible outcomes: {outcomes_line}",
    ]
    if description:
        parts += ["", "Background:", description]
    parts += [
        "",
        "Task: estimate the probability that this market resolves YES. Base your "
        "estimate on publicly known facts and base rates as of today; do not "
        "anchor to market prices.",
    ]
    return "\n".join(parts)
