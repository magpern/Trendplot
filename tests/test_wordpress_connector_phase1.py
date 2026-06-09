from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.connectors.hmac_signing import build_signature_string, connector_auth_headers, sign_request
from app.connectors.phase1_client import Phase1ConnectorError, TrendplotPhase1ConnectorClient
from app.wordpress_connector.service import WordPressConnectorService


def test_hmac_signing_get() -> None:
    secret = "test-secret"
    path = "/wp-json/trendplot/v1/health"
    ts, signature = sign_request(method="GET", path=path, body="", shared_secret=secret, timestamp="1710000000")
    expected = build_signature_string(method="GET", path=path, timestamp="1710000000", body="")
    assert ts == "1710000000"
    assert len(signature) == 64
    headers = connector_auth_headers(
        method="GET",
        path=path,
        body="",
        site_id="site-1",
        shared_secret=secret,
        timestamp="1710000000",
    )
    assert headers["X-Trendplot-Site-Id"] == "site-1"
    assert headers["X-Trendplot-Timestamp"] == "1710000000"
    assert headers["X-Trendplot-Signature"] == signature
    assert expected.endswith("\n")


def test_phase1_client_exposes_update_draft() -> None:
    client = TrendplotPhase1ConnectorClient(
        base_url="https://example.com",
        site_id="site-1",
        shared_secret="secret",
    )
    assert hasattr(client, "create_draft")
    assert hasattr(client, "update_draft")
    assert hasattr(client, "get_wordpress_draft")


def test_hmac_signing_get_draft_status() -> None:
    path = "/wp-json/trendplot/v1/drafts/4608"
    ts, signature = sign_request(method="GET", path=path, body="", shared_secret="secret", timestamp="1710000003")
    assert build_signature_string(method="GET", path=path, timestamp="1710000003", body="") == f"GET\n{path}\n1710000003\n"
    headers = connector_auth_headers(
        method="GET",
        path=path,
        body="",
        site_id="site-1",
        shared_secret="secret",
        timestamp="1710000003",
    )
    assert headers["X-Trendplot-Signature"] == signature
    assert ts == "1710000003"


def test_hmac_signing_patch_exact_body() -> None:
    body = '{"title":"Updated","content":"<p>Hi</p>","trendplot_article_id":"job-1"}'
    path = "/wp-json/trendplot/v1/drafts/4608"
    ts, signature = sign_request(method="PATCH", path=path, body=body, shared_secret="secret", timestamp="1710000002")
    assert build_signature_string(method="PATCH", path=path, timestamp="1710000002", body=body).count("\n") == 3
    headers = connector_auth_headers(
        method="PATCH",
        path=path,
        body=body,
        site_id="site-1",
        shared_secret="secret",
        timestamp="1710000002",
    )
    assert headers["X-Trendplot-Signature"] == signature
    assert ts == "1710000002"


def test_hmac_signing_post_exact_body() -> None:
    body = '{"title":"Test","content":"<p>Hi</p>","trendplot_article_id":"job-1"}'
    path = "/wp-json/trendplot/v1/drafts"
    ts, signature = sign_request(method="POST", path=path, body=body, shared_secret="secret", timestamp="1710000001")
    assert build_signature_string(method="POST", path=path, timestamp="1710000001", body=body).count("\n") == 3
    assert signature


def test_phase1_client_invalid_config() -> None:
    with pytest.raises(ValueError, match="wordpress_base_url"):
        TrendplotPhase1ConnectorClient(base_url="", site_id="s", shared_secret="x")
    with pytest.raises(ValueError, match="trendplot_site_id"):
        TrendplotPhase1ConnectorClient(base_url="https://example.com", site_id="", shared_secret="x")


def _service_with_mocks(*, job: dict[str, Any] | None = None, connector_row: dict[str, Any] | None = None) -> tuple[WordPressConnectorService, MagicMock, MagicMock]:
    repositories = MagicMock()
    repositories.autopilot_workspaces.get = AsyncMock(return_value={"id": "ws-1"})
    repositories.workspace_wordpress_connector.get = AsyncMock(return_value=connector_row)
    repositories.workspace_wordpress_connector.upsert = AsyncMock(side_effect=lambda _ws, fields: {**(connector_row or {}), **fields, "workspace_id": "ws-1"})
    repositories.jobs.get_job = AsyncMock(return_value=job)
    repositories.jobs.mark_status = AsyncMock()
    repositories.jobs.update_wordpress_publish_state = AsyncMock(side_effect=lambda job_id, **fields: {**(job or {}), **fields, "id": job_id})
    repositories.workspace_content_inventory.list_for_workspace = AsyncMock(return_value=[])
    repositories.artifacts.create_artifact = AsyncMock()
    job_service = MagicMock()
    job_service._resolve_publishable_html = AsyncMock(return_value="<p>Publishable</p>")  # noqa: SLF001
    job_service._latest_artifact_json = AsyncMock(return_value={"title": "Test Article", "excerpt": "Excerpt"})  # noqa: SLF001
    job_service.run_seo_optimization = AsyncMock(return_value={"job_id": (job or {}).get("id", "job-1"), "status": "optimized"})
    service = WordPressConnectorService(MagicMock(), repositories, job_service=job_service)
    return service, repositories, job_service


def test_connection_test_success() -> None:
    service, repositories, _ = _service_with_mocks(
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        }
    )
    client = MagicMock()
    client.health = AsyncMock(return_value={"plugin_version": "1.0.0", "api_version": "v1"})
    client.site_info = AsyncMock(return_value={"plugin_version": "1.0.0"})

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.test_wordpress_connector("ws-1")

    result = asyncio.run(_run())
    assert result["status"] == "connected"
    assert result["plugin_version"] == "1.0.0"
    repositories.workspace_wordpress_connector.upsert.assert_awaited()


def test_connection_test_failure() -> None:
    service, repositories, _ = _service_with_mocks(
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        }
    )
    client = MagicMock()
    client.health = AsyncMock(side_effect=RuntimeError("unreachable"))

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.test_wordpress_connector("ws-1")

    result = asyncio.run(_run())
    assert result["status"] == "failed"
    assert "unreachable" in result["error"]
    repositories.workspace_wordpress_connector.upsert.assert_awaited()


def test_create_draft_success() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "completed",
        "request_input": {"opportunity_context": {"related_products": ["BPC-157"], "source": "manual_recommendation"}},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.create_draft = AsyncMock(return_value={"id": 200, "edit_url": "https://example.com/wp-admin/post.php?post=200&action=edit", "url": "https://example.com/?p=200", "status": "draft"})

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.create_wordpress_draft("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "created"
    assert result["wordpress_post_id"] == 200
    sent_body = client.create_draft.await_args.args[0]
    payload = json.loads(sent_body)
    assert payload["trendplot_article_id"] == "job-1"
    assert payload["content"] == "<p>Publishable</p>"
    repositories.jobs.update_wordpress_publish_state.assert_awaited()
    repositories.jobs.mark_status.assert_awaited_with("job-1", "published_draft")


def test_create_draft_failure_marks_failed_publish_when_no_post() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.create_draft = AsyncMock(
        side_effect=Phase1ConnectorError("HMAC signature verification failed.", status_code=401)
    )

    async def _run() -> None:
        with patch.object(service, "_client", return_value=client):
            await service.create_wordpress_draft("job-1")

    with pytest.raises(ValueError, match="WordPress draft creation failed"):
        asyncio.run(_run())
    repositories.jobs.mark_status.assert_awaited_with("job-1", "failed_publish", "HMAC signature verification failed.")


def test_existing_draft_short_circuits_without_force() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": 4608,
        "wordpress_edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.create_draft = AsyncMock()

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.create_wordpress_draft("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "existing"
    assert result["wordpress_post_id"] == 4608
    client.create_draft.assert_not_awaited()
    repositories.jobs.update_wordpress_publish_state.assert_not_awaited()


def test_force_resend_clears_wordpress_state_and_creates_draft() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": 4608,
        "wordpress_edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
        "request_input": {},
    }
    cleared_job = {**job, "wordpress_post_id": None, "wordpress_edit_url": None}
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    repositories.jobs.get_job = AsyncMock(side_effect=[job, cleared_job, cleared_job])
    client = MagicMock()
    client.create_draft = AsyncMock(
        return_value={
            "id": 4700,
            "edit_url": "https://example.com/wp-admin/post.php?post=4700&action=edit",
            "url": "https://example.com/?p=4700",
            "status": "draft",
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.create_wordpress_draft("job-1", force=True)

    result = asyncio.run(_run())
    assert result["status"] == "created"
    assert result["wordpress_post_id"] == 4700
    clear_call = repositories.jobs.update_wordpress_publish_state.await_args_list[0]
    assert clear_call.args[0] == "job-1"
    assert clear_call.kwargs.get("wordpress_post_id") is None
    client.create_draft.assert_awaited_once()


def test_update_draft_success() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "wordpress_status": "draft",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.update_draft = AsyncMock(
        return_value={
            "id": 4608,
            "edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
            "url": "https://example.com/?p=4608",
            "status": "draft",
            "modified_at": "2026-06-08T12:00:00+00:00",
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.update_wordpress_draft("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "updated"
    assert result["wordpress_post_id"] == 4608
    client.update_draft.assert_awaited_once()
    patch_args = client.update_draft.await_args
    assert patch_args.args[0] == "4608"
    payload = json.loads(patch_args.args[1])
    assert payload["trendplot_article_id"] == "job-1"
    sync_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert sync_call.kwargs.get("wordpress_draft_updated_at")
    assert sync_call.kwargs.get("last_wordpress_sync_at")
    assert sync_call.kwargs.get("wordpress_publish_error") is None


def test_update_draft_requires_wordpress_post_id() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, _, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )

    async def _run() -> None:
        await service.update_wordpress_draft("job-1")

    with pytest.raises(ValueError, match="No WordPress draft is linked"):
        asyncio.run(_run())


def test_update_draft_rejects_published_post() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "99",
        "wordpress_status": "publish",
        "request_input": {},
    }
    service, _, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )

    async def _run() -> None:
        await service.update_wordpress_draft("job-1")

    with pytest.raises(ValueError, match="published_post_rejected"):
        asyncio.run(_run())


def test_update_draft_failure_stores_error() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "wordpress_status": "draft",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.update_draft = AsyncMock(
        side_effect=Phase1ConnectorError("Post ID 4608 does not exist.", status_code=404, code="not_found")
    )

    async def _run() -> None:
        with patch.object(service, "_client", return_value=client):
            await service.update_wordpress_draft("job-1")

    with pytest.raises(ValueError, match="missing_draft"):
        asyncio.run(_run())
    error_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert "missing_draft" in str(error_call.kwargs.get("wordpress_publish_error"))


def test_duplicate_draft_409_existing_id_shape() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.create_draft = AsyncMock(
        side_effect=Phase1ConnectorError(
            "duplicate_article_id",
            status_code=409,
            payload={
                "code": "duplicate_article_id",
                "message": "A draft already exists",
                "existing_id": 4621,
            },
        )
    )
    client.get_wordpress_draft = AsyncMock(
        return_value={
            "id": 4621,
            "edit_url": "https://example.com/wp-admin/post.php?post=4621&action=edit",
            "url": "https://example.com/?p=4621",
            "status": "draft",
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.create_wordpress_draft("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "duplicate"
    assert result["wordpress_post_id"] == 4621
    assert "4621" in result["message"]
    client.get_wordpress_draft.assert_awaited_once_with("4621")


def test_duplicate_draft_409_handling() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.create_draft = AsyncMock(
        side_effect=Phase1ConnectorError(
            "duplicate",
            status_code=409,
            payload={"id": 150, "edit_url": "https://example.com/wp-admin/post.php?post=150&action=edit"},
        )
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.create_wordpress_draft("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "duplicate"
    assert result["wordpress_post_id"] == 150
    assert result["can_update"] is True
    repositories.jobs.update_wordpress_publish_state.assert_awaited()
    state_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert state_call.kwargs.get("wordpress_post_id") == "150"
    assert state_call.kwargs.get("wordpress_publish_error") is None


def test_missing_connector_config() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, _, _ = _service_with_mocks(job=job, connector_row=None)
    from app.config import Settings

    service.settings = Settings(
        WORDPRESS_CONNECTOR_ENABLED=False,
        WORDPRESS_CONNECTOR_BASE_URL="",
        WORDPRESS_CONNECTOR_SITE_ID="",
        WORDPRESS_CONNECTOR_SECRET="",
        WORDPRESS_CONNECTOR_STAGING_BASE_URL="",
        WORDPRESS_CONNECTOR_STAGING_SITE_ID="",
        WORDPRESS_CONNECTOR_STAGING_SECRET="",
        WORDPRESS_CONNECTOR_PRODUCTION_BASE_URL="",
        WORDPRESS_CONNECTOR_PRODUCTION_SITE_ID="",
        WORDPRESS_CONNECTOR_PRODUCTION_SECRET="",
    )

    async def _run() -> None:
        await service.create_wordpress_draft("job-1")

    with pytest.raises(ValueError, match="not configured"):
        asyncio.run(_run())


def test_missing_publishable_html() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, _, job_service = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    job_service._resolve_publishable_html = AsyncMock(return_value=None)  # noqa: SLF001

    async def _run() -> None:
        await service.create_wordpress_draft("job-1")

    with pytest.raises(ValueError, match="Publishable HTML"):
        asyncio.run(_run())


def test_shared_secret_not_returned_after_save() -> None:
    service, repositories, _ = _service_with_mocks(
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "super-secret",
        }
    )

    async def _run() -> dict[str, Any]:
        return await service.get_settings("ws-1")

    public = asyncio.run(_run())
    assert public["shared_secret_configured"] is True
    assert "super-secret" not in json.dumps(public)
    repositories.workspace_wordpress_connector.get.assert_awaited()


def test_environment_settings_round_trip() -> None:
    service, repositories, _ = _service_with_mocks(
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "active_environment": "staging",
            "environments_json": {
                "staging": {
                    "wordpress_base_url": "https://staging.example.com",
                    "trendplot_site_id": "staging-site",
                    "trendplot_shared_secret": "staging-secret",
                },
                "production": {
                    "wordpress_base_url": "https://prod.example.com",
                    "trendplot_site_id": "prod-site",
                    "trendplot_shared_secret": "prod-secret",
                },
            },
        }
    )

    async def _get() -> dict[str, Any]:
        return await service.get_settings("ws-1")

    public = asyncio.run(_get())
    assert public["active_environment"] == "staging"
    assert public["environments"]["staging"]["wordpress_base_url"] == "https://staging.example.com"
    assert public["environments"]["production"]["trendplot_site_id"] == "prod-site"
    assert "prod-secret" not in json.dumps(public)

    async def _switch() -> dict[str, Any]:
        return await service.save_settings("ws-1", active_environment="production")

    switched = asyncio.run(_switch())
    assert switched["active_environment"] == "production"
    assert switched["wordpress_base_url"] == "https://prod.example.com"
    repositories.workspace_wordpress_connector.upsert.assert_awaited()


def test_get_wordpress_draft_client_success() -> None:
    client = TrendplotPhase1ConnectorClient(
        base_url="https://example.com",
        site_id="site-1",
        shared_secret="secret",
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"id":4608,"status":"publish"}'
    mock_response.json.return_value = {
        "id": 4608,
        "status": "publish",
        "url": "https://example.com/?p=4608",
        "edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
        "modified_at": "2026-06-08T12:00:00+00:00",
        "trendplot_article_id": "job-1",
    }

    async def _run() -> dict[str, Any]:
        with patch("httpx.AsyncClient") as mock_client_cls:
            http = AsyncMock()
            http.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = http
            return await client.get_wordpress_draft(4608)

    result = asyncio.run(_run())
    assert result["status"] == "publish"
    assert result["id"] == 4608


def test_get_wordpress_draft_client_errors() -> None:
    client = TrendplotPhase1ConnectorClient(
        base_url="https://example.com",
        site_id="site-1",
        shared_secret="secret",
    )

    async def _request(status_code: int, payload: dict[str, Any]) -> None:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.content = json.dumps(payload).encode()
        mock_response.json.return_value = payload
        with patch("httpx.AsyncClient") as mock_client_cls:
            http = AsyncMock()
            http.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = http
            await client.get_wordpress_draft(999)

    with pytest.raises(Phase1ConnectorError) as exc:
        asyncio.run(_request(404, {"code": "not_found", "message": "Post ID 999 does not exist."}))
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"

    with pytest.raises(Phase1ConnectorError) as exc:
        asyncio.run(_request(403, {"code": "not_trendplot_draft", "message": "Not a Trendplot draft."}))
    assert exc.value.status_code == 403

    with pytest.raises(Phase1ConnectorError) as exc:
        asyncio.run(_request(401, {"code": "unauthorized", "message": "HMAC signature verification failed."}))
    assert exc.value.status_code == 401


def test_get_wordpress_draft_client_malformed_response() -> None:
    client = TrendplotPhase1ConnectorClient(
        base_url="https://example.com",
        site_id="site-1",
        shared_secret="secret",
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'"not-an-object"'
    mock_response.json.return_value = "not-an-object"

    async def _run() -> dict[str, Any]:
        with patch("httpx.AsyncClient") as mock_client_cls:
            http = AsyncMock()
            http.request = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = http
            return await client.get_wordpress_draft(4608)

    result = asyncio.run(_run())
    assert result == {"data": "not-an-object"}


def test_refresh_wordpress_status_stores_publish() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "wordpress_status": "draft",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.get_wordpress_draft = AsyncMock(
        return_value={
            "id": 4608,
            "status": "publish",
            "url": "https://example.com/?p=4608",
            "edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
            "modified_at": "2026-06-08T12:00:00+00:00",
            "trendplot_article_id": "job-1",
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.refresh_wordpress_status("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "refreshed"
    assert result["wordpress_status"] == "publish"
    state_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert state_call.kwargs.get("wordpress_status") == "publish"
    assert state_call.kwargs.get("wordpress_publish_error") is None


def test_refresh_wordpress_status_missing_post_clears_link() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "wordpress_status": "draft",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.get_wordpress_draft = AsyncMock(
        side_effect=Phase1ConnectorError("Post not found.", status_code=404, code="not_found")
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.refresh_wordpress_status("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "missing"
    state_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert state_call.kwargs.get("wordpress_post_id") is None
    assert "missing_draft" in str(state_call.kwargs.get("wordpress_publish_error"))


def test_refresh_wordpress_status_not_managed() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "wordpress_edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
        "wordpress_status": "draft",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.get_wordpress_draft = AsyncMock(
        side_effect=Phase1ConnectorError("Forbidden.", status_code=403, code="not_trendplot_draft")
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.refresh_wordpress_status("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "not_managed"
    assert result["wordpress_post_id"] == "4608"
    state_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert "wordpress_post_id" not in state_call.kwargs
    assert "not_trendplot_draft" in str(state_call.kwargs.get("wordpress_publish_error"))


def test_refresh_wordpress_status_requires_post_id() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "status": "completed", "request_input": {}}
    service, _, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )

    async def _run() -> None:
        await service.refresh_wordpress_status("job-1")

    with pytest.raises(ValueError, match="No WordPress post is linked"):
        asyncio.run(_run())


def test_refresh_wordpress_status_malformed_response() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "request_input": {},
    }
    service, _, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.get_wordpress_draft = AsyncMock(return_value={"id": 4608})

    async def _run() -> None:
        with patch.object(service, "_client", return_value=client):
            await service.refresh_wordpress_status("job-1")

    with pytest.raises(ValueError, match="Malformed connector response"):
        asyncio.run(_run())


def test_connector_config_uses_active_environment() -> None:
    service, _, _ = _service_with_mocks(
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "active_environment": "production",
            "environments_json": {
                "staging": {
                    "wordpress_base_url": "https://staging.example.com",
                    "trendplot_site_id": "staging-site",
                    "trendplot_shared_secret": "staging-secret",
                },
                "production": {
                    "wordpress_base_url": "https://prod.example.com",
                    "trendplot_site_id": "prod-site",
                    "trendplot_shared_secret": "prod-secret",
                },
            },
        }
    )

    async def _run() -> dict[str, Any]:
        return await service._connector_config("ws-1")

    config = asyncio.run(_run())
    assert config["wordpress_base_url"] == "https://prod.example.com"
    assert config["trendplot_site_id"] == "prod-site"


def test_connector_config_uses_workspace_secret_only() -> None:
    settings = MagicMock()
    settings.wordpress_connector_enabled = True
    settings.wordpress_connector_staging_secret = "env-secret"
    settings.wordpress_connector_secret = "legacy-env-secret"
    settings.wordpress_connector_active_environment = "staging"
    settings.wordpress_connector_timeout_seconds = 30.0
    repositories = MagicMock()
    repositories.workspace_wordpress_connector.get = AsyncMock(
        return_value={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "active_environment": "staging",
            "environments_json": {
                "staging": {
                    "wordpress_base_url": "https://example.com",
                    "trendplot_site_id": "site-1",
                    "trendplot_shared_secret": "workspace-secret",
                },
            },
        }
    )
    service = WordPressConnectorService(settings, repositories)

    async def _run() -> dict[str, Any]:
        return await service._connector_config("ws-1")

    config = asyncio.run(_run())
    assert config["trendplot_shared_secret"] == "workspace-secret"
    assert config["wordpress_base_url"] == "https://example.com"


def test_refresh_wordpress_status_auth_failed_returns_structured() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4608",
        "wordpress_status": "draft",
        "request_input": {},
    }
    service, repositories, _ = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )
    client = MagicMock()
    client.get_wordpress_draft = AsyncMock(
        side_effect=Phase1ConnectorError("HMAC signature verification failed.", status_code=401, code="unauthorized")
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.refresh_wordpress_status("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "failed"
    assert result["error_code"] == "auth_failed"
    state_call = repositories.jobs.update_wordpress_publish_state.await_args_list[-1]
    assert "auth_failed" in str(state_call.kwargs.get("wordpress_publish_error"))


def test_analyze_ui_wordpress_connector_section() -> None:
    assert "wp-connector-panel" in ANALYZE_WEBSITE_HTML
    assert "WordPress connector" in ANALYZE_WEBSITE_HTML
    assert "Upload target:" in ANALYZE_WEBSITE_HTML
    assert "wp-connector-active-env" in ANALYZE_WEBSITE_HTML
    assert "data-connector-test-env" in ANALYZE_WEBSITE_HTML
    assert "renderConnectorEnvironmentFields" in ANALYZE_WEBSITE_HTML
    assert "Send to WordPress as draft" in ANALYZE_WEBSITE_HTML
    assert "Create WordPress Draft" not in ANALYZE_WEBSITE_HTML
    assert "wp-connector-create-draft" not in ANALYZE_WEBSITE_HTML
    assert "Configure both servers below" in ANALYZE_WEBSITE_HTML
    assert "Select an article draft first" in ANALYZE_WEBSITE_HTML
    assert "Selected Trendplot article" in ANALYZE_WEBSITE_HTML
    assert "WordPress draft created" in ANALYZE_WEBSITE_HTML
    assert "Update WordPress draft" in ANALYZE_WEBSITE_HTML
    assert "data-update-wordpress" in ANALYZE_WEBSITE_HTML
    assert "updateArticleWordPressDraft" in ANALYZE_WEBSITE_HTML
    assert "wordpressDraftIsEditable" in ANALYZE_WEBSITE_HTML
    assert "wordpressPostIsPublished" in ANALYZE_WEBSITE_HTML
    assert "data-send-wordpress" in ANALYZE_WEBSITE_HTML
    assert "formatArticleJobStatus" in ANALYZE_WEBSITE_HTML
    assert "published_draft: \"WordPress draft created\"" in ANALYZE_WEBSITE_HTML
    assert "Open in WordPress" in ANALYZE_WEBSITE_HTML
    assert "Send to WordPress again" in ANALYZE_WEBSITE_HTML
    assert "Try WordPress send again" in ANALYZE_WEBSITE_HTML
    assert "refreshDraftWordPressControls" in ANALYZE_WEBSITE_HTML
    assert "data-resend-wordpress" in ANALYZE_WEBSITE_HTML
    assert "wordpress-connector/draft" in ANALYZE_WEBSITE_HTML
    assert "wordpress-connector/draft/update" in ANALYZE_WEBSITE_HTML
    assert "Refresh WordPress status" in ANALYZE_WEBSITE_HTML
    assert "data-refresh-wordpress-status" in ANALYZE_WEBSITE_HTML
    assert "refreshArticleWordPressStatus" in ANALYZE_WEBSITE_HTML
    assert "wordpressPostIsMissing" in ANALYZE_WEBSITE_HTML
    assert "wordpressPostNotManaged" in ANALYZE_WEBSITE_HTML
    assert "wordpress-connector/status/refresh" in ANALYZE_WEBSITE_HTML
    assert "maybeAutoRefreshWordPressStatus" in ANALYZE_WEBSITE_HTML
    assert 'result.status === "failed"' in ANALYZE_WEBSITE_HTML


def test_analyze_ui_send_button_disabled_without_job() -> None:
    assert 'data-send-wordpress disabled' in ANALYZE_WEBSITE_HTML
    assert "sendToWordPressDisabledReason" in ANALYZE_WEBSITE_HTML
    assert "Select an article draft first." in ANALYZE_WEBSITE_HTML


def test_analyze_ui_selected_article_title_helper() -> None:
    assert "articleJobTitle" in ANALYZE_WEBSITE_HTML
    assert "This will create a draft post in WordPress" in ANALYZE_WEBSITE_HTML
