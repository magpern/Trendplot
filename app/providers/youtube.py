from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.providers.base import GeneratedContent


class YouTubeVideoProvider:
    provider_name = "youtube"

    def __init__(self, settings: Settings) -> None:
        if not settings.youtube_api_key:
            raise ValueError("YOUTUBE_API_KEY is required.")
        self.api_key = settings.youtube_api_key

    async def fetch_candidates(self, query: str, max_results: int = 8) -> GeneratedContent:
        max_results = max(5, min(max_results, 10))
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": str(max_results),
            "key": self.api_key,
        }
        url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        candidates = []
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            candidates.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "channel_title": snippet.get("channelTitle"),
                    "published_at": snippet.get("publishedAt"),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                }
            )

        return GeneratedContent(
            content_json={
                "query": query,
                "candidates": candidates,
            },
            provider=self.provider_name,
        )

    async def fetch_video(self, query: str) -> GeneratedContent:
        candidates = await self.fetch_candidates(query, max_results=5)
        first = next(iter(candidates.content_json.get("candidates", [])), None)
        if not first:
            return GeneratedContent(
                content_json={"query": query, "video": None, "status": "not_found"},
                provider=self.provider_name,
            )

        return GeneratedContent(
            content_json={
                **first,
                "query": query,
                "embed_url": f"https://www.youtube.com/embed/{first['video_id']}",
                "status": "selected_without_ai_evaluation",
            },
            provider=self.provider_name,
        )
