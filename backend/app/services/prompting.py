"""Prompt builder for prediction markets (Russian).

We deliberately do NOT show the model the current Polymarket price — we want
the model's independent probability estimate, not a reflection of consensus.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import Event, Market


def _format_end_date(end: datetime | None) -> str:
    if not end:
        return "не указана"
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = end - now
    days = delta.days
    when = end.strftime("%Y-%m-%d")
    if days <= 0:
        return f"{when} (уже прошла)"
    if days == 1:
        return f"{when} (через 1 день)"
    return f"{when} (через {days} дней)"


def build_prompt(event: Event, market: Market) -> str:
    outcomes = market.outcomes or ["Yes", "No"]
    outcomes_line = " / ".join(outcomes)

    description = (event.description or "").strip()
    if len(description) > 1500:
        description = description[:1500] + "…"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parts = [
        "Ты калиброванный прогнозист (forecaster). Тебе нужно оценить "
        "вероятность исхода рынка прогнозов.",
        f"Сегодня: {today}.",
        "",
        f"Событие: {event.title}",
    ]
    if event.category:
        parts.append(f"Категория: {event.category}")
    parts += [
        f"Дата резолва: {_format_end_date(event.end_date)}",
        "",
        f"Вопрос рынка: {market.question}",
        f"Возможные исходы: {outcomes_line}",
    ]
    if description:
        parts += ["", "Контекст события:", description]
    parts += [
        "",
        "Задача: оцени вероятность того, что этот рынок резолвнется YES. "
        "Опирайся на публично известные факты, базовые ставки и здравый смысл "
        "на сегодняшнюю дату. Не пытайся угадать рыночную цену — давай свою "
        "независимую оценку.",
    ]
    return "\n".join(parts)
