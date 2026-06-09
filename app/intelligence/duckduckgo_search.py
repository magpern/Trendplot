from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from app.config import Settings

logger = logging.getLogger(__name__)


class DuckDuckGoSearchProvider:
    provider_name = "duckduckgo"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return True

    async def search_web(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return []
        configured_max = max(1, int(getattr(self.settings, "duckduckgo_search_max_results", 10)))
        limit = max(1, min(int(max_results or 5), configured_max))
        timeout = max(1.0, float(getattr(self.settings, "duckduckgo_search_timeout_seconds", 10.0)))
        try:
            raw_results = await asyncio.wait_for(
                asyncio.to_thread(self._search_sync, cleaned_query, limit, timeout),
                timeout=timeout + 2.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "DuckDuckGo search timed out.",
                extra={"provider": self.provider_name, "query": cleaned_query},
            )
            return []
        except Exception as exc:  # noqa: BLE001 - fail-open for discovery
            logger.warning(
                "DuckDuckGo search failed.",
                extra={"provider": self.provider_name, "query": cleaned_query, "error": str(exc)},
            )
            return []

        results: list[dict[str, Any]] = []
        for item in raw_results or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("href") or item.get("url") or "").strip()
            if not url:
                continue
            domain = _domain_of(url)
            results.append(
                {
                    "source_type": "web",
                    "query": cleaned_query,
                    "title": str(item.get("title") or ""),
                    "url": url,
                    "snippet": str(item.get("body") or item.get("snippet") or ""),
                    "domain": domain,
                    "provider": self.provider_name,
                    "status": "ok",
                    "verified": False,
                }
            )
        if not results:
            logger.warning(
                "DuckDuckGo search returned no usable results.",
                extra={"provider": self.provider_name, "query": cleaned_query},
            )
        return results

    def _search_sync(self, query: str, limit: int, timeout: float) -> list[dict[str, Any]]:
        try:
            from ddgs import DDGS
            from ddgs.exceptions import DDGSException, TimeoutException
        except ImportError as exc:
            logger.warning(
                "DuckDuckGo search package missing (install ddgs).",
                extra={"provider": self.provider_name, "error": str(exc)},
            )
            return []

        try:
            return list(
                DDGS(timeout=int(max(1, timeout))).text(
                    query,
                    max_results=limit,
                    backend="duckduckgo",
                )
            )
        except TimeoutException as exc:
            logger.warning(
                "DuckDuckGo search backend timed out.",
                extra={"provider": self.provider_name, "query": query, "error": str(exc)},
            )
            return []
        except DDGSException as exc:
            logger.warning(
                "DuckDuckGo search returned no results.",
                extra={"provider": self.provider_name, "query": query, "error": str(exc)},
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "DuckDuckGo search unexpected error.",
                extra={"provider": self.provider_name, "query": query, "error": str(exc)},
            )
            return []


def _domain_of(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().lstrip("www.")
