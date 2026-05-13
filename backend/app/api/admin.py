from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SyncResult
from app.db import get_session
from app.services.ingestion import sync_trending_events

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/sync/polymarket", response_model=SyncResult)
async def sync_polymarket(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    min_volume: float = Query(default=10_000.0, ge=0),
) -> SyncResult:
    counts = await sync_trending_events(session, limit=limit, min_volume=min_volume)
    return SyncResult(**counts)
