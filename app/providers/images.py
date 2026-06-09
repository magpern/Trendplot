from app.config import Settings
from app.providers.base import GeneratedContent


class PlaceholderImageProvider:
    provider_name = "placeholder-image"

    def __init__(self, settings: Settings) -> None:
        self.image_url = settings.placeholder_image_url

    async def fetch_featured_image(self, query: str) -> GeneratedContent:
        return GeneratedContent(
            content_json={
                "url": None,
                "alt_text": query,
                "caption": "",
                "status": "missing",
                "reason": "No real image provider is configured; placeholder images are not inserted by default.",
            },
            provider=self.provider_name,
        )
