from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.connectors.phase1_client import TrendplotPhase1ConnectorClient
from app.providers.base import GeneratedContent, PublishPolicy


class ConnectorNotConfiguredError(RuntimeError):
    pass


class Phase1WordPressPublisher:
    """WordPress publisher adapter using Trendplot Connector plugin Phase 1 only."""

    provider_name = "trendplot-connector-phase1"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self) -> TrendplotPhase1ConnectorClient:
        if not self.settings.wordpress_connector_enabled:
            raise ConnectorNotConfiguredError("WORDPRESS_CONNECTOR_ENABLED is false.")
        return TrendplotPhase1ConnectorClient(
            base_url=self.settings.wordpress_connector_base_url,
            site_id=self.settings.wordpress_connector_site_id,
            shared_secret=self.settings.wordpress_connector_secret,
            timeout_seconds=self.settings.wordpress_connector_timeout_seconds,
        )

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
        return await self.publish_post(
            title=title,
            html_content=html_content,
            status="draft",
            excerpt=excerpt,
            categories=categories,
            tags=tags,
            featured_media=featured_media,
            template=template,
        )

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
        if status != "draft":
            raise ValueError("Live publishing is not supported. Connector Phase 1 supports drafts only.")
        body_dict = {
            "title": title,
            "content": html_content,
            "excerpt": excerpt or "",
            "categories": categories or [],
            "tags": tags or [],
            "trendplot_article_id": "",
            "trendplot_source": "trendplot",
            "trendplot_generated": "",
            "related_products": [],
            "related_articles": [],
        }
        body_json = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)
        response = await self._client().create_draft(body_json)
        return GeneratedContent(
            content_json={
                "id": response.get("id"),
                "link": response.get("url"),
                "edit_url": response.get("edit_url"),
                "status": response.get("status") or "draft",
                "title": title,
                "connector_response": response,
                "provider": self.provider_name,
            },
            provider=self.provider_name,
        )

    async def list_categories(self) -> list[dict[str, Any]]:
        data = await self._client().list_categories()
        return _items(data)

    async def list_tags(self, search: str = "") -> list[dict[str, Any]]:
        data = await self._client().list_tags(search=search)
        return _items(data)

    async def list_templates(self) -> list[dict[str, Any]]:
        return []

    async def resolve_or_create_tags(self, tag_names: list[str]) -> dict[str, Any]:
        if not tag_names:
            return {"tags": [], "warnings": []}
        existing = await self.list_tags()
        by_name = {str(tag.get("name") or "").strip().lower(): tag for tag in existing}
        matched = [by_name[name.strip().lower()] for name in tag_names if name.strip().lower() in by_name]
        missing = [name for name in tag_names if name.strip().lower() not in by_name]
        warnings = (
            [f"Connector Phase 1 does not create tags automatically: {', '.join(missing)}"]
            if missing
            else []
        )
        return {"tags": matched, "warnings": warnings}

    async def upload_featured_image_from_url(self, image_url: str, alt_text: str = "") -> dict[str, Any]:
        raise NotImplementedError("Featured image upload is not available in connector Phase 1.")

    async def upload_featured_image_from_path(self, image_path: str, alt_text: str = "") -> dict[str, Any]:
        raise NotImplementedError("Featured image upload is not available in connector Phase 1.")


class DisabledWordPressPublisher:
    provider_name = "wordpress-disabled"

    async def publish_draft(self, *args: Any, **kwargs: Any) -> GeneratedContent:
        raise ConnectorNotConfiguredError("WordPress connector is not configured.")

    async def publish_post(self, *args: Any, **kwargs: Any) -> GeneratedContent:
        raise ConnectorNotConfiguredError("WordPress connector is not configured.")

    async def list_categories(self) -> list[dict[str, Any]]:
        return []

    async def list_tags(self, search: str = "") -> list[dict[str, Any]]:
        return []

    async def list_templates(self) -> list[dict[str, Any]]:
        return []

    async def resolve_or_create_tags(self, tag_names: list[str]) -> dict[str, Any]:
        return {"tags": [], "warnings": []}

    async def upload_featured_image_from_url(self, image_url: str, alt_text: str = "") -> dict[str, Any]:
        raise ConnectorNotConfiguredError("WordPress connector is not configured.")

    async def upload_featured_image_from_path(self, image_path: str, alt_text: str = "") -> dict[str, Any]:
        raise ConnectorNotConfiguredError("WordPress connector is not configured.")


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("items", data.get("categories", data.get("tags", data)))
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []
