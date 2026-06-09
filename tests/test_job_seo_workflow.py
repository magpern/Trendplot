from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.connectors.phase1_client import Phase1ConnectorError, TrendplotPhase1ConnectorClient
from app.providers.base import GeneratedContent
from app.wordpress_connector.seo import (
    extract_rank_math_score,
    normalize_connector_seo_payload,
    normalize_seo_package_payload,
    robots_for_connector,
    robots_from_connector,
    seo_fields_for_connector,
    seo_package_response,
    validate_seo_fields,
)
from app.wordpress_connector.service import WordPressConnectorService


def _service_with_mocks(
    *,
    job: dict[str, Any] | None = None,
    connector_row: dict[str, Any] | None = None,
) -> tuple[WordPressConnectorService, MagicMock, MagicMock]:
    repositories = MagicMock()
    repositories.autopilot_workspaces.get = AsyncMock(return_value={"id": "ws-1"})
    repositories.workspace_wordpress_connector.get = AsyncMock(return_value=connector_row)
    repositories.workspace_wordpress_connector.upsert = AsyncMock(
        side_effect=lambda _ws, fields: {**(connector_row or {}), **fields, "workspace_id": "ws-1"}
    )
    repositories.jobs.get_job = AsyncMock(return_value=job)
    repositories.jobs.mark_status = AsyncMock()
    repositories.jobs.update_wordpress_publish_state = AsyncMock(
        side_effect=lambda job_id, **fields: {**(job or {}), **fields, "id": job_id}
    )
    repositories.jobs.update_job_seo = AsyncMock(
        side_effect=lambda job_id, **fields: {**(job or {}), **fields, "id": job_id}
    )
    repositories.workspace_content_inventory.list_for_workspace = AsyncMock(return_value=[])
    repositories.artifacts.create_artifact = AsyncMock()
    job_service = MagicMock()
    job_service._resolve_publishable_html = AsyncMock(return_value="<p>Article body about TB-500 and BPC-157.</p>")  # noqa: SLF001
    job_service._latest_artifact_json = AsyncMock(  # noqa: SLF001
        return_value={
            "title": "TB-500 vs BPC-157",
            "focus_keyword": "TB-500 vs BPC-157",
        }
    )
    job_service._latest_artifact_text = AsyncMock(return_value=None)  # noqa: SLF001
    job_service.run_seo_optimization = AsyncMock(
        return_value={
            "job_id": "job-1",
            "status": "optimized",
            "optimization_report": {"changes": []},
        }
    )
    job_service.registry.content_generation.generate_seo_metadata = AsyncMock(
        return_value=GeneratedContent(
            content_json={
                "seo_title": "TB-500 vs BPC-157: Research Comparison",
                "seo_description": "Compare TB-500 and BPC-157 research context, differences, and why they appear together in peptide discussions.",
                "seo_focus_keyword": "TB-500 vs BPC-157, BPC-157",
                "seo_canonical_url": "https://staging.example.com/tb-500-vs-bpc-157/",
                "seo_robots": "index, follow",
                "seo_schema_type": "Article",
            },
            provider="openai",
            model="gpt-test",
        )
    )
    service = WordPressConnectorService(MagicMock(), repositories, job_service=job_service)
    return service, repositories, job_service


def test_normalize_seo_package_payload_maps_connector_shape() -> None:
    payload = normalize_seo_package_payload(
        {
            "title": "Title",
            "description": "Description",
            "focus_keyword": "keyword one",
            "canonical_url": "",
            "robots": [],
            "schema_type": "Article",
        }
    )
    assert payload["seo_title"] == "Title"
    assert payload["seo_description"] == "Description"
    assert payload["seo_focus_keyword"] == "keyword one"
    assert payload["seo_schema_type"] == "Article"
    assert "seo_canonical_url" not in payload


def test_seo_package_response_shape() -> None:
    package = seo_package_response(
        {
            "title": "Title",
            "description": "Description",
            "focus_keyword": "keyword",
            "robots": [],
            "schema_type": "Article",
        }
    )
    assert package["robots"] == []
    assert package["canonical_url"] == ""


def test_validate_seo_fields_rejects_long_description() -> None:
    errors = validate_seo_fields(
        {
            "seo_title": "Short title",
            "seo_description": "x" * 171,
            "seo_focus_keyword": "keyword",
        }
    )
    assert any("170" in error for error in errors)


def test_robots_roundtrip_for_rank_math() -> None:
    assert robots_for_connector("index, follow") == []
    assert robots_for_connector("noindex, nofollow") == ["noindex", "nofollow"]
    assert robots_from_connector([]) == "index, follow"
    assert robots_from_connector(["noindex"]) == "noindex"


def test_seo_fields_for_connector_shape() -> None:
    payload = seo_fields_for_connector(
        {
            "seo_title": "Title",
            "seo_description": "Description",
            "seo_focus_keyword": "keyword",
            "seo_canonical_url": "https://example.com/post/",
            "seo_robots": "index, follow",
            "seo_schema_type": "Article",
        }
    )
    assert payload["title"] == "Title"
    assert payload["robots"] == []
    assert payload["schema_type"] == "Article"


def test_generate_job_seo_stores_fields_without_sync() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4621",
        "request_input": {"target_keyword": "TB-500 vs BPC-157"},
    }
    service, repositories, job_service = _service_with_mocks(
        job=job,
        connector_row={
            "workspace_id": "ws-1",
            "connector_enabled": True,
            "wordpress_base_url": "https://example.com",
            "trendplot_site_id": "site-1",
            "trendplot_shared_secret": "secret",
        },
    )

    result = asyncio.run(service.generate_seo_package("job-1"))
    assert result["status"] == "generated"
    assert result["package"]["title"].startswith("TB-500")
    assert result["seo_title"].startswith("TB-500")
    repositories.jobs.update_job_seo.assert_awaited()
    update_call = repositories.jobs.update_job_seo.await_args
    assert update_call.kwargs.get("seo_generated_at")
    assert update_call.kwargs.get("seo_focus_keyword") == "TB-500 vs BPC-157, BPC-157"
    assert "seo_synced_at" not in update_call.kwargs
    job_service.registry.content_generation.generate_seo_metadata.assert_awaited()


def test_sync_job_seo_to_wordpress_success() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "published_draft",
        "wordpress_post_id": "4621",
        "wordpress_status": "publish",
        "seo_title": "TB-500 vs BPC-157",
        "seo_description": "Research comparison article.",
        "seo_focus_keyword": "TB-500 vs BPC-157",
        "seo_canonical_url": "https://example.com/tb-500-vs-bpc-157/",
        "seo_robots": "index, follow",
        "seo_schema_type": "Article",
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
    client.update_post_seo = AsyncMock(
        return_value={
            "seo": {
                "title": "TB-500 vs BPC-157",
                "description": "Research comparison article.",
                "focus_keyword": "TB-500 vs BPC-157",
                "canonical_url": "https://example.com/tb-500-vs-bpc-157/",
                "robots": "index, follow",
                "schema_type": "Article",
            }
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.sync_job_seo_to_wordpress("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "synced"
    assert result["seo_synced_at"]
    client.update_post_seo.assert_awaited_once()
    body_json = client.update_post_seo.await_args.args[1]
    assert json.loads(body_json)["seo"]["focus_keyword"] == "TB-500 vs BPC-157"
    repositories.jobs.update_wordpress_publish_state.assert_awaited()


def test_sync_job_seo_published_post_allowed() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "wordpress_post_id": "4621",
        "wordpress_status": "publish",
        "seo_title": "Title",
        "seo_description": "Description",
        "seo_focus_keyword": "keyword",
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
    client.update_post_seo = AsyncMock(return_value={"seo": {"title": "Title", "description": "Description", "focus_keyword": "keyword"}})

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.sync_job_seo_to_wordpress("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "synced"


def test_sync_job_seo_missing_wordpress_post() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "seo_title": "Title", "request_input": {}}
    service, _, _ = _service_with_mocks(job=job, connector_row=None)

    with pytest.raises(ValueError, match="No WordPress post is linked"):
        asyncio.run(service.sync_job_seo_to_wordpress("job-1"))


def test_sync_job_seo_validation_error() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "wordpress_post_id": "4621",
        "seo_title": "Title",
        "seo_description": "Description",
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

    with pytest.raises(ValueError, match="Focus keyword is required"):
        asyncio.run(service.sync_job_seo_to_wordpress("job-1"))


def test_sync_job_seo_auth_failed_returns_structured() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "wordpress_post_id": "4621",
        "seo_title": "Title",
        "seo_description": "Description",
        "seo_focus_keyword": "keyword",
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
    client.update_post_seo = AsyncMock(
        side_effect=Phase1ConnectorError("HMAC signature verification failed.", status_code=401, code="unauthorized")
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.sync_job_seo_to_wordpress("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "failed"
    assert result["error_code"] == "auth_failed"
    assert result["seo_last_error"]


def test_sync_job_seo_clears_last_error_on_success() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "wordpress_post_id": "4621",
        "seo_title": "Title",
        "seo_description": "Description",
        "seo_focus_keyword": "keyword",
        "seo_last_error": "auth_failed: old",
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
    client.update_post_seo = AsyncMock(return_value={"seo": {"title": "Title", "description": "Description", "focus_keyword": "keyword"}})

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.sync_job_seo_to_wordpress("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "synced"
    update_call = repositories.jobs.update_job_seo.await_args_list[-1]
    assert update_call.kwargs.get("seo_last_error") is None


def test_refresh_job_seo_invalid_plugin_response() -> None:
    job = {"id": "job-1", "workspace_id": "ws-1", "wordpress_post_id": "4621", "request_input": {}}
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
    client.get_post_seo = AsyncMock(return_value={"unexpected": True})

    async def _run() -> None:
        with patch.object(service, "_client", return_value=client):
            await service.refresh_job_seo_from_wordpress("job-1")

    with pytest.raises(ValueError, match="no SEO fields"):
        asyncio.run(_run())


def test_extract_rank_math_score_optional() -> None:
    assert extract_rank_math_score({"rank_math_score": 82}) == 82.0
    assert extract_rank_math_score({"seo": {"score": 71}}) == 71.0
    assert extract_rank_math_score({"seo": {"title": "x"}}) is None


def test_refresh_job_seo_from_wordpress_roundtrip() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "wordpress_post_id": "4621",
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
    client.get_post_seo = AsyncMock(
        return_value={
            "seo": {
                "title": "Refreshed title",
                "description": "Refreshed description",
                "focus_keyword": "refreshed keyword",
                "canonical_url": "https://example.com/refreshed/",
                "robots": "index, follow",
                "schema_type": "Article",
            }
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            return await service.refresh_job_seo_from_wordpress("job-1")

    result = asyncio.run(_run())
    assert result["status"] == "refreshed"
    repositories.jobs.update_job_seo.assert_awaited()
    update_call = repositories.jobs.update_job_seo.await_args
    assert update_call.kwargs.get("seo_title") == "Refreshed title"
    assert update_call.kwargs.get("seo_focus_keyword") == "refreshed keyword"


def test_phase1_client_exposes_post_seo_methods() -> None:
    client = TrendplotPhase1ConnectorClient(
        base_url="https://example.com",
        site_id="site-1",
        shared_secret="secret",
    )
    assert hasattr(client, "get_post_seo")
    assert hasattr(client, "update_post_seo")


def test_analyze_ui_seo_section_markers() -> None:
    assert "renderJobSeoSection" in ANALYZE_WEBSITE_HTML
    assert "Generate SEO" in ANALYZE_WEBSITE_HTML
    assert "Save SEO" in ANALYZE_WEBSITE_HTML
    assert "Sync SEO to WordPress" in ANALYZE_WEBSITE_HTML
    assert "Run SEO Optimization" in ANALYZE_WEBSITE_HTML
    assert "Update WordPress draft" in ANALYZE_WEBSITE_HTML
    assert "Recommended slug" in ANALYZE_WEBSITE_HTML
    assert "not the post permalink" in ANALYZE_WEBSITE_HTML
    assert "Published in WordPress:" in ANALYZE_WEBSITE_HTML
    assert "Refresh SEO from WordPress" in ANALYZE_WEBSITE_HTML
    assert "data-generate-seo" in ANALYZE_WEBSITE_HTML
    assert "data-sync-seo" in ANALYZE_WEBSITE_HTML
    assert "/seo/generate" in ANALYZE_WEBSITE_HTML
    assert "/seo/sync" in ANALYZE_WEBSITE_HTML
    assert "/seo/refresh" in ANALYZE_WEBSITE_HTML
    assert "rank_math_score" in ANALYZE_WEBSITE_HTML
    assert "seo_last_error" in ANALYZE_WEBSITE_HTML
