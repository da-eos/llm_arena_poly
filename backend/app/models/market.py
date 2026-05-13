import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.prediction import Prediction


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    polymarket_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    question: Mapped[str] = mapped_column(String, nullable=False)
    outcomes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    resolved_outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="markets")
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="market", cascade="all, delete-orphan"
    )
