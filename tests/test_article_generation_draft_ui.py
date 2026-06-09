from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.services.jobs import GENERATION_ACTIVE_STATUSES, JobService


def test_analyze_ui_async_draft_generation_and_console() -> None:
    assert "/generate-article/async" in ANALYZE_WEBSITE_HTML
    assert "draft-console" in ANALYZE_WEBSITE_HTML
    assert "Recent article jobs" in ANALYZE_WEBSITE_HTML
    assert "tokens-per-minute" in ANALYZE_WEBSITE_HTML
    assert "Stop running" in ANALYZE_WEBSITE_HTML
    assert "data-delete-draft-job" in ANALYZE_WEBSITE_HTML


def test_generation_active_statuses_include_pipeline_stages() -> None:
    assert "queued" in GENERATION_ACTIVE_STATUSES
    assert "running_generation" in GENERATION_ACTIVE_STATUSES
    assert "running_review" in GENERATION_ACTIVE_STATUSES
    assert "completed" not in GENERATION_ACTIVE_STATUSES


def test_get_generation_result_none_while_running() -> None:
    repositories = MagicMock()
    repositories.jobs.get_job = AsyncMock(return_value={"status": "running_generation"})
    service = JobService(settings=MagicMock(), registry=MagicMock(), repositories=repositories)
    result = asyncio.run(service.get_generation_result("job-1"))
    assert result is None


def test_get_generation_result_builds_summary_when_terminal() -> None:
    repositories = MagicMock()
    repositories.jobs.get_job = AsyncMock(
        return_value={
            "status": "completed",
            "human_review_required": True,
            "request_input": {"publish_policy": "manual_review"},
        }
    )
    service = JobService(settings=MagicMock(), registry=MagicMock(), repositories=repositories)
    service._latest_artifact_json = AsyncMock(side_effect=lambda _job_id, artifact_type: {  # noqa: SLF001
        "quality_check_results": {"passed": True, "status": "pass"},
        "final_quality_check_results": {"passed": True, "status": "pass"},
        "structured_article_json": {"title": "Test"},
        "wordpress_presentation_metadata": {"seo_title": "SEO"},
        "sanity_check_results": {"passed": True},
    }.get(artifact_type))
    service._latest_artifact_text = AsyncMock(return_value="<p>html</p>")  # noqa: SLF001
    result = asyncio.run(service.get_generation_result("job-1"))
    assert result is not None
    assert result["job_id"] == "job-1"
    assert result["status"] == "completed"
    assert result["structured_article"]["title"] == "Test"
