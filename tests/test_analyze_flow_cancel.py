from __future__ import annotations

from app.analyze_flow import finish_overall_status, mark_flow_cancelled, mark_step, new_analyze_flow_state
from app.analyze_ui import ANALYZE_WEBSITE_HTML


def test_analyze_ui_stop_button() -> None:
    assert 'id="stop-run-button"' in ANALYZE_WEBSITE_HTML
    assert "Stop analysis" in ANALYZE_WEBSITE_HTML
    assert "stopCurrentRun" in ANALYZE_WEBSITE_HTML
    assert "/cancel" in ANALYZE_WEBSITE_HTML


def test_mark_flow_cancelled_sets_terminal_state() -> None:
    state = new_analyze_flow_state()
    mark_step(state, "website_crawl", "running", "Scraping pages.")
    mark_step(state, "website_analysis", "queued", "")
    mark_flow_cancelled(state, "Analysis cancelled by user.")
    assert state.cancel_requested is True
    assert state.overall_status == "cancelled"
    assert state.step("website_crawl").status == "failed"
    assert state.step("website_analysis").status == "skipped"


def test_finish_overall_status_preserves_cancelled() -> None:
    state = new_analyze_flow_state()
    mark_flow_cancelled(state)
    finish_overall_status(state)
    assert state.overall_status == "cancelled"
