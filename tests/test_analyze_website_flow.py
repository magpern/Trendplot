from __future__ import annotations

import asyncio

from app.analyze_flow import (
    extract_flow_summary,
    mark_step,
    new_analyze_flow_state,
    publishing_safety_state,
    summarize_steps_from_payloads,
    update_step_progress,
)
from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.api.routes import _analyze_flow_progress_callback, _create_or_reuse_workspace_for_flow, _find_workspace_by_url
from app.api.routes import AnalyzeWebsiteFlowRequest
from app.config import Settings


class _FakeAutopilot:
    def __init__(self, workspaces):
        self.workspaces = workspaces

    async def list_workspaces(self):
        return self.workspaces


def test_analyze_form_renders():
    assert "Analyze Website" in ANALYZE_WEBSITE_HTML
    assert 'id="website_url"' in ANALYZE_WEBSITE_HTML
    assert 'id="start-button"' in ANALYZE_WEBSITE_HTML
    assert "ENTITY_RELEVANCE_BATCH_SIZE" not in ANALYZE_WEBSITE_HTML


def test_submit_reuses_workspace_by_url():
    autopilot = _FakeAutopilot([{"id": "ws-1", "website_url": "https://www.example.com/"}])
    found = asyncio.run(_find_workspace_by_url(autopilot, "https://example.com"))
    assert found and found["id"] == "ws-1"


def test_reused_workspace_merges_provided_competitors():
    class _Autopilot:
        def __init__(self):
            self.merge_calls: list[tuple[str, list[str]]] = []

        async def list_workspaces(self):
            return [{"id": "ws-1", "website_url": "https://www.example.com/"}]

        async def merge_workspace_competitors(self, workspace_id: str, competitor_urls: list[str]) -> list[str]:
            self.merge_calls.append((workspace_id, competitor_urls))
            return competitor_urls

        async def get_workspace(self, workspace_id: str):
            return {"workspace": {"id": workspace_id, "website_url": "https://www.example.com/"}}

        async def create_workspace(self, **kwargs):
            raise AssertionError("create_workspace should not run when reusing")

    autopilot = _Autopilot()
    payload = AnalyzeWebsiteFlowRequest(
        website_url="https://example.com",
        competitor_urls=["https://rival.example"],
    )
    result = asyncio.run(_create_or_reuse_workspace_for_flow(autopilot, payload))
    assert autopilot.merge_calls == [("ws-1", ["https://rival.example/"])]
    assert result["workspace"]["id"] == "ws-1"


def test_product_analyze_flow_has_ten_steps() -> None:
    from app.analyze_flow import PRODUCT_ANALYZE_STEP_KEYS

    state = new_analyze_flow_state()
    keys = {step.key for step in state.steps}
    assert keys == set(PRODUCT_ANALYZE_STEP_KEYS)
    assert "competitor_discovery" not in keys
    assert "market_intelligence" not in keys
    assert not any(step["status"] == "disabled" for step in state.as_dict()["steps"])


def test_future_steps_remain_queued_before_they_start():
    state = new_analyze_flow_state()
    mark_step(state, "workspace_setup", "succeeded", "Workspace ready.")
    update_step_progress(state, "sitemap_discovery", "Checking robots.txt")
    payload = state.as_dict()
    assert next(step for step in payload["steps"] if step["key"] == "sitemap_discovery")["status"] == "running"
    assert next(step for step in payload["steps"] if step["key"] == "website_crawl")["status"] == "queued"
    assert next(step for step in payload["steps"] if step["key"] == "ai_opportunity_ideation")["status"] == "queued"


def test_only_current_step_is_running():
    state = new_analyze_flow_state()
    update_step_progress(state, "sitemap_discovery", "Checking robots.txt")
    update_step_progress(state, "website_crawl", "Scraping page 1 of 30")
    running = [step.key for step in state.steps if step.status == "running"]
    assert running == ["website_crawl"]


def test_sitemap_progress_details_appear():
    state = new_analyze_flow_state()
    callback = _analyze_flow_progress_callback(object(), state)
    asyncio.run(
        callback(
            {
                "step": "sitemap_discovery",
                "message": "Selected 30 URLs from 39 discovered",
                "progress_current": 30,
                "progress_total": 39,
                "progress_label": "Selected 30 of 39",
                "details": {
                    "robots_txt_checked": True,
                    "sitemap_urls_found": 4,
                    "sitemap_urls_discovered": 39,
                    "sitemap_urls_selected": 30,
                    "crawl_fallback_used": False,
                },
            }
        )
    )
    step = state.step("sitemap_discovery")
    assert step.status == "running"
    assert step.progress_current == 30
    assert step.progress_total == 39
    assert step.details["sitemap_urls_found"] == 4


def test_crawl_progress_details_appear():
    state = new_analyze_flow_state()
    callback = _analyze_flow_progress_callback(object(), state)
    asyncio.run(
        callback(
            {
                "step": "website_crawl",
                "message": "Scraping page 10/30: /faq/",
                "progress_current": 10,
                "progress_total": 30,
                "details": {"current_url": "https://example.com/faq/", "current_path": "/faq/"},
            }
        )
    )
    step = state.step("website_crawl")
    assert step.status == "running"
    assert step.progress_current == 10
    assert step.details["current_url"] == "https://example.com/faq/"


def test_failed_step_surfaces_error():
    state = new_analyze_flow_state()
    mark_step(state, "website_analysis", "failed", "Analyzing crawled pages", error="OpenAI request failed.")
    payload = state.as_dict()
    failed = next(step for step in payload["steps"] if step["key"] == "website_analysis")
    assert failed["status"] == "failed"
    assert failed["error"] == "OpenAI request failed."


def test_warning_step_renders_message_contract():
    state = new_analyze_flow_state()
    mark_step(state, "sitemap_discovery", "warning", "Malformed sitemap ignored.", warnings=["One sitemap was malformed."])
    step = state.as_dict()["steps"][1]
    assert step["status"] == "warning"
    assert step["message"] == "Malformed sitemap ignored."
    assert step["warnings"] == ["One sitemap was malformed."]


def test_low_content_warning_surfaces():
    summary = extract_flow_summary(
        workspace_payload={
            "workspace": {"id": "ws", "name": "Site", "website_url": "https://example.com", "mode": "manual_review", "settings": {}},
            "niche_profile": {"primary_niche": "generic", "confidence": 0.4},
            "opportunity_intelligence": {"recommendations": [], "summary": {"total": 0}},
            "calendar_items": [],
        },
        analysis_payload={"low_content_warning": "Low content depth.", "analysis_page_count": 2, "analysis": {"pages": [], "artifacts": []}},
        plan_payload={"items": []},
        settings=Settings(WORDPRESS_BASE_URL="", WORDPRESS_USERNAME="", WORDPRESS_APP_PASSWORD=""),
    )
    assert "Low content depth." in summary["warnings"]
    assert summary["site"]["low_content_warning"] == "Low content depth."


def test_recommendations_render_data_available():
    summary = extract_flow_summary(
        workspace_payload={
            "workspace": {"id": "ws", "name": "Site", "website_url": "https://example.com", "mode": "manual_review", "settings": {}},
            "niche_profile": {"primary_niche": "analytics", "confidence": 0.8},
            "opportunity_intelligence": {
                "recommendations": [{"title": "Create analytics comparison", "action": "create", "score": 0.8}],
                "summary": {"total": 1, "create": 1, "refresh": 0, "monitor": 0, "ignore": 0},
            },
            "calendar_items": [],
        },
        analysis_payload={"analysis_page_count": 8, "analysis": {"pages": [], "artifacts": []}},
        plan_payload={"items": []},
        settings=Settings(),
    )
    assert summary["recommendations"]["total"] == 1
    assert summary["recommendations"]["items"][0]["title"] == "Create analytics comparison"
    assert summary["recommendations"]["top"][0]["title"] == "Create analytics comparison"


def test_schedule_render_data_available():
    summary = extract_flow_summary(
        workspace_payload={
            "workspace": {"id": "ws", "name": "Site", "website_url": "https://example.com", "mode": "manual_review", "settings": {}},
            "niche_profile": {},
            "opportunity_intelligence": {"recommendations": [], "summary": {"total": 0}},
        },
        analysis_payload={"analysis_page_count": 8, "analysis": {"pages": [], "artifacts": []}},
        plan_payload={"items": [{"id": "item-1", "title": "Post", "scheduled_for": "2026-06-08", "content_role": "trend_article", "state": "planned"}]},
        settings=Settings(),
    )
    assert summary["schedule"][0]["title"] == "Post"
    assert summary["schedule"][0]["suggested_publish_date"] == "2026-06-08"


def test_step_details_open_state_is_preserved_in_ui():
    assert "openStepDetails" in ANALYZE_WEBSITE_HTML
    assert "syncOpenStepDetailsFromDom" in ANALYZE_WEBSITE_HTML
    assert 'data-step-key="${escapeHtml(step.key)}"' in ANALYZE_WEBSITE_HTML


def test_summarize_steps_marks_ideation_and_ranking():
    state = new_analyze_flow_state()
    summarize_steps_from_payloads(
        state,
        analysis_payload={
            "analysis_page_count": 8,
            "analysis": {"pages": [], "artifacts": []},
            "ai_opportunity_ideation": {"metrics": {"opportunities_created": 42}},
        },
        workspace_payload={"opportunity_intelligence": {"summary": {"total": 40}}},
        settings=Settings(),
    )
    assert state.step("ai_opportunity_ideation").status == "succeeded"
    assert "42" in state.step("ai_opportunity_ideation").message
    assert state.step("opportunity_ranking").status == "succeeded"
    assert "40" in state.step("opportunity_ranking").message


def test_analyze_ui_recent_runs_compact_without_inline_rerun_buttons():
    assert "RECENT_RUNS_VISIBLE = 3" in ANALYZE_WEBSITE_HTML
    assert "View all previous analyses" in ANALYZE_WEBSITE_HTML
    assert "recent-runs-older" in ANALYZE_WEBSITE_HTML
    assert "renderRecentRunCard" in ANALYZE_WEBSITE_HTML
    assert "buildRerunActionsHtml" not in ANALYZE_WEBSITE_HTML
    assert "rerun-toolbar" not in ANALYZE_WEBSITE_HTML
    assert "disabled:" not in ANALYZE_WEBSITE_HTML or "rerun-menu-item" in ANALYZE_WEBSITE_HTML


def test_analyze_ui_delete_in_actions_menu():
    assert "Delete analysis" in ANALYZE_WEBSITE_HTML
    assert 'method: "DELETE"' in ANALYZE_WEBSITE_HTML


def test_analyze_ui_running_progress_visibility():
    assert "active-run-banner" in ANALYZE_WEBSITE_HTML
    assert "Analysis in progress" in ANALYZE_WEBSITE_HTML
    assert "renderActiveRunBanner" in ANALYZE_WEBSITE_HTML
    assert "Analyzing…" in ANALYZE_WEBSITE_HTML
    assert "pulse-dot" in ANALYZE_WEBSITE_HTML
    assert "startElapsedTimer" in ANALYZE_WEBSITE_HTML


def test_analyze_ui_rerun_menu_and_step_icons():
    assert "renderRerunMenuHtml" in ANALYZE_WEBSITE_HTML
    assert "rerun-menu-item" in ANALYZE_WEBSITE_HTML
    assert "Re-run AI recommendations" in ANALYZE_WEBSITE_HTML
    assert "Re-generate schedule" in ANALYZE_WEBSITE_HTML
    assert "Start full re-analysis" in ANALYZE_WEBSITE_HTML
    assert "Website analysis incomplete." in ANALYZE_WEBSITE_HTML
    assert "renderStepRerunIcon" in ANALYZE_WEBSITE_HTML
    assert "data-step-rerun" in ANALYZE_WEBSITE_HTML
    assert "STEP_RERUN_TYPES" in ANALYZE_WEBSITE_HTML
    assert "Open result" in ANALYZE_WEBSITE_HTML
    assert 'title="${escapeHtml(title)}"' in ANALYZE_WEBSITE_HTML or "title=" in ANALYZE_WEBSITE_HTML


def test_draft_generation_action_is_gated():
    assert 'id="generate-draft"' in ANALYZE_WEBSITE_HTML
    assert "Select a recommendation or schedule item first." in ANALYZE_WEBSITE_HTML


def test_progress_counters_and_details_renderers_exist():
    assert "renderProgress(step)" in ANALYZE_WEBSITE_HTML
    assert "renderStepDetails(step)" in ANALYZE_WEBSITE_HTML
    assert "renderStepStatus(step)" in ANALYZE_WEBSITE_HTML
    assert "renderTimingNote(step)" in ANALYZE_WEBSITE_HTML
    assert "Recommendations" in ANALYZE_WEBSITE_HTML
    assert "progress_current" in ANALYZE_WEBSITE_HTML
    assert "data-step-key" in ANALYZE_WEBSITE_HTML
    assert "<summary>Details</summary>" in ANALYZE_WEBSITE_HTML


def test_backwards_compatibility_with_old_status_payload():
    state = new_analyze_flow_state()
    payload = state.as_dict()
    first = payload["steps"][0]
    first.pop("progress_current")
    first.pop("progress_total")
    first.pop("progress_label")
    first.pop("details")
    assert "message" in first
    assert "renderProgress(step)" in ANALYZE_WEBSITE_HTML


def test_inferred_completed_steps_do_not_get_fake_durations():
    state = new_analyze_flow_state()
    summarize_steps_from_payloads(
        state,
        analysis_payload={"analysis_page_count": 8, "analysis": {"artifacts": []}},
        workspace_payload={"opportunity_intelligence": {"summary": {}}},
        settings=Settings(),
    )
    ideation_step = state.step("ai_opportunity_ideation")
    assert ideation_step.duration_seconds is None
    assert ideation_step.completed_at is None
    assert ideation_step.timing_note == "included in analysis phase"


def test_wordpress_draft_action_disabled_when_not_configured():
    safety = publishing_safety_state(Settings(WORDPRESS_CONNECTOR_ENABLED=False))
    assert safety["draft_upload_available"] is False
    assert "Trendplot Connector" in (safety["draft_disabled_reason"] or "")


def test_live_publish_disabled_via_connector():
    safety = publishing_safety_state(
        Settings(
            WORDPRESS_CONNECTOR_ENABLED=True,
            WORDPRESS_CONNECTOR_BASE_URL="https://example.com",
            WORDPRESS_CONNECTOR_SITE_ID="site-1",
            WORDPRESS_CONNECTOR_SECRET="secret",
            ALLOW_LIVE_PUBLISH=True,
        )
    )
    assert safety["draft_upload_available"] is True
    assert safety["live_publish_available"] is False
    assert "drafts only" in (safety["live_disabled_reason"] or "").lower()
