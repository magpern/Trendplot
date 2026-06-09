from __future__ import annotations

import json
from typing import Any

import httpx

from app.connectors.hmac_signing import PHASE1_CONNECTOR_BASE_PATH, connector_auth_headers


class Phase1ConnectorError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.payload = payload


class TrendplotPhase1ConnectorClient:
    """HTTP client for Trendplot Connector plugin Phase 1 write endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        site_id: str,
        shared_secret: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not base_url.strip():
            raise ValueError("wordpress_base_url is required.")
        if not site_id.strip():
            raise ValueError("trendplot_site_id is required.")
        if not shared_secret.strip():
            raise ValueError("trendplot_shared_secret is required.")
        self.base_url = base_url.rstrip("/")
        self.site_id = site_id.strip()
        self.shared_secret = shared_secret
        self.timeout = max(5.0, timeout_seconds)

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def site_info(self) -> dict[str, Any]:
        return await self._request("GET", "/site-info")

    async def list_categories(self) -> dict[str, Any]:
        return await self._request("GET", "/categories")

    async def list_tags(self, *, search: str = "") -> dict[str, Any]:
        path = "/tags"
        if search.strip():
            return await self._request_with_query("GET", path, query=f"?search={search.strip()}")
        return await self._request("GET", path)

    async def create_draft(self, body_json: str) -> dict[str, Any]:
        return await self._request("POST", "/drafts", body=body_json)

    async def update_draft(self, post_id: str | int, body_json: str) -> dict[str, Any]:
        normalized_id = str(post_id).strip()
        if not normalized_id:
            raise ValueError("wordpress_post_id is required for draft update.")
        return await self._request("PATCH", f"/drafts/{normalized_id}", body=body_json)

    async def get_wordpress_draft(self, post_id: str | int) -> dict[str, Any]:
        normalized_id = str(post_id).strip()
        if not normalized_id:
            raise ValueError("wordpress_post_id is required for draft status lookup.")
        return await self._request("GET", f"/drafts/{normalized_id}")

    async def get_post_seo(self, post_id: str | int) -> dict[str, Any]:
        normalized_id = str(post_id).strip()
        if not normalized_id:
            raise ValueError("wordpress_post_id is required for SEO lookup.")
        return await self._request("GET", f"/posts/{normalized_id}/seo")

    async def update_post_seo(self, post_id: str | int, body_json: str) -> dict[str, Any]:
        normalized_id = str(post_id).strip()
        if not normalized_id:
            raise ValueError("wordpress_post_id is required for SEO update.")
        if not body_json.strip():
            raise ValueError("SEO payload is required.")
        return await self._request("PATCH", f"/posts/{normalized_id}/seo", body=body_json)

    async def _request_with_query(self, method: str, path: str, query: str) -> dict[str, Any]:
        connector_path = f"{PHASE1_CONNECTOR_BASE_PATH}{path}{query}"
        url = f"{self.base_url}{connector_path}"
        headers = connector_auth_headers(
            method=method,
            path=connector_path.split("?")[0] if "?" in connector_path else connector_path,
            body="",
            site_id=self.site_id,
            shared_secret=self.shared_secret,
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, headers=headers)
        return self._parse_response(response)

    async def _request(self, method: str, path: str, *, body: str = "") -> dict[str, Any]:
        connector_path = f"{PHASE1_CONNECTOR_BASE_PATH}{path}"
        url = f"{self.base_url}{connector_path}"
        headers = connector_auth_headers(
            method=method,
            path=connector_path,
            body=body,
            site_id=self.site_id,
            shared_secret=self.shared_secret,
        )
        if method in {"POST", "PATCH"}:
            headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, content=body.encode("utf-8") if body else None, headers=headers)
        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        payload: Any = None
        if response.content:
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = {"raw": response.text}
        if response.status_code >= 400:
            message = "Connector request failed."
            code = None
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("error") or message)
                code = str(payload.get("code") or "") or None
            raise Phase1ConnectorError(
                message,
                status_code=response.status_code,
                code=code,
                payload=payload,
            )
        if not isinstance(payload, dict):
            return {"data": payload}
        return payload
