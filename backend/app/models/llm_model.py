import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._base import created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.prediction import Prediction


class LLMProviderEnum(str, enum.Enum):
    anthropic = "anthropic"
    openai = "openai"
    google = "google"
    openrouter = "openrouter"


class LLMModel(Base):
    __tablename__ = "llm_models"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    provider: Mapped[LLMProviderEnum] = mapped_column(
        Enum(LLMProviderEnum, name="llm_provider"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    model_id_at_provider: Mapped[str] = mapped_column(String, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_at: Mapped[datetime] = created_at_col()

    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="llm_model"
    )
