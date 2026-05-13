"""Common types and base class for LLM providers."""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.models import LLMProviderEnum

logger = logging.getLogger(__name__)


JSON_INSTRUCTION = (
    'Ответь ОДНИМ JSON-объектом, без пояснений и без markdown-блоков. '
    'Схема: {"probability_yes": число 0..1, "reasoning": строка, '
    '"confidence": число 0..1}. '
    '"probability_yes" — твоя оценка вероятности того, что рынок резолвнется YES. '
    'Поле "reasoning" пиши ОБЯЗАТЕЛЬНО НА РУССКОМ ЯЗЫКЕ, 2–4 предложения, '
    'без воды, по делу. "confidence" — твоя самооценка уверенности.'
)


class PredictionResult(BaseModel):
    probability_yes: float = Field(ge=0.0, le=1.0)
    reasoning: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    raw_response: dict[str, Any]
    latency_ms: int
    cost_usd: float | None = None

    @field_validator("reasoning")
    @classmethod
    def _strip_reasoning(cls, v: str) -> str:
        return v.strip()


class ProviderError(Exception):
    pass


class ProviderDisabledError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    """Raised when the model output cannot be parsed as the required JSON."""


def _extract_json_blob(text: str) -> dict[str, Any]:
    """Parse a JSON object out of a model response.

    Strategy: try strict json.loads first; if that fails, fall back to grabbing
    the first balanced `{...}` substring (models occasionally wrap the JSON in
    backticks or prose).
    """
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        try:
            obj = json.loads(fence.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Greedy: first '{' to last '}'.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise ProviderResponseError(f"could not extract JSON from response: {text[:300]!r}")


def _coerce_result(
    parsed: dict[str, Any],
    *,
    raw_response: dict[str, Any],
    latency_ms: int,
    cost_usd: float | None,
) -> PredictionResult:
    try:
        return PredictionResult(
            probability_yes=float(parsed["probability_yes"]),
            reasoning=str(parsed.get("reasoning") or ""),
            confidence=(
                float(parsed["confidence"])
                if parsed.get("confidence") is not None
                else None
            ),
            raw_response=raw_response,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ProviderResponseError(f"invalid prediction shape: {exc}") from exc


class LLMProvider(ABC):
    provider: LLMProviderEnum

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise ProviderDisabledError(
                f"provider {self.provider.value} has no API key configured"
            )

    @abstractmethod
    async def _call(
        self, prompt: str, model_id: str, *, client: httpx.AsyncClient
    ) -> tuple[str, dict[str, Any], float | None]:
        """Return (text_response, raw_payload, cost_usd_or_None)."""

    async def predict(self, prompt: str, model_id: str) -> PredictionResult:
        self._ensure_enabled()
        full_prompt = f"{prompt.strip()}\n\n{JSON_INSTRUCTION}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            start = time.monotonic()
            text, raw, cost = await self._call(full_prompt, model_id, client=client)
            latency_ms = int((time.monotonic() - start) * 1000)
            try:
                parsed = _extract_json_blob(text)
                return _coerce_result(
                    parsed, raw_response=raw, latency_ms=latency_ms, cost_usd=cost
                )
            except ProviderResponseError as first_err:
                logger.info(
                    "provider=%s model=%s first JSON parse failed: %s — retrying",
                    self.provider.value, model_id, first_err,
                )

            # Second attempt with a stricter suffix.
            retry_prompt = (
                f"{full_prompt}\n\n"
                "Предыдущий ответ не был валидным JSON. Верни ТОЛЬКО JSON-объект "
                "по указанной схеме и ничего больше. reasoning — на русском."
            )
            start2 = time.monotonic()
            text2, raw2, cost2 = await self._call(retry_prompt, model_id, client=client)
            latency_ms2 = int((time.monotonic() - start2) * 1000)
            parsed2 = _extract_json_blob(text2)  # will raise ProviderResponseError if bad
            total_cost = (cost or 0.0) + (cost2 or 0.0) if (cost or cost2) else None
            return _coerce_result(
                parsed2,
                raw_response={"first_attempt": raw, "retry": raw2},
                latency_ms=latency_ms + latency_ms2,
                cost_usd=total_cost,
            )
