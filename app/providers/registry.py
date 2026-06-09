from dataclasses import dataclass

from app.config import Settings
from app.content_generation import OpenAIContentGenerationProvider
from app.providers.base import (
    ContentGenerationProvider,
    ImageProvider,
    SocialPublisher,
    VideoProvider,
    WordPressPublisher,
)
from app.providers.images import PlaceholderImageProvider
from app.providers.youtube import YouTubeVideoProvider
from app.publishers.placeholders import PlaceholderSocialPublisher
from app.connectors.phase1_publisher import DisabledWordPressPublisher, Phase1WordPressPublisher


@dataclass(slots=True)
class ProviderRegistry:
    content_generation: ContentGenerationProvider
    image: ImageProvider
    video: VideoProvider
    wordpress: WordPressPublisher
    social_publishers: dict[str, SocialPublisher]

    def social_publisher(self, platform: str) -> SocialPublisher:
        return self.social_publishers[platform.lower()]


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    if _connector_configured(settings):
        wordpress: WordPressPublisher = Phase1WordPressPublisher(settings)
    else:
        wordpress = DisabledWordPressPublisher()
    return ProviderRegistry(
        content_generation=OpenAIContentGenerationProvider(settings),
        image=PlaceholderImageProvider(settings),
        video=YouTubeVideoProvider(settings),
        wordpress=wordpress,
        social_publishers={
            "instagram": PlaceholderSocialPublisher("Instagram"),
            "tiktok": PlaceholderSocialPublisher("TikTok"),
        },
    )


def _connector_configured(settings: Settings) -> bool:
    return bool(
        settings.wordpress_connector_enabled
        and settings.wordpress_connector_base_url.strip()
        and settings.wordpress_connector_site_id.strip()
        and settings.wordpress_connector_secret.strip()
    )
