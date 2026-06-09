from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ProviderUsage:
    token_input: int | None = None
    token_output: int | None = None
    estimated_cost: float | None = None


@dataclass(slots=True)
class GeneratedContent:
    content_text: str | None = None
    content_json: dict[str, Any] | None = None
    provider: str = ""
    model: str | None = None
    task_type: str | None = None
    usage: ProviderUsage | None = None
    raw_response: dict[str, Any] | None = None
    reasoning_enabled: bool = False
    reasoning_effort: str | None = None
    reasoning_supported: bool = False
    reasoning_source: str | None = None


@dataclass(slots=True)
class PublishPolicy:
    mode: str = "manual"
    wordpress_status: str = "draft"
    human_review_required: bool = True


class ContentGenerationProvider(Protocol):
    provider_name: str
    model: str

    async def generate_article(self, prompt: str, task_type: str | None = None) -> GeneratedContent:
        ...

    async def generate_article_markdown(self, prompt: str) -> GeneratedContent:
        ...

    async def generate_seo_metadata(self, prompt: str) -> GeneratedContent:
        ...

    async def generate_social_post(self, platform: str, prompt: str) -> GeneratedContent:
        ...

    async def generate_website_analysis(self, prompt: str) -> GeneratedContent:
        ...

    async def evaluate_youtube_candidates(self, prompt: str) -> GeneratedContent:
        ...


class ImageProvider(Protocol):
    provider_name: str

    async def fetch_featured_image(self, query: str) -> GeneratedContent:
        ...


class VideoProvider(Protocol):
    provider_name: str

    async def fetch_candidates(self, query: str, max_results: int = 8) -> GeneratedContent:
        ...

    async def fetch_video(self, query: str) -> GeneratedContent:
        ...


class WordPressPublisher(Protocol):
    provider_name: str

    async def publish_draft(
        self,
        title: str,
        html_content: str,
        policy: PublishPolicy,
        excerpt: str | None = None,
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        featured_media: int | None = None,
        template: str | None = None,
    ) -> GeneratedContent:
        ...

    async def publish_post(
        self,
        title: str,
        html_content: str,
        status: str,
        excerpt: str | None = None,
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        featured_media: int | None = None,
        template: str | None = None,
    ) -> GeneratedContent:
        ...

    async def list_categories(self) -> list[dict[str, Any]]:
        ...

    async def list_tags(self, search: str = "") -> list[dict[str, Any]]:
        ...

    async def list_templates(self) -> list[dict[str, Any]]:
        ...

    async def resolve_or_create_tags(self, tag_names: list[str]) -> dict[str, Any]:
        ...

    async def upload_featured_image_from_url(self, image_url: str, alt_text: str = "") -> dict[str, Any]:
        ...

    async def upload_featured_image_from_path(self, image_path: str, alt_text: str = "") -> dict[str, Any]:
        ...


class SocialPublisher(Protocol):
    provider_name: str
    platform: str

    async def publish(self, content: str, policy: PublishPolicy) -> GeneratedContent:
        ...
