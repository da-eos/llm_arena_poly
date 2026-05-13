from typing import Any

import httpx

from app.llm.base import LLMProvider, ProviderError
from app.models import LLMProviderEnum


class AnthropicProvider(LLMProvider):
    provider = LLMProviderEnum.anthropic
    base_url = "https://api.anthropic.com/v1/messages"
    api_version = "2023-06-01"

    async def _call(
        self, prompt: str, model_id: str, *, client: httpx.AsyncClient
    ) -> tuple[str, dict[str, Any], float | None]:
        payload = {
            "model": model_id,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self._api_key or "",
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }
        resp = await client.post(self.base_url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise ProviderError(
                f"anthropic {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        # content is a list of blocks; concatenate text blocks.
        parts: list[str] = []
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts), data, None
