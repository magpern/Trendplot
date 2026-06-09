from __future__ import annotations

import re

from app.analyze_flow import extract_flow_summary
from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.config import Settings


def _sample_recommendations() -> list[dict]:
    return [
        {"title": "Create guide A", "action": "create", "score": 0.9, "priority": "high", "topic": "guide a"},
        {"title": "Create guide B", "action": "create", "score": 0.85, "priority": "high", "topic": "guide b"},
        {"title": "Refresh old post", "action": "refresh", "score": 0.7, "priority": "medium", "topic": "refresh", "metadata": {"inventory_url": "https://example.com/old/"}},
        {"title": "Monitor trend", "action": "monitor", "score": 0.5, "priority": "low", "topic": "trend", "explanation": "Wait for more demand."},
        {"title": "Ignore noise", "action": "ignore", "score": 0.2, "priority": "low", "topic": "noise", "explanation": "Low relevance."},
    ]


def test_flow_summary_includes_full_recommendation_items() -> None:
    recs = _sample_recommendations()
    summary = extract_flow_summary(
        workspace_payload={
            "workspace": {"id": "ws", "name": "Site", "website_url": "https://example.com", "mode": "manual_review", "settings": {}},
            "niche_profile": {},
            "opportunity_intelligence": {
                "recommendations": recs,
                "summary": {"total": 5, "create": 2, "refresh": 1, "monitor": 1, "ignore": 1},
            },
        },
        analysis_payload={"analysis_page_count": 8, "analysis": {"pages": [], "artifacts": []}},
        plan_payload={"items": []},
        settings=Settings(),
    )
    assert len(summary["recommendations"]["items"]) == 5
    assert summary["recommendations"]["create"] == 2
    assert summary["recommendations"]["monitor"] == 1


def test_analyze_ui_recommendation_queue_filters_present() -> None:
    assert "rec-queue-filters" in ANALYZE_WEBSITE_HTML
    assert "recommendationQueueFilter" in ANALYZE_WEBSITE_HTML
    assert "data-rec-filter" in ANALYZE_WEBSITE_HTML
    assert "No recommendations in this queue." in ANALYZE_WEBSITE_HTML


def test_analyze_ui_action_specific_ctas() -> None:
    assert "Select for draft" in ANALYZE_WEBSITE_HTML
    assert "Review refresh task" in ANALYZE_WEBSITE_HTML
    assert "Keep monitoring" in ANALYZE_WEBSITE_HTML
    assert "Promote to draft" in ANALYZE_WEBSITE_HTML
    assert "Existing page:" in ANALYZE_WEBSITE_HTML


def test_analyze_ui_filter_logic_in_script() -> None:
    assert "filteredRecommendations" in ANALYZE_WEBSITE_HTML
    assert 'recommendationQueueFilter = "create"' in ANALYZE_WEBSITE_HTML
    assert "recommendationCountMismatches" in ANALYZE_WEBSITE_HTML
    assert "Recommendation count mismatch" in ANALYZE_WEBSITE_HTML
    assert "recommendationQueueCounts" in ANALYZE_WEBSITE_HTML
    assert "resolveRecommendationItems" in ANALYZE_WEBSITE_HTML
    assert "opportunity_recommendations" in ANALYZE_WEBSITE_HTML
    assert "exportRecommendationsCsv" in ANALYZE_WEBSITE_HTML
    assert "Export CSV" in ANALYZE_WEBSITE_HTML


def test_analyze_ui_active_filter_class() -> None:
    assert re.search(r'rec-queue-filter.*active', ANALYZE_WEBSITE_HTML)


def test_monitor_items_no_select_for_draft_by_default() -> None:
    actions_fn = ANALYZE_WEBSITE_HTML.split("function renderRecommendationActions")[1].split("function renderRecommendationList")[0]
    assert "Keep monitoring" in actions_fn
    assert "Promote to draft" in actions_fn
    monitor_idx = actions_fn.index('if (action === "monitor")')
    create_idx = actions_fn.index('if (action === "create")')
    monitor_section = actions_fn[monitor_idx:create_idx]
    assert "Select for draft" not in monitor_section


def test_refresh_items_use_refresh_cta() -> None:
    refresh_block = ANALYZE_WEBSITE_HTML.split('if (action === "refresh")')[1].split("if (action ===")[0]
    assert "Review refresh task" in refresh_block
    assert "Select for draft" not in refresh_block


def test_ignore_items_have_no_draft_button() -> None:
    actions_fn = ANALYZE_WEBSITE_HTML.split("function renderRecommendationActions")[1].split("function wireRecommendationList")[0]
    assert 'action === "ignore"' not in actions_fn
    assert actions_fn.strip().endswith('return "";') or 'return "";' in actions_fn
