from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.scoring import leaderboard_rows, model_history, score_all_resolved

router = APIRouter(tags=["leaderboard"])


class LeaderboardRow(BaseModel):
    slug: str
    display_name: str
    provider: str
    n: int
    avg_brier: float | None = None
    avg_log_loss: float | None = None
    total_pnl: float
    accuracy: float | None = None


class LeaderboardResponse(BaseModel):
    metric: str
    rows: list[LeaderboardRow]


class HistoryRow(BaseModel):
    score_id: str
    prediction_id: str
    market_id: str
    event_id: str
    event_title: str
    market_question: str
    resolved_outcome: str | None
    predicted_probability_yes: float
    market_price: float | None
    brier_score: float
    log_loss: float
    pnl_demo_usd: float
    cum_pnl_usd: float
    was_correct: bool
    created_at: str


def _sort_key(metric: str, row: dict[str, Any]) -> tuple[int, float]:
    """Returns (placeholder-for-no-data, value). For brier/logloss lower is
    better, so we negate; for pnl higher is better. (1, ...) sorts last so
    rows without scored predictions go to the bottom.
    """
    if metric == "brier":
        v = row.get("avg_brier")
        return (1, 0.0) if v is None else (0, v)
    if metric == "logloss":
        v = row.get("avg_log_loss")
        return (1, 0.0) if v is None else (0, v)
    # pnl — descending
    v = row.get("total_pnl") or 0.0
    return (0, -float(v))


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    metric: str = Query(default="brier", pattern="^(brier|logloss|pnl)$"),
    category: str | None = None,
) -> LeaderboardResponse:
    rows = await leaderboard_rows(category=category)
    rows.sort(key=lambda r: _sort_key(metric, r))
    return LeaderboardResponse(
        metric=metric,
        rows=[LeaderboardRow(**r) for r in rows],
    )


@router.get("/models/{slug}/history", response_model=list[HistoryRow])
async def get_model_history(slug: str) -> list[HistoryRow]:
    rows = await model_history(slug)
    if not rows:
        # Distinguish 404 vs empty: we don't know which without an extra query.
        # For MVP, return an empty list either way.
        return []
    return [HistoryRow(**r) for r in rows]


@router.post("/admin/score-now")
async def score_now() -> dict[str, int]:
    """Recompute scores for every resolved market (manual backfill)."""
    return await score_all_resolved()
