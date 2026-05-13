import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import EventDetail, EventList, EventRead, OkResponse
from app.db import get_session
from app.models import Event

router = APIRouter(prefix="/events", tags=["events"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=EventList)
async def list_events(
    session: SessionDep,
    tracked: bool | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EventList:
    stmt = select(Event)
    count_stmt = select(func.count()).select_from(Event)
    if tracked is not None:
        stmt = stmt.where(Event.is_tracked == tracked)
        count_stmt = count_stmt.where(Event.is_tracked == tracked)
    if category is not None:
        stmt = stmt.where(Event.category == category)
        count_stmt = count_stmt.where(Event.category == category)

    stmt = stmt.order_by(Event.volume.desc().nullslast()).limit(limit).offset(offset)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).scalars().all()
    return EventList(
        items=[EventRead.model_validate(e) for e in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _get_event_or_404(session: AsyncSession, event_id: uuid.UUID) -> Event:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.markets))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return event


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(event_id: uuid.UUID, session: SessionDep) -> EventDetail:
    event = await _get_event_or_404(session, event_id)
    return EventDetail.model_validate(event)


@router.post("/{event_id}/track", response_model=OkResponse)
async def track_event(event_id: uuid.UUID, session: SessionDep) -> OkResponse:
    event = await _get_event_or_404(session, event_id)
    event.is_tracked = True
    await session.commit()
    return OkResponse()


@router.post("/{event_id}/untrack", response_model=OkResponse)
async def untrack_event(event_id: uuid.UUID, session: SessionDep) -> OkResponse:
    event = await _get_event_or_404(session, event_id)
    event.is_tracked = False
    await session.commit()
    return OkResponse()
