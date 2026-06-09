from __future__ import annotations

from app.analyze_flow import mark_step, new_analyze_flow_state
from app.analyze_ui import ANALYZE_WEBSITE_HTML


def test_analyze_ui_delete_action_in_menu() -> None:
    assert "Delete analysis" in ANALYZE_WEBSITE_HTML
    assert "data-delete-run" in ANALYZE_WEBSITE_HTML
    assert "deleteAnalysisRun" in ANALYZE_WEBSITE_HTML
    assert "rerun-menu-item-danger" in ANALYZE_WEBSITE_HTML


def test_delete_blocks_in_progress_overall_status() -> None:
    state = new_analyze_flow_state()
    state.overall_status = "running"
    mark_step(state, "website_crawl", "running", "Scraping pages.")
    assert state.overall_status == "running"
    assert any(step.status == "running" for step in state.steps)


def test_delete_allowed_when_terminal() -> None:
    state = new_analyze_flow_state()
    mark_step(state, "website_crawl", "succeeded", "Done.")
    state.overall_status = "succeeded"
    assert state.overall_status not in {"running", "queued"}
    assert not any(step.status == "running" for step in state.steps)
