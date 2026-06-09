import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.connectors.wordpress_schemas import (
    CONNECTOR_BASE_PATH,
    ConnectorDraftPostRequest,
    ConnectorEnvelope,
    ConnectorEventRequest,
    ConnectorMediaFromUrlRequest,
    ConnectorPublishPostRequest,
    ConnectorSchedulePostRequest,
    STABLE_ERROR_CODES,
)
from app.providers.base import GeneratedContent, PublishPolicy


class TrendplotConnectorContract:
    """Backend-side contract description for the future Trendplot Connector plugin."""

    api_version = "v1"
    base_path = "/wp-json/trendplot/v1"

    def capabilities(self) -> dict[str, Any]:
        return {
            "connector_name": "Trendplot Connector",
            "api_version": self.api_version,
            "base_path": self.base_path,
            "status": "implemented_backend_contract",
            "authentication": {
                "type": "site_pairing_hmac",
                "headers": [
                    "Authorization",
                    "X-Trendplot-Site-ID",
                    "X-Trendplot-Timestamp",
                    "X-Trendplot-Signature",
                ],
            },
            "endpoints": {
                "health": f"{self.base_path}/health",
                "capabilities": f"{self.base_path}/capabilities",
                "draft": f"{self.base_path}/posts/draft",
                "publish": f"{self.base_path}/posts/{{post_id}}/publish",
                "schedule": f"{self.base_path}/posts/{{post_id}}/schedule",
                "media": f"{self.base_path}/media",
                "media_from_url": f"{self.base_path}/media/from-url",
                "content_inventory": f"{self.base_path}/inventory/content",
                "product_inventory": f"{self.base_path}/inventory/products",
                "categories": f"{self.base_path}/taxonomies/categories",
                "tags": f"{self.base_path}/taxonomies/tags",
                "templates": f"{self.base_path}/templates",
                "authors": f"{self.base_path}/authors",
                "metrics": f"{self.base_path}/metrics/content",
                "backend_events": "/api/connectors/wordpress/events",
            },
            "response_envelope": {
                "success": {"ok": True, "data": {}, "warnings": [], "request_id": "req_123"},
                "error": {"ok": False, "error": {"code": "validation_failed", "message": "", "details": {}}},
                "stable_error_codes": sorted(STABLE_ERROR_CODES),
            },
            "request_schemas": {
                "draft_post": ConnectorDraftPostRequest.model_json_schema(),
                "publish_post": ConnectorPublishPostRequest.model_json_schema(),
                "schedule_post": ConnectorSchedulePostRequest.model_json_schema(),
                "media_from_url": ConnectorMediaFromUrlRequest.model_json_schema(),
                "event": ConnectorEventRequest.model_json_schema(),
            },
            "responsibilities": [
                "Expose WordPress capabilities.",
                "Own WordPress and Elementor internals.",
                "Publish drafts and live posts through stable schemas.",
                "Sync content, products, categories, tags, templates, media, and metrics.",
                "Emit content lifecycle events to Trendplot.",
            ],
            "backend_rule": "Trendplot backend must consume plugin capabilities and must not guess protected WordPress or builder metadata.",
        }


class ConnectorError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class TrendplotWordPressConnectorClient:
    provider_name = "trendplot-connector"

    def __init__(self, settings: Settings) -> None:
        if not settings.wordpress_connector_base_url:
            raise ValueError("WORDPRESS_CONNECTOR_BASE_URL is required when connector publishing is enabled.")
        if not settings.wordpress_connector_site_id:
            raise ValueError("WORDPRESS_CONNECTOR_SITE_ID is required when connector publishing is enabled.")
        if not settings.wordpress_connector_secret:
            raise ValueError("WORDPRESS_CONNECTOR_SECRET is required when connector publishing is enabled.")
        self.base_url = settings.wordpress_connector_base_url.rstrip("/")
        self.site_id = settings.wordpress_connector_site_id
        self.secret = settings.wordpress_connector_secret
        self.timeout = max(5.0, settings.wordpress_connector_timeout_seconds)
        self.base_path = CONNECTOR_BASE_PATH

    async def health(self) -> dict[str, Any]:
        return await self._get("/health")

    async def capabilities(self) -> dict[str, Any]:
        return await self._get("/capabilities")

    async def site_summary(self) -> dict[str, Any]:
        return await self._get("/site-summary")

    async def list_categories(self) -> list[dict[str, Any]]:
        data = await self._get("/taxonomies/categories")
        return _items(data)

    async def list_tags(self, search: str = "") -> list[dict[str, Any]]:
        params = {"search": search} if search.strip() else None
        data = await self._get("/taxonomies/tags", params=params)
        return _items(data)

    async def list_templates(self) -> list[dict[str, Any]]:
        data = await self._get("/templates")
        return _items(data)

    async def list_authors(self) -> list[dict[str, Any]]:
        data = await self._get("/authors")
        return _items(data)

    async def content_inventory(
        self,
        *,
        post_type: str = "post,page,product",
        updated_after: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "post_type": post_type,
            "limit": max(1, min(limit, 500)),
        }
        if updated_after:
            params["updated_after"] = updated_after
        if cursor:
            params["cursor"] = cursor
        return await self._get("/inventory/content", params=params)

    async def product_inventory(
        self,
        *,
        updated_after: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params = {"limit": max(1, min(limit, 500))}
        if updated_after:
            params["updated_after"] = updated_after
        if cursor:
            params["cursor"] = cursor
        return await self._get("/inventory/products", params=params)

    async def content_metrics(self, *, updated_after: str | None = None, limit: int = 100) -> dict[str, Any]:
        params = {"limit": max(1, min(limit, 500))}
        if updated_after:
            params["updated_after"] = updated_after
        return await self._get("/metrics/content", params=params)

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
        if policy.wordpress_status != "draft":
            raise ValueError("Connector draft publishing only accepts draft policy.")
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
        if status not in {"draft", "publish"}:
            raise ValueError("Connector publish status must be draft or publish.")
        capabilities = await self.capabilities()
        capability_map = capabilities.get("capabilities") if isinstance(capabilities.get("capabilities"), dict) else {}
        if status == "draft" and not capability_map.get("draft_publish", False):
            raise ConnectorError("capability_not_supported", "Connector does not support draft publishing.")
        if status == "publish" and not capability_map.get("live_publish", False):
            raise ConnectorError("live_publish_disabled", "Connector does not allow live publishing.")

        draft_payload = ConnectorDraftPostRequest(
            title=title,
            excerpt=excerpt,
            content_html=html_content,
            categories=categories or [],
            tags=tags or [],
            featured_media_id=featured_media,
            template=_template_payload(template),
        )
        data = await self._post("/posts/draft", draft_payload.model_dump(exclude_none=True))
        if status == "publish":
            post_id = data.get("post_id")
            if not post_id:
                raise ConnectorError("validation_failed", "Connector draft response did not include post_id.")
            publish_payload = ConnectorPublishPostRequest(
                confirm_live_publish=True,
                quality_status="passed",
                sanity_status="passed",
                compliance_status="passed",
            )
            data = await self._post(f"/posts/{post_id}/publish", publish_payload.model_dump(exclude_none=True))
        return GeneratedContent(
            content_json={
                "id": data.get("post_id"),
                "link": data.get("public_url") or data.get("url"),
                "status": data.get("status"),
                "title": title,
                "connector_response": data,
                "provider": self.provider_name,
            },
            provider=self.provider_name,
        )

    async def schedule_post(self, post_id: int | str, publish_at: str, timezone: str = "UTC") -> dict[str, Any]:
        payload = ConnectorSchedulePostRequest(publish_at=publish_at, timezone=timezone)
        return await self._post(f"/posts/{post_id}/schedule", payload.model_dump())

    async def upload_featured_image_from_url(self, image_url: str, alt_text: str = "") -> dict[str, Any]:
        payload = ConnectorMediaFromUrlRequest(url=image_url, alt_text=alt_text, usage="featured")
        return await self.upload_media_from_url(payload)

    async def upload_media_from_url(self, payload: ConnectorMediaFromUrlRequest) -> dict[str, Any]:
        return await self._post("/media/from-url", payload.model_dump(mode="json", exclude_none=True))

    async def upload_featured_image_from_path(self, image_path: str, alt_text: str = "") -> dict[str, Any]:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Featured image not found: {image_path}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            content = path.read_bytes()
            files = {"file": (path.name, content, _mime_from_path(path))}
            data = {"alt_text": alt_text, "usage": "featured"}
            response = await client.post(
                self._url("/media"),
                headers=self._headers("POST", f"{self.base_path}/media", content),
                files=files,
                data=data,
            )
        return self._parse_response(response)

    async def resolve_or_create_tags(self, tag_names: list[str]) -> dict[str, Any]:
        if not tag_names:
            return {"tags": [], "warnings": []}
        existing = await self.list_tags()
        by_name = {str(tag.get("name", "")).strip().lower(): tag for tag in existing}
        matched = [by_name[name.strip().lower()] for name in tag_names if name.strip().lower() in by_name]
        missing = [name for name in tag_names if name.strip().lower() not in by_name]
        return {"tags": matched, "warnings": [f"Connector did not create missing tags: {', '.join(missing)}"] if missing else []}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self._url(path),
                params=params,
                headers=self._headers("GET", f"{self.base_path}{path}", b""),
            )
        return self._parse_response(response)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._url(path),
                content=body,
                headers={
                    **self._headers("POST", f"{self.base_path}{path}", body),
                    "Content-Type": "application/json",
                },
            )
        return self._parse_response(response)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.base_path}{path}"

    def _headers(self, method: str, path: str, body: bytes) -> dict[str, str]:
        timestamp = str(int(time.time()))
        body_hash = hashlib.sha256(body).hexdigest()
        base = f"{method.upper()}\n{path}\n{timestamp}\n{body_hash}"
        signature = hmac.new(self.secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "X-Trendplot-Site-ID": self.site_id,
            "X-Trendplot-Timestamp": timestamp,
            "X-Trendplot-Signature": signature,
            "Accept": "application/json",
        }

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        payload = response.json()
        envelope = ConnectorEnvelope.model_validate(payload)
        if not envelope.ok:
            error = envelope.error
            raise ConnectorError(
                error.code if error else "internal_error",
                error.message if error else "Connector request failed.",
                error.details if error else {},
            )
        data = envelope.data
        if isinstance(data, dict):
            result = dict(data)
        elif isinstance(data, list):
            result = {"items": data}
        else:
            result = {}
        result["_connector"] = {
            "api_version": envelope.api_version,
            "plugin_version": envelope.plugin_version,
            "site_id": envelope.site_id,
            "warnings": envelope.warnings,
            "request_id": envelope.request_id,
        }
        return result


class FallbackWordPressPublisher:
    provider_name = "wordpress-fallback"

    def __init__(self, primary: Any, fallback: Any, *, fallback_enabled: bool = True) -> None:
        self.primary = primary
        self.fallback = fallback
        self.fallback_enabled = fallback_enabled

    async def publish_draft(self, *args: Any, **kwargs: Any) -> GeneratedContent:
        return await self._call("publish_draft", *args, **kwargs)

    async def publish_post(self, *args: Any, **kwargs: Any) -> GeneratedContent:
        return await self._call("publish_post", *args, **kwargs)

    async def list_categories(self) -> list[dict[str, Any]]:
        return await self._call("list_categories")

    async def list_tags(self, search: str = "") -> list[dict[str, Any]]:
        return await self._call("list_tags", search=search)

    async def list_templates(self) -> list[dict[str, Any]]:
        return await self._call("list_templates")

    async def upload_featured_image_from_url(self, image_url: str, alt_text: str = "") -> dict[str, Any]:
        return await self._call("upload_featured_image_from_url", image_url=image_url, alt_text=alt_text)

    async def upload_featured_image_from_path(self, image_path: str, alt_text: str = "") -> dict[str, Any]:
        return await self._call("upload_featured_image_from_path", image_path=image_path, alt_text=alt_text)

    async def resolve_or_create_tags(self, tag_names: list[str]) -> dict[str, Any]:
        return await self._call("resolve_or_create_tags", tag_names)

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return await getattr(self.primary, method)(*args, **kwargs)
        except Exception:
            if not self.fallback_enabled:
                raise
            return await getattr(self.fallback, method)(*args, **kwargs)


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("items", data.get("terms", data.get("templates", [])))
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def _template_payload(template: str | None) -> dict[str, str] | None:
    if not template:
        return None
    builder = "elementor" if str(template).startswith("elementor") else None
    return {"key": str(template), "builder": builder, "mode": "html_widget" if builder == "elementor" else ""}


def _mime_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"
