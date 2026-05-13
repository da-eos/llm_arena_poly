from typing import Any

import httpx

from app.llm.base import LLMProvider, ProviderError
from app.models import LLMProviderEnum


class OpenRouterProvider(LLMProvider):
    """OpenAI-compatible chat completions through openrouter.ai."""

    provider = LLMProviderEnum.openrouter
    base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def _call(
        self, prompt: str, model_id: str, *, client: httpx.AsyncClient
    ) -> tuple[str, dict[str, Any], float | None]:
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/da-eos/llm_arena_poly",
            "X-Title": "LLM Arena",
        }
        resp = await client.post(self.base_url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise ProviderError(
                f"openrouter {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or ""

        # OpenRouter returns spend in `usage.total_cost` (USD) for some models.
        cost: float | None = None
        usage = data.get("usage") or {}
        if isinstance(usage.get("total_cost"), (int, float)):
            cost = float(usage["total_cost"])
        return text, data, cost
