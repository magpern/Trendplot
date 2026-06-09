from typing import Any, Protocol


class SerpShapeProvider(Protocol):
    async def get_serp_shape(self, keyword: str, locale: str | None = None) -> dict:
        """Return non-authoritative SERP shape signals for future opportunity scoring."""


class FreshnessSignalProvider(Protocol):
    async def get_freshness_signals(self, topic: str) -> dict:
        """Return trend/freshness hints for future campaign planning."""


class WebSearchProvider(Protocol):
    provider_name: str

    async def search_web(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Return web search results from an approved API/provider."""


class AcademicSearchProvider(Protocol):
    provider_name: str

    async def search_academic(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Return academic results from an approved source such as PubMed."""


class YouTubeSearchProvider(Protocol):
    provider_name: str

    async def search_youtube(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Return YouTube search results through the configured YouTube Data API."""


class RedditSignalProvider(Protocol):
    provider_name: str

    async def search_reddit(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Return Reddit/community signals from an approved API/provider."""


class TrendSignalProvider(Protocol):
    provider_name: str

    async def search_trends(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Return trend/freshness signals from an approved API/provider."""


class NullIntelligenceProvider:
    provider_name = "null-intelligence"

    async def get_serp_shape(self, keyword: str, locale: str | None = None) -> dict:
        return {
            "status": "not_configured",
            "keyword": keyword,
            "locale": locale,
            "features": [],
        }

    async def get_freshness_signals(self, topic: str) -> dict:
        return {
            "status": "not_configured",
            "topic": topic,
            "freshness_score": None,
            "reason": "External intelligence providers are scaffolded but not integrated.",
        }

    async def search_web(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        return [_not_configured_result("web", query, self.provider_name)]

    async def search_academic(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        return [_not_configured_result("academic", query, self.provider_name)]

    async def search_youtube(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        return [_not_configured_result("youtube", query, self.provider_name)]

    async def search_reddit(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        return [_not_configured_result("reddit", query, self.provider_name)]

    async def search_trends(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        return [_not_configured_result("trend", query, self.provider_name)]


class VideoProviderYouTubeSearchAdapter:
    provider_name = "youtube"

    def __init__(self, video_provider: Any) -> None:
        self.video_provider = video_provider
        self.provider_name = getattr(video_provider, "provider_name", "youtube")

    async def search_youtube(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        result = await self.video_provider.fetch_candidates(query, max_results=max_results)
        payload = result.content_json or {}
        return [
            {
                "source_type": "youtube",
                "query": query,
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("description"),
                "published_at": item.get("published_at"),
                "channel_title": item.get("channel_title"),
                "provider": self.provider_name,
                "verified": False,
            }
            for item in payload.get("candidates", [])
            if isinstance(item, dict)
        ]


def _not_configured_result(source_type: str, query: str, provider: str) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "query": query,
        "title": "External provider not configured",
        "url": "",
        "snippet": "No external results were fetched because this provider is disabled or not configured.",
        "provider": provider,
        "status": "not_configured",
        "verified": False,
    }
