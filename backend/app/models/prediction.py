import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.llm_model import LLMModel
    from app.models.market import Market
    from app.models.score import Score


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("market_id", "llm_model_id", name="uq_prediction_market_model"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    market_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("markets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    predicted_probability_yes: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = created_at_col()

    market: Mapped["Market"] = relationship("Market", back_populates="predictions")
    llm_model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="predictions")
    score: Mapped["Score | None"] = relationship(
        "Score", back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )
