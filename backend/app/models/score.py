import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.prediction import Prediction


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[uuid.UUID] = uuid_pk()
    prediction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    brier_score: Mapped[float] = mapped_column(Float, nullable=False)
    log_loss: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_demo_usd: Mapped[float] = mapped_column(Float, nullable=False)
    was_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = created_at_col()

    prediction: Mapped["Prediction"] = relationship("Prediction", back_populates="score")
