import httpx

from app.providers.base import GeneratedContent, ImageProvider, VideoProvider


class EnrichmentService:
    def __init__(
        self,
        image_provider: ImageProvider,
        video_provider: VideoProvider,
    ) -> None:
        self.image_provider = image_provider
        self.video_provider = video_provider

    async def fetch_featured_image(self, query: str) -> GeneratedContent:
        return await self.image_provider.fetch_featured_image(query)

    async def fetch_youtube_video(self, query: str) -> GeneratedContent:
        try:
            return await self.video_provider.fetch_video(query)
        except httpx.HTTPError as exc:
            return GeneratedContent(
                content_json={
                    "query": query,
                    "video": None,
                    "status": "failed",
                    "error": str(exc),
                },
                provider=getattr(self.video_provider, "provider_name", "video-provider"),
            )

    async def fetch_youtube_candidates(self, query: str, max_results: int = 8) -> GeneratedContent:
        try:
            return await self.video_provider.fetch_candidates(query, max_results=max_results)
        except httpx.HTTPError as exc:
            return GeneratedContent(
                content_json={
                    "query": query,
                    "candidates": [],
                    "status": "failed",
                    "error": str(exc),
                },
                provider=getattr(self.video_provider, "provider_name", "video-provider"),
            )
