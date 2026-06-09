from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchProvider:
    provider_name = "brave-search"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._api_key = str(settings.brave_search_api_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search_web(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        if not self.is_configured():
            return []
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return []
        limit = max(1, min(int(max_results or 5), 20))
        timeout = max(1.0, float(getattr(self.settings, "web_search_timeout_seconds", 10.0)))
        params = {"q": cleaned_query, "count": str(limit)}
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(BRAVE_WEB_SEARCH_URL, params=params, headers=headers)
                if response.status_code == 429:
                    logger.warning(
                        "Brave Search rate limit reached.",
                        extra={
                            "provider": self.provider_name,
                            "query": cleaned_query,
                            "status_code": response.status_code,
                        },
                    )
                    return []
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            logger.warning(
                "Brave Search request timed out.",
                extra={"provider": self.provider_name, "query": cleaned_query, "error": str(exc)},
            )
            return []
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Brave Search HTTP error.",
                extra={
                    "provider": self.provider_name,
                    "query": cleaned_query,
                    "status_code": exc.response.status_code,
                    "error": str(exc),
                },
            )
            return []
        except httpx.HTTPError as exc:
            logger.warning(
                "Brave Search request failed.",
                extra={"provider": self.provider_name, "query": cleaned_query, "error": str(exc)},
            )
            return []
        except Exception as exc:  # noqa: BLE001 - fail-open for discovery
            logger.warning(
                "Brave Search unexpected error.",
                extra={"provider": self.provider_name, "query": cleaned_query, "error": str(exc)},
            )
            return []

        results: list[dict[str, Any]] = []
        web_block = payload.get("web") if isinstance(payload.get("web"), dict) else {}
        for item in web_block.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            domain = _domain_of(url)
            results.append(
                {
                    "source_type": "web",
                    "query": cleaned_query,
                    "title": str(item.get("title") or ""),
                    "url": url,
                    "snippet": str(item.get("description") or ""),
                    "domain": domain,
                    "provider": self.provider_name,
                    "status": "ok",
                    "verified": False,
                }
            )
        return results


def _domain_of(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().lstrip("www.")
