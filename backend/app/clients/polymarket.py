import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.settings import get_settings

logger = logging.getLogger(__name__)


class PolymarketError(Exception):
    pass


class RetryableHTTPError(PolymarketError):
    pass


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RetryableHTTPError):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    return False


class PolymarketClient:
    """Async client for Polymarket Gamma API.

    Concurrency-capped via an internal semaphore (~5 req/s effective).
    Retries 429 / 5xx / transport errors up to 3 times with exponential backoff.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
        max_concurrency: int = 5,
    ) -> None:
        self._base_url = (base_url or get_settings().polymarket_base_url).rstrip("/")
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": "llmarena/0.1"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "PolymarketClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @retry(
        retry=retry_if_exception_type((RetryableHTTPError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with self._semaphore:
            resp = await self._client.request(method, path, **kwargs)
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            raise RetryableHTTPError(f"polymarket {method} {path} → {resp.status_code}")
        if resp.status_code >= 400:
            raise PolymarketError(
                f"polymarket {method} {path} → {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    async def fetch_trending_events(
        self,
        limit: int = 50,
        min_volume: float = 10_000.0,
    ) -> list[dict[str, Any]]:
        params = {
            "limit": limit,
            "closed": "false",
            "active": "true",
            "order": "volume",
            "ascending": "false",
        }
        data = await self._request("GET", "/events", params=params)
        if not isinstance(data, list):
            raise PolymarketError(f"unexpected /events payload: {type(data).__name__}")
        return [
            e for e in data
            if isinstance(e.get("volume"), (int, float)) and e["volume"] >= min_volume
        ]

    async def fetch_event_by_id(self, polymarket_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/events/{polymarket_id}")
        if not isinstance(data, dict):
            raise PolymarketError(f"unexpected /events/{polymarket_id} payload")
        return data
