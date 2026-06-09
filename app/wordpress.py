import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import bleach
import httpx
import markdown

from app.config import Settings
from app.providers.base import GeneratedContent, PublishPolicy


ALLOWED_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "details",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "iframe",
    "img",
    "li",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "strong",
    "summary",
    "ul",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel", "class", "id"],
    "img": ["alt", "src", "title", "class", "id"],
    "iframe": [
        "allow",
        "allowfullscreen",
        "frameborder",
        "height",
        "loading",
        "referrerpolicy",
        "src",
        "title",
        "width",
    ],
}

ELEMENTOR_TEMPLATE_KEYS = {"elementor_header_footer", "elementor_canvas"}


def markdown_to_sanitized_html(markdown_text: str) -> str:
    html = markdown.markdown(markdown_text, extensions=["extra", "sane_lists"])
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=["http", "https"],
        strip=True,
    )


class WordPressClient:
    provider_name = "wordpress"

    def __init__(self, settings: Settings) -> None:
        if not settings.wordpress_base_url:
            raise ValueError("WORDPRESS_BASE_URL is required.")
        if not settings.wordpress_username or not settings.wordpress_app_password:
            raise ValueError("WORDPRESS_USERNAME and WORDPRESS_APP_PASSWORD are required.")

        self.base_url = settings.wordpress_base_url.rstrip("/")
        self.username = settings.wordpress_username
        self.app_password = settings.wordpress_app_password
        self.default_template = normalize_template_key(settings.wordpress_default_template)
        self.auto_create_tags = settings.wordpress_auto_create_tags
        self.max_tags = max(1, settings.wordpress_max_tags)
        self.upload_featured_image = settings.wordpress_upload_featured_image
        self.fail_on_template_error = settings.wordpress_fail_on_template_error

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
            raise ValueError("WordPress publisher only supports draft status for the MVP.")
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
            raise ValueError("WordPress status must be 'draft' or 'publish'.")
        template = normalize_template_key(template or "")
        payload: dict[str, Any] = {
            "title": title,
            "content": html_content,
            "status": status,
        }
        if excerpt:
            payload["excerpt"] = excerpt
        if categories:
            payload["categories"] = categories
        if tags:
            payload["tags"] = tags
        if featured_media:
            payload["featured_media"] = featured_media

        if template:
            payload["template"] = template
        template_result: dict[str, Any] = {"template": template or "", "applied": False, "warnings": []}
        elementor_result: dict[str, Any] = {"requested": False, "applied": False, "warnings": []}
        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=30,
        ) as client:
            response = await client.post(
                f"{self.base_url}/wp-json/wp/v2/posts",
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()
            post_id = response_payload.get("id")
            if post_id and template:
                template_result = _template_result_from_payload(
                    response_payload,
                    template,
                    method="create_payload",
                    warnings=[],
                )
            if post_id and template and not template_result.get("applied"):
                template_result = await self._apply_template(client, int(post_id), template)
            if post_id and _is_elementor_template(template):
                elementor_result = await self._apply_elementor_builder_metadata(
                    client,
                    int(post_id),
                    html_content=html_content,
                    template=template,
                )

        return GeneratedContent(
            content_json={
                "id": response_payload.get("id"),
                "link": response_payload.get("link"),
                "status": response_payload.get("status"),
                "title": response_payload.get("title"),
                "payload": payload,
                "template_result": template_result,
                "elementor_result": elementor_result,
            },
            provider=self.provider_name,
        )

    async def list_categories(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=30,
        ) as client:
            response = await client.get(
                f"{self.base_url}/wp-json/wp/v2/categories",
                params={"per_page": 100, "hide_empty": False},
            )
            response.raise_for_status()
            categories = response.json()
        return [
            {
                "id": category.get("id"),
                "name": category.get("name"),
                "slug": category.get("slug"),
            }
            for category in categories
        ]

    async def list_tags(self, search: str = "") -> list[dict[str, Any]]:
        params: dict[str, Any] = {"per_page": 100, "hide_empty": False}
        if search.strip():
            params["search"] = search.strip()
        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=30,
        ) as client:
            response = await client.get(f"{self.base_url}/wp-json/wp/v2/tags", params=params)
            response.raise_for_status()
            tags = response.json()
        return [
            {
                "id": tag.get("id"),
                "name": tag.get("name"),
                "slug": tag.get("slug"),
                "count": tag.get("count"),
            }
            for tag in tags
        ]

    async def list_templates(self) -> list[dict[str, Any]]:
        templates = {
            "": {"key": "", "label": "Default theme template", "source": "wordpress"},
            "elementor_header_footer": {
                "key": "elementor_header_footer",
                "label": "Elementor Full Width",
                "source": "elementor",
                "aliases": ["elementor_full_width"],
            },
            "elementor_canvas": {
                "key": "elementor_canvas",
                "label": "Elementor Canvas",
                "source": "elementor",
                "note": "Usually not recommended for SEO blog posts because it removes header/footer.",
            },
        }
        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=30,
        ) as client:
            try:
                response = await client.get(f"{self.base_url}/wp-json/wp/v2/types/post", params={"context": "edit"})
                response.raise_for_status()
                payload = response.json()
                for key, label in (payload.get("template") or {}).items():
                    templates[str(key)] = {
                        "key": str(key),
                        "label": str(label),
                        "source": "rest-types",
                    }
            except httpx.HTTPError:
                pass
        default_key = normalize_template_key(self.default_template) or "elementor_header_footer"
        result = list(templates.values())
        for item in result:
            item["default"] = item.get("key") == default_key
        return result

    async def resolve_or_create_tags(self, tag_names: list[str]) -> dict[str, Any]:
        clean_names = _clean_tag_names(tag_names, self.max_tags)
        result: dict[str, Any] = {"requested": clean_names, "tags": [], "warnings": []}
        if not clean_names:
            return result

        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=30,
        ) as client:
            for name in clean_names:
                resolved = await self._find_tag(client, name)
                created = False
                if not resolved and self.auto_create_tags:
                    resolved = await self._create_tag(client, name)
                    created = bool(resolved)
                if resolved:
                    result["tags"].append({**resolved, "created": created})
                else:
                    result["warnings"].append(f"Tag could not be resolved and auto-create is disabled: {name}")
        return result

    async def upload_featured_image_from_url(self, image_url: str, alt_text: str = "") -> dict[str, Any]:
        if not self.upload_featured_image:
            return {
                "uploaded": False,
                "id": None,
                "url": image_url,
                "warning": "WORDPRESS_UPLOAD_FEATURED_IMAGE=false; image URL was not uploaded.",
            }
        if not image_url.strip():
            return {"uploaded": False, "id": None, "warning": "No featured image URL provided."}

        filename = _filename_from_url(image_url)
        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=60,
        ) as client:
            image_response = await client.get(image_url)
            image_response.raise_for_status()
            media_response = await client.post(
                f"{self.base_url}/wp-json/wp/v2/media",
                content=image_response.content,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": image_response.headers.get("content-type", "image/jpeg"),
                },
            )
            media_response.raise_for_status()
            media = media_response.json()
            media_id = media.get("id")
            if media_id and alt_text.strip():
                await client.post(
                    f"{self.base_url}/wp-json/wp/v2/media/{media_id}",
                    json={"alt_text": alt_text.strip()},
                )
        return {
            "uploaded": bool(media_id),
            "id": media_id,
            "url": media.get("source_url") or image_url,
            "alt_text": alt_text,
        }

    async def upload_featured_image_from_path(self, image_path: str, alt_text: str = "") -> dict[str, Any]:
        if not self.upload_featured_image:
            return {
                "uploaded": False,
                "id": None,
                "path": image_path,
                "warning": "WORDPRESS_UPLOAD_FEATURED_IMAGE=false; local image was not uploaded.",
            }
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            return {"uploaded": False, "id": None, "path": image_path, "warning": "Local image file was not found."}
        content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        async with httpx.AsyncClient(
            auth=(self.username, self.app_password),
            timeout=60,
        ) as client:
            media_response = await client.post(
                f"{self.base_url}/wp-json/wp/v2/media",
                content=path.read_bytes(),
                headers={
                    "Content-Disposition": f'attachment; filename="{path.name}"',
                    "Content-Type": content_type,
                },
            )
            media_response.raise_for_status()
            media = media_response.json()
            media_id = media.get("id")
            if media_id and alt_text.strip():
                await client.post(
                    f"{self.base_url}/wp-json/wp/v2/media/{media_id}",
                    json={"alt_text": alt_text.strip()},
                )
        return {
            "uploaded": bool(media_id),
            "id": media_id,
            "url": media.get("source_url"),
            "path": image_path,
            "alt_text": alt_text,
        }

    async def _apply_template(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        template: str,
    ) -> dict[str, Any]:
        attempts = [
            {"template": template, "meta": {"_wp_page_template": template}},
            {"template": template},
            {"meta": {"_wp_page_template": template}},
        ]
        warnings = []
        for payload in attempts:
            try:
                response = await client.post(f"{self.base_url}/wp-json/wp/v2/posts/{post_id}", json=payload)
                response.raise_for_status()
                method = "template_and_meta" if "template" in payload and "meta" in payload else "template" if "template" in payload else "meta._wp_page_template"
                response_result = _template_result_from_payload(response.json(), template, method=method, warnings=warnings)
                if response_result.get("applied"):
                    return response_result
                verified = await self._verify_template(client, post_id, template, method=method, warnings=warnings)
                if verified.get("applied"):
                    return verified
                warnings.extend(verified.get("warnings", []))
            except httpx.HTTPError as exc:
                warnings.append(str(exc))
        if self.fail_on_template_error:
            raise ValueError(f"WordPress template could not be applied: {template}")
        return {"template": template, "applied": False, "warnings": warnings}

    async def _verify_template(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        template: str,
        *,
        method: str,
        warnings: list[str],
    ) -> dict[str, Any]:
        try:
            response = await client.get(f"{self.base_url}/wp-json/wp/v2/posts/{post_id}", params={"context": "edit"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "template": template,
                "applied": False,
                "method": method,
                "warnings": [*warnings, f"Template verification failed: {exc}"],
            }
        return _template_result_from_payload(response.json(), template, method=f"{method}+verify", warnings=warnings)

    async def _apply_elementor_builder_metadata(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        *,
        html_content: str,
        template: str,
    ) -> dict[str, Any]:
        meta = _elementor_builder_meta(html_content=html_content, template=template)
        warnings: list[str] = []
        attempts = [
            {"meta": meta},
            {"meta": {key: value for key, value in meta.items() if key != "_elementor_data"}},
        ]
        for payload in attempts:
            try:
                response = await client.post(f"{self.base_url}/wp-json/wp/v2/posts/{post_id}", json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                warnings.append(str(exc))
                continue

            result = _elementor_result_from_payload(response.json(), warnings=warnings)
            if result.get("applied"):
                return result

            verified = await self._verify_elementor_builder_metadata(client, post_id, warnings=warnings)
            if verified.get("applied"):
                return verified
            warnings.extend(verified.get("warnings", []))

        if self.fail_on_template_error:
            raise ValueError("WordPress Elementor builder metadata could not be applied.")
        return {
            "requested": True,
            "applied": False,
            "method": "meta",
            "warnings": [
                *warnings,
                "Elementor builder metadata was not confirmed. WordPress may require protected Elementor meta to be registered for REST updates.",
            ],
        }

    async def _verify_elementor_builder_metadata(
        self,
        client: httpx.AsyncClient,
        post_id: int,
        *,
        warnings: list[str],
    ) -> dict[str, Any]:
        try:
            response = await client.get(f"{self.base_url}/wp-json/wp/v2/posts/{post_id}", params={"context": "edit"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "requested": True,
                "applied": False,
                "method": "meta+verify",
                "warnings": [*warnings, f"Elementor metadata verification failed: {exc}"],
            }
        return _elementor_result_from_payload(response.json(), warnings=warnings, method="meta+verify")

    async def _find_tag(self, client: httpx.AsyncClient, name: str) -> dict[str, Any] | None:
        response = await client.get(f"{self.base_url}/wp-json/wp/v2/tags", params={"search": name, "per_page": 20})
        response.raise_for_status()
        normalized_name = name.strip().lower()
        for tag in response.json():
            if str(tag.get("name") or "").strip().lower() == normalized_name:
                return {"id": tag.get("id"), "name": tag.get("name"), "slug": tag.get("slug")}
        return None

    async def _create_tag(self, client: httpx.AsyncClient, name: str) -> dict[str, Any] | None:
        try:
            response = await client.post(f"{self.base_url}/wp-json/wp/v2/tags", json={"name": name})
            response.raise_for_status()
            tag = response.json()
            return {"id": tag.get("id"), "name": tag.get("name"), "slug": tag.get("slug")}
        except httpx.HTTPStatusError as exc:
            payload = exc.response.json() if exc.response.content else {}
            term_id = payload.get("data", {}).get("term_id")
            if term_id:
                return {"id": term_id, "name": name, "slug": ""}
            raise


def _clean_tag_names(tag_names: list[str], max_tags: int) -> list[str]:
    seen: set[str] = set()
    cleaned = []
    for name in tag_names:
        value = " ".join(str(name).replace("#", "").split()).strip(" ,;")
        if not value or len(value) > 60:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
        if len(cleaned) >= max_tags:
            break
    return cleaned


def _filename_from_url(image_url: str) -> str:
    parsed = urlparse(image_url)
    filename = PurePosixPath(parsed.path).name or "featured-image.jpg"
    if "." not in filename:
        return f"{filename}.jpg"
    return filename


def normalize_template_key(template: str) -> str:
    aliases = {
        "elementor_full_width": "elementor_header_footer",
        "elementor full width": "elementor_header_footer",
    }
    value = str(template or "").strip()
    return aliases.get(value.lower(), value)


def _template_result_from_payload(
    payload: dict[str, Any],
    template: str,
    *,
    method: str,
    warnings: list[str],
) -> dict[str, Any]:
    response_template = normalize_template_key(str(payload.get("template") or ""))
    response_meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    response_page_template = normalize_template_key(str(response_meta.get("_wp_page_template") or ""))
    applied = template in {response_template, response_page_template}
    result_warnings = list(warnings)
    if not applied:
        result_warnings.append(
            "WordPress did not echo the requested template in the post response. "
            "The post may not receive the Elementor layout unless the site exposes template/meta assignment through REST."
        )
    return {
        "template": template,
        "applied": applied,
        "method": method,
        "response_template": response_template,
        "response_page_template": response_page_template,
        "warnings": result_warnings,
    }


def _is_elementor_template(template: str) -> bool:
    return normalize_template_key(template) in ELEMENTOR_TEMPLATE_KEYS


def _elementor_builder_meta(html_content: str, template: str) -> dict[str, str]:
    return {
        "_elementor_edit_mode": "builder",
        "_elementor_template_type": "wp-post",
        "_elementor_version": "3.0.0",
        "_elementor_data": _elementor_data(html_content),
        "_wp_page_template": normalize_template_key(template),
    }


def _elementor_data(html_content: str) -> str:
    seed = hashlib.md5(html_content.encode("utf-8")).hexdigest()
    section_id = seed[:7]
    column_id = seed[7:14]
    widget_id = seed[14:21]
    data = [
        {
            "id": section_id,
            "elType": "section",
            "settings": {},
            "elements": [
                {
                    "id": column_id,
                    "elType": "column",
                    "settings": {"_column_size": 100},
                    "elements": [
                        {
                            "id": widget_id,
                            "elType": "widget",
                            "widgetType": "html",
                            "settings": {"html": html_content},
                        }
                    ],
                    "isInner": False,
                }
            ],
            "isInner": False,
        }
    ]
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _elementor_result_from_payload(
    payload: dict[str, Any],
    *,
    warnings: list[str],
    method: str = "meta",
) -> dict[str, Any]:
    response_meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    edit_mode = str(response_meta.get("_elementor_edit_mode") or "")
    template_type = str(response_meta.get("_elementor_template_type") or "")
    has_data = bool(response_meta.get("_elementor_data"))
    applied = edit_mode == "builder" and template_type == "wp-post"
    result_warnings = list(warnings)
    if not applied:
        result_warnings.append(
            "WordPress did not echo Elementor builder metadata. The REST API may be blocking protected Elementor meta."
        )
    return {
        "requested": True,
        "applied": applied,
        "method": method,
        "edit_mode": edit_mode,
        "template_type": template_type,
        "has_elementor_data": has_data,
        "warnings": result_warnings,
    }
