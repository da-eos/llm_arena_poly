from typing import Any

import httpx

from app.llm.base import LLMProvider, ProviderError
from app.models import LLMProviderEnum


class OpenAIProvider(LLMProvider):
    provider = LLMProviderEnum.openai
    base_url = "https://api.openai.com/v1/chat/completions"

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
        }
        resp = await client.post(self.base_url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise ProviderError(f"openai {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or ""
        return text, data, None
