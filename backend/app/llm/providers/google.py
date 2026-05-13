from typing import Any

import httpx

from app.llm.base import LLMProvider, ProviderError
from app.models import LLMProviderEnum


class GoogleProvider(LLMProvider):
    provider = LLMProviderEnum.google
    base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def _call(
        self, prompt: str, model_id: str, *, client: httpx.AsyncClient
    ) -> tuple[str, dict[str, Any], float | None]:
        url = f"{self.base_url}/{model_id}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        headers = {"Content-Type": "application/json"}
        resp = await client.post(
            url, json=payload, headers=headers, params={"key": self._api_key}
        )
        if resp.status_code >= 400:
            raise ProviderError(f"google {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        candidates = data.get("candidates") or []
        parts: list[str] = []
        if candidates:
            content = candidates[0].get("content") or {}
            for p in content.get("parts") or []:
                if isinstance(p, dict) and "text" in p:
                    parts.append(str(p["text"]))
        return "".join(parts), data, None
