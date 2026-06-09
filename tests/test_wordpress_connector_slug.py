from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.wordpress_connector.service import WordPressConnectorService
from app.wordpress_connector.slug import evaluate_slug_sync, slug_from_public_url


def test_slug_from_public_url() -> None:
    assert slug_from_public_url("https://test.example.com/tb-500-vs-bpc-157/") == "tb-500-vs-bpc-157"


def test_evaluate_slug_sync_warns_when_wordpress_ignores_request() -> None:
    warning = evaluate_slug_sync(
        recommended_slug="tb-500-vs-bpc-157",
        request_slug="tb-500-vs-bpc-157",
        response_slug="tb-500-vs-bpc-157-relationship-article-on-why-these-peptides-appear-toge",
    )
    assert warning is not None
    assert "tb-500-vs-bpc-157" in warning


def test_evaluate_slug_sync_silent_when_slugs_match() -> None:
    assert (
        evaluate_slug_sync(
            recommended_slug="tb-500-vs-bpc-157",
            request_slug="tb-500-vs-bpc-157",
            response_slug="tb-500-vs-bpc-157",
        )
        is None
    )


def test_create_draft_payload_includes_recommended_slug() -> None:
    job = {
        "id": "job-1",
        "workspace_id": "ws-1",
        "status": "completed",
        "recommended_slug": "tb-500-vs-bpc-157",
        "request_input": {},
    }
    repositories = MagicMock()
    repositories.jobs.get_job = AsyncMock(return_value=job)
    repositories.jobs.mark_status = AsyncMock()
    repositories.jobs.update_wordpress_publish_state = AsyncMock(
        side_effect=lambda job_id, **fields: {**job, **fields, "id": job_id}
    )
    repositories.workspace_content_inventory.list_for_workspace = AsyncMock(return_value=[])
    repositories.artifacts.create_artifact = AsyncMock()
    job_service = MagicMock()
    job_service._resolve_publishable_html = AsyncMock(return_value="<p>body</p>")  # noqa: SLF001
    job_service._latest_artifact_json = AsyncMock(return_value={"title": "Long title"})  # noqa: SLF001
    job_service.run_seo_optimization = AsyncMock()
    service = WordPressConnectorService(MagicMock(), repositories, job_service=job_service)
    client = MagicMock()
    client.create_draft = AsyncMock(
        return_value={
            "id": 4621,
            "slug": "long-title-slug",
            "edit_url": "https://example.com/wp-admin/post.php?post=4621&action=edit",
            "url": "https://example.com/long-title-slug/",
            "status": "draft",
        }
    )

    async def _run() -> dict[str, Any]:
        with patch.object(service, "_client", return_value=client):
            with patch.object(service, "_connector_row", AsyncMock(return_value={"workspace_id": "ws-1"})):
                with patch.object(
                    service,
                    "_connector_config",
                    AsyncMock(
                        return_value={
                            "connector_enabled": True,
                            "wordpress_base_url": "https://example.com",
                        }
                    ),
                ):
                    return await service.create_wordpress_draft("job-1")

    result = asyncio.run(_run())
    payload = json.loads(client.create_draft.await_args.args[0])
    assert payload["slug"] == "tb-500-vs-bpc-157"
    assert result.get("slug_sync_warning")
