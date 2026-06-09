from __future__ import annotations

from app.analyze_flow import (
    finish_overall_status,
    mark_step,
    merge_flow_summary,
    new_analyze_flow_state,
    new_analyze_flow_state_from_parent,
    skip_unstarted_flow_steps,
    update_step_progress,
)


def test_partial_rerun_preserves_completed_parent_steps() -> None:
    parent = new_analyze_flow_state()
    mark_step(parent, "website_crawl", "succeeded", "Scraped 30 pages.")
    mark_step(parent, "ai_opportunity_ideation", "succeeded", "Generated 40 opportunities.")
    mark_step(parent, "opportunity_ranking", "succeeded", "Saved 40 recommendations.")

    child = new_analyze_flow_state_from_parent(parent, rerun_type="recommendations")
    assert child.step("website_crawl").status == "succeeded"
    assert child.step("ai_opportunity_ideation").status == "queued"
    assert child.step("opportunity_ranking").status == "queued"
    assert child.step("content_calendar").status == "queued"


def test_partial_rerun_only_resets_target_steps_for_recommendations() -> None:
    parent = new_analyze_flow_state()
    mark_step(parent, "ai_opportunity_ideation", "succeeded", "Generated 40 opportunities.")
    mark_step(parent, "opportunity_ranking", "succeeded", "Saved 40 recommendations.")
    mark_step(parent, "content_calendar", "succeeded", "Calendar built.")

    child = new_analyze_flow_state_from_parent(parent, rerun_type="recommendations")
    assert child.step("ai_opportunity_ideation").status == "queued"
    assert child.step("opportunity_ranking").status == "queued"
    assert child.step("content_calendar").status == "succeeded"


def test_finish_overall_status_stays_running_while_step_reopens() -> None:
    state = new_analyze_flow_state()
    mark_step(state, "website_crawl", "succeeded", "Pre-crawl finished.")
    update_step_progress(state, "website_crawl", "Scraping page 2 of 20")
    assert state.step("website_crawl").status == "running"
    finish_overall_status(state)
    assert state.overall_status == "running"


def test_finish_overall_status_stays_running_when_warning_and_queued_remain() -> None:
    state = new_analyze_flow_state()
    mark_step(state, "ai_opportunity_ideation", "warning", "No opportunities generated.")
    mark_step(state, "website_analysis", "succeeded", "Website analysis completed.")
    assert state.step("opportunity_ranking").status == "queued"
    finish_overall_status(state)
    assert state.overall_status == "running"


def test_partial_rerun_marks_tail_steps_skipped() -> None:
    state = new_analyze_flow_state()
    mark_step(state, "opportunity_ranking", "succeeded", "Done.")
    skip_unstarted_flow_steps(state, note="Not part of this partial rerun.")
    finish_overall_status(state)
    assert state.step("draft_generation").status == "skipped"
    assert state.overall_status == "succeeded"


def test_merge_flow_summary_keeps_prior_fields() -> None:
    prior = {
        "workspace": {"name": "Example Lab"},
        "recommendations": {"total": 80},
    }
    updated = {"recommendations": {"total": 85, "create": 40}}
    merged = merge_flow_summary(prior, updated)
    assert merged["workspace"]["name"] == "Example Lab"
    assert merged["recommendations"]["total"] == 85
    assert merged["recommendations"]["create"] == 40
