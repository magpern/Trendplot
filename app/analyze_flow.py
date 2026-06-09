from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings


RUNNING_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"succeeded", "failed", "skipped", "warning", "cancelled", "disabled"}


@dataclass(slots=True)
class AnalyzeFlowStep:
    key: str
    label: str
    status: str = "queued"
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    message: str = ""
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    progress_current: int | None = None
    progress_total: int | None = None
    progress_label: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timing_note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "message": self.message,
            "error": self.error,
            "warnings": list(self.warnings),
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "progress_label": self.progress_label,
            "details": dict(self.details),
            "timing_note": self.timing_note,
        }


@dataclass(slots=True)
class AnalyzeFlowState:
    workspace_id: str | None = None
    job_id: str = field(default_factory=lambda: str(uuid4()))
    parent_run_id: str | None = None
    rerun_type: str | None = None
    website_url: str | None = None
    run_label: str | None = None
    request_payload: dict[str, Any] = field(default_factory=dict)
    prior_summary: dict[str, Any] = field(default_factory=dict)
    overall_status: str = "queued"
    cancel_requested: bool = False
    steps: list[AnalyzeFlowStep] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def step(self, key: str) -> AnalyzeFlowStep:
        for item in self.steps:
            if item.key == key:
                return item
        raise KeyError(key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "job_id": self.job_id,
            "parent_run_id": self.parent_run_id,
            "rerun_type": self.rerun_type,
            "website_url": self.website_url,
            "run_label": self.run_label,
            "request_payload": dict(self.request_payload),
            "prior_summary": dict(self.prior_summary),
            "overall_status": self.overall_status,
            "cancel_requested": self.cancel_requested,
            "steps": [step.as_dict() for step in self.steps],
            "summary": self.summary,
        }


PRODUCT_ANALYZE_STEP_KEYS: frozenset[str] = frozenset(
    {
        "workspace_setup",
        "sitemap_discovery",
        "website_crawl",
        "website_analysis",
        "niche_intelligence",
        "ai_opportunity_ideation",
        "opportunity_ranking",
        "content_calendar",
        "draft_generation",
        "wordpress_upload",
    }
)

REQUIRED_ANALYZE_STEPS: tuple[tuple[str, str, str], ...] = (
    ("workspace_setup", "Workspace setup", "Creating or reusing the Trendplot workspace."),
    ("sitemap_discovery", "Sitemap discovery", "Finding public sitemap files and selecting important URLs."),
    ("website_crawl", "Website crawl", "Scraping selected website pages."),
    ("website_analysis", "Website analysis", "Analyzing crawled page signals."),
    ("niche_intelligence", "Niche intelligence", "Persisting stable niche context."),
    ("ai_opportunity_ideation", "AI article ideation", "Generating catalog-aware article opportunities."),
    ("opportunity_ranking", "Recommendations", "Saving ranked article recommendations."),
    ("content_calendar", "Content calendar generation", "Building the proposed publishing schedule."),
    ("draft_generation", "Draft generation", "Available after selecting a recommendation or calendar item."),
    ("wordpress_upload", "WordPress upload", "Available as an explicit operator action when configured."),
)


PARTIAL_RERUN_STEP_KEYS: dict[str, tuple[str, ...]] = {
    "recommendations": ("ai_opportunity_ideation", "opportunity_ranking"),
    "schedule": ("content_calendar",),
}


def partial_rerun_step_keys(rerun_type: str, settings: Settings | None = None) -> tuple[str, ...]:
    del settings
    return PARTIAL_RERUN_STEP_KEYS.get(rerun_type, ())


def new_analyze_flow_state(settings: Settings | None = None) -> AnalyzeFlowState:
    del settings
    return AnalyzeFlowState(
        steps=[AnalyzeFlowStep(key=key, label=label, message=message) for key, label, message in REQUIRED_ANALYZE_STEPS],
    )


def _copy_step_state(target: AnalyzeFlowStep, source: AnalyzeFlowStep) -> None:
    target.status = source.status
    target.started_at = source.started_at
    target.completed_at = source.completed_at
    target.duration_seconds = source.duration_seconds
    target.message = source.message
    target.error = source.error
    target.warnings = list(source.warnings)
    target.progress_current = source.progress_current
    target.progress_total = source.progress_total
    target.progress_label = source.progress_label
    target.details = copy.deepcopy(source.details)
    target.timing_note = source.timing_note


def new_analyze_flow_state_from_parent(
    parent: AnalyzeFlowState,
    *,
    rerun_type: str,
    settings: Settings | None = None,
) -> AnalyzeFlowState:
    effective_settings = settings or Settings()
    state = new_analyze_flow_state(effective_settings)
    affected = set(partial_rerun_step_keys(rerun_type, effective_settings))
    parent_steps = {item.key: item for item in parent.steps}
    for step in state.steps:
        prior = parent_steps.get(step.key)
        if prior is None:
            continue
        if step.key in affected:
            step.status = "queued"
            step.message = f"Waiting to re-run ({rerun_type.replace('_', ' ')})."
            step.error = None
            step.warnings = []
            step.progress_current = None
            step.progress_total = None
            step.progress_label = None
            step.started_at = None
            step.completed_at = None
            step.duration_seconds = None
            step.timing_note = None
            continue
        _copy_step_state(step, prior)
        if not step.timing_note and step.status in TERMINAL_STATUSES:
            step.timing_note = "preserved from previous run"
    return state


def merge_flow_summary(prior: dict[str, Any], updated: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(prior)
    for key, value in updated.items():
        if value is None:
            continue
        if isinstance(value, dict) and not value:
            continue
        if isinstance(value, list) and not value:
            continue
        merged[key] = value
    return merged


def mark_step(
    state: AnalyzeFlowState,
    key: str,
    status: str,
    message: str = "",
    *,
    error: str | None = None,
    warnings: list[str] | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_label: str | None = None,
    details: dict[str, Any] | None = None,
    timing_note: str | None = None,
) -> AnalyzeFlowStep:
    step = state.step(key)
    if step.status in TERMINAL_STATUSES and status == "running":
        step.completed_at = None
        step.duration_seconds = None
        step.error = None

    if status == "running":
        for other in state.steps:
            if other.key != key and other.status == "running":
                other.status = "queued"
    now = _now()
    if status == "running" and step.started_at is None:
        step.started_at = now
    if status in TERMINAL_STATUSES and step.started_at and step.completed_at is None:
        step.completed_at = now
        step.duration_seconds = _duration_seconds(step.started_at, step.completed_at)
    step.status = status
    if message:
        step.message = message
    step.error = error
    if warnings is not None:
        step.warnings = warnings
    if progress_current is not None:
        step.progress_current = progress_current
    if progress_total is not None:
        step.progress_total = progress_total
    if progress_label is not None:
        step.progress_label = progress_label
    if details is not None:
        step.details.update({key: value for key, value in details.items() if value is not None})
    if timing_note is not None:
        step.timing_note = timing_note
    return step


def update_step_progress(
    state: AnalyzeFlowState,
    key: str,
    message: str,
    *,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_label: str | None = None,
    details: dict[str, Any] | None = None,
    timing_note: str | None = None,
) -> AnalyzeFlowStep:
    return mark_step(
        state,
        key,
        "running",
        message,
        progress_current=progress_current,
        progress_total=progress_total,
        progress_label=progress_label,
        details=details,
        timing_note=timing_note,
    )


def finish_overall_status(state: AnalyzeFlowState) -> None:
    if state.cancel_requested or state.overall_status == "cancelled":
        state.overall_status = "cancelled"
        return
    if any(step.status == "failed" for step in state.steps):
        state.overall_status = "failed"
        return
    if any(step.status == "running" for step in state.steps):
        state.overall_status = "running"
        return
    # Keep the run alive while later pipeline steps have not started yet.
    if any(step.status == "queued" for step in state.steps):
        state.overall_status = "running"
        return
    if any(step.status == "warning" for step in state.steps):
        state.overall_status = "warning"
        return
    if all(step.status in TERMINAL_STATUSES for step in state.steps):
        state.overall_status = "succeeded"
        return
    state.overall_status = "running"


def mark_flow_cancelled(state: AnalyzeFlowState, message: str = "Analysis cancelled.") -> None:
    state.cancel_requested = True
    for step in state.steps:
        if step.status == "running":
            mark_step(state, step.key, "failed", message, error=message)
        elif step.status == "queued":
            mark_step(state, step.key, "skipped", "Cancelled before start.")
    state.overall_status = "cancelled"


def skip_unstarted_flow_steps(state: AnalyzeFlowState, *, note: str = "Not part of this run.") -> None:
    for step in state.steps:
        if step.status != "queued":
            continue
        mark_step(
            state,
            step.key,
            "skipped",
            note,
            timing_note="optional step",
        )


def mark_ideation_short_circuit_steps(state: AnalyzeFlowState, settings: Settings) -> None:
    """No-op: product analyze flow has no legacy steps."""
    del state, settings


def _summarize_recommendations_tail(
    state: AnalyzeFlowState,
    analysis_payload: dict[str, Any],
    workspace_payload: dict[str, Any],
    settings: Settings,
) -> None:
    ideation = (analysis_payload or {}).get("ai_opportunity_ideation") or {}
    metrics = ideation.get("metrics") if isinstance(ideation.get("metrics"), dict) else {}
    opp_count = int(metrics.get("opportunities_created") or len(ideation.get("opportunities") or []))
    oi_summary = ((workspace_payload.get("opportunity_intelligence") or {}).get("summary") or {})
    saved = int(oi_summary.get("total") or opp_count)

    mark_step(
        state,
        "ai_opportunity_ideation",
        _terminal_status(state, "ai_opportunity_ideation", "succeeded" if opp_count else "warning"),
        f"Generated {opp_count} AI article opportunities." if opp_count else "No AI article opportunities generated.",
        details=metrics,
        timing_note=_timing_note_if_inferred(state, "ai_opportunity_ideation"),
    )
    mark_step(
        state,
        "opportunity_ranking",
        _terminal_status(state, "opportunity_ranking", "succeeded" if saved else "warning"),
        f"Saved {saved} AI recommendations to your queue.",
        details={"recommendations_ranked": saved},
        timing_note=_timing_note_if_inferred(state, "opportunity_ranking"),
    )


def _connector_configured(settings: Settings) -> bool:
    return bool(
        settings.wordpress_connector_enabled
        and settings.wordpress_connector_base_url.strip()
        and settings.wordpress_connector_site_id.strip()
        and settings.wordpress_connector_secret.strip()
    )


def publishing_safety_state(settings: Settings) -> dict[str, Any]:
    connector_configured = _connector_configured(settings)
    return {
        "default_mode": "manual_review",
        "wordpress_configured": connector_configured,
        "draft_upload_available": connector_configured,
        "live_publish_available": False,
        "allow_live_publish": settings.allow_live_publish,
        "allow_auto_live": settings.allow_auto_live,
        "unattended_mode_enabled": settings.unattended_mode_enabled,
        "wordpress_connector_enabled": settings.wordpress_connector_enabled,
        "draft_disabled_reason": None
        if connector_configured
        else "WordPress upload unavailable: enable and configure the Trendplot Connector.",
        "live_disabled_reason": "Live publish is not available via the connector (drafts only).",
    }


def extract_flow_summary(
    *,
    workspace_payload: dict[str, Any],
    analysis_payload: dict[str, Any] | None = None,
    plan_payload: dict[str, Any] | None = None,
    settings: Settings,
) -> dict[str, Any]:
    workspace = workspace_payload.get("workspace") or {}
    niche_profile = workspace_payload.get("niche_profile") or {}
    recommendations = (workspace_payload.get("opportunity_intelligence") or {}).get("recommendations") or []
    recommendation_summary = (workspace_payload.get("opportunity_intelligence") or {}).get("summary") or {}
    calendar_items = (plan_payload or {}).get("items") or workspace_payload.get("calendar_items") or []
    low_content_warning = (analysis_payload or {}).get("low_content_warning")
    analysis_page_count = (analysis_payload or {}).get("analysis_page_count")
    pages = (analysis_payload or {}).get("analysis", {}).get("pages") or []
    artifacts = (analysis_payload or {}).get("analysis", {}).get("artifacts") or []
    url_discovery = _artifact_content(artifacts, "url_discovery")
    competitor_seo_intelligence = _artifact_content(artifacts, "competitor_seo_intelligence") or {}
    entity_relevance = ((workspace_payload.get("opportunity_intelligence") or {}).get("summary") or {}).get("entity_relevance") or {}
    competitor_discovery = (analysis_payload or {}).get("competitor_discovery") or {}
    strategy_profile = (analysis_payload or {}).get("strategy_profile")
    if not strategy_profile:
        strategy_profile = ((analysis_payload or {}).get("site_understanding") or {}).get("source", {}).get("strategy_profile")
    warnings = _flow_warnings(
        low_content_warning=low_content_warning,
        url_discovery=url_discovery,
        entity_relevance=entity_relevance,
        competitor_discovery=competitor_discovery,
        competitor_seo_intelligence=competitor_seo_intelligence,
        settings=settings,
        competitors=workspace_payload.get("workspace", {}).get("settings", {}).get("competitors", []),
    )
    return {
        "workspace": {
            "id": workspace.get("id"),
            "name": workspace.get("name"),
            "website_url": workspace.get("website_url"),
            "mode": workspace.get("mode"),
        },
        "site": {
            "url": workspace.get("website_url"),
            "niche": niche_profile.get("primary_niche") or "generic",
            "confidence": niche_profile.get("confidence"),
            "pages_analyzed": analysis_page_count if analysis_page_count is not None else len(pages),
            "competitors_analyzed": len(workspace_payload.get("competitor_snapshots") or []),
            "low_content_warning": low_content_warning,
            "strategy_profile": strategy_profile if isinstance(strategy_profile, dict) else {},
        },
        "recommendations": {
            "total": recommendation_summary.get("total", len(recommendations)),
            "create": recommendation_summary.get("create", _count_action(recommendations, "create")),
            "refresh": recommendation_summary.get("refresh", _count_action(recommendations, "refresh")),
            "monitor": recommendation_summary.get("monitor", _count_action(recommendations, "monitor")),
            "ignore": recommendation_summary.get("ignore", _count_action(recommendations, "ignore")),
            "items": recommendations,
            "top": recommendations[:10],
            "entity_relevance": entity_relevance,
        },
        "schedule": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "recommendation_source": item.get("origin_type") or item.get("source_type") or item.get("policy") or "recommendation",
                "suggested_publish_date": item.get("scheduled_for"),
                "content_type": item.get("content_role"),
                "priority": item.get("priority") or item.get("state"),
                "state": item.get("state"),
                "generated_job_id": item.get("generated_job_id"),
            }
            for item in calendar_items[:30]
        ],
        "warnings": warnings,
        "publishing_safety": publishing_safety_state(settings),
        "url_discovery": url_discovery or {},
        "competitor_discovery": competitor_discovery,
        "competitor_intelligence": competitor_seo_intelligence,
    }


def summarize_steps_from_payloads(
    state: AnalyzeFlowState,
    *,
    analysis_payload: dict[str, Any],
    workspace_payload: dict[str, Any],
    settings: Settings,
) -> None:
    low_content_warning = analysis_payload.get("low_content_warning")
    analysis_block = analysis_payload.get("analysis") or {}
    artifacts = analysis_block.get("artifacts") or []
    url_discovery = _artifact_content(artifacts, "url_discovery")
    competitor_seo_intelligence = _artifact_content(artifacts, "competitor_seo_intelligence") or {}
    website_discovery = (url_discovery or {}).get("website") or {}
    entity_relevance = ((workspace_payload.get("opportunity_intelligence") or {}).get("summary") or {}).get("entity_relevance") or {}
    competitor_discovery = analysis_payload.get("competitor_discovery") or {}
    mark_step(
        state,
        "sitemap_discovery",
        _terminal_status(state, "sitemap_discovery", "warning" if _sitemap_warning(website_discovery) else "succeeded"),
        _sitemap_message(website_discovery),
        warnings=_sitemap_warnings(website_discovery),
        progress_current=int(website_discovery.get("sitemap_urls_selected") or 0),
        progress_total=int(website_discovery.get("sitemap_urls_discovered") or 0),
        progress_label=_sitemap_progress_label(website_discovery),
        details=_sitemap_details(website_discovery),
        timing_note=_timing_note_if_inferred(state, "sitemap_discovery"),
    )
    page_count = int(analysis_payload.get("analysis_page_count") or 0)
    mark_step(
        state,
        "website_crawl",
        _terminal_status(state, "website_crawl", "warning" if low_content_warning else "succeeded"),
        _website_crawl_message(website_discovery, page_count),
        warnings=[low_content_warning] if low_content_warning else [],
        progress_current=int(website_discovery.get("urls_crawled") or page_count),
        progress_total=int(website_discovery.get("sitemap_urls_selected") or page_count),
        progress_label=_website_crawl_progress_label(website_discovery, page_count),
        details={
            "urls_discovered": int(website_discovery.get("sitemap_urls_discovered") or 0),
            "useful_url_count": int(website_discovery.get("useful_url_count") or 0),
            "urls_selected": int(website_discovery.get("sitemap_urls_selected") or 0),
            "urls_crawled": int(website_discovery.get("urls_crawled") or page_count),
            "urls_skipped_by_cap": int(website_discovery.get("urls_skipped_by_cap") or 0),
            "skipped_by_cap_examples": website_discovery.get("skipped_by_cap_examples") or [],
            "crawl_budget": website_discovery.get("crawl_budget") or {},
            "crawl_timing": website_discovery.get("crawl_timing") or {},
        },
        timing_note=_timing_note_if_inferred(state, "website_crawl"),
    )
    mark_step(
        state,
        "website_analysis",
        _terminal_status(state, "website_analysis", "succeeded"),
        "Website analysis completed.",
        timing_note=_timing_note_if_inferred(state, "website_analysis"),
    )
    mark_step(
        state,
        "niche_intelligence",
        _terminal_status(state, "niche_intelligence", "succeeded"),
        "Niche profile refreshed.",
        timing_note=_timing_note_if_inferred(state, "niche_intelligence"),
    )
    _summarize_recommendations_tail(state, analysis_payload, workspace_payload, settings)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_seconds(started_at: str | None, completed_at: str | None) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        return None
    return round(max(0.0, (completed - started).total_seconds()), 3)


def _artifact_content(artifacts: list[dict[str, Any]], artifact_type: str) -> dict[str, Any] | None:
    for artifact in reversed(artifacts):
        if artifact.get("artifact_type") == artifact_type and isinstance(artifact.get("content_json"), dict):
            return artifact["content_json"]
    return None


def _count_action(recommendations: list[dict[str, Any]], action: str) -> int:
    return sum(1 for item in recommendations if item.get("action") == action)


def _sitemap_warning(discovery: dict[str, Any]) -> bool:
    return bool(discovery.get("robots_txt_checked")) and int(discovery.get("sitemap_urls_selected") or 0) == 0


def _sitemap_warnings(discovery: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if _sitemap_warning(discovery):
        warnings.append("No usable sitemap URLs were selected; internal crawl fallback was used.")
    skipped = discovery.get("skipped_url_counts_by_reason") if isinstance(discovery.get("skipped_url_counts_by_reason"), dict) else {}
    if skipped.get("malformed_sitemap"):
        warnings.append("One or more sitemap files were malformed.")
    if skipped.get("sitemap_fetch_failed"):
        warnings.append("One or more sitemap files could not be fetched.")
    return warnings


def _sitemap_message(discovery: dict[str, Any]) -> str:
    useful = int(discovery.get("useful_url_count") or discovery.get("sitemap_urls_selected") or 0)
    selected = int(discovery.get("sitemap_urls_selected") or 0)
    discovered = int(discovery.get("sitemap_urls_discovered") or 0)
    if useful and useful == selected:
        return f"Found {useful} useful URL(s) from {discovered} discovered."
    if useful:
        return f"Selected {selected} of {useful} useful URL(s) ({discovered} discovered)."
    if selected:
        return f"Selected {selected} sitemap URLs from {discovered} discovered."
    return "Sitemap discovery produced no selected URLs; fallback crawl remains available."


def _sitemap_progress_label(discovery: dict[str, Any]) -> str:
    useful = int(discovery.get("useful_url_count") or 0)
    selected = int(discovery.get("sitemap_urls_selected") or 0)
    discovered = int(discovery.get("sitemap_urls_discovered") or 0)
    if useful and useful == selected:
        return f"Found {useful} useful URLs"
    if useful:
        return f"Selected {selected} of {useful} useful URLs"
    if selected or discovered:
        return f"Selected {selected} URLs from {discovered} discovered."
    if discovery.get("robots_txt_checked"):
        return "Checked robots.txt."
    return ""


def _website_crawl_message(discovery: dict[str, Any], pages_analyzed: int) -> str:
    selected = int(discovery.get("sitemap_urls_selected") or discovery.get("urls_selected") or pages_analyzed)
    crawled = int(discovery.get("urls_crawled") or pages_analyzed)
    skipped = int(discovery.get("urls_skipped_by_cap") or 0)
    if skipped > 0:
        return f"Scraped {crawled} of {selected} selected pages. {skipped} skipped due to page limit."
    if crawled and selected:
        return f"Scraped {crawled} of {selected} pages."
    return f"Analyzed {pages_analyzed} pages."


def _website_crawl_progress_label(discovery: dict[str, Any], pages_analyzed: int) -> str:
    selected = int(discovery.get("sitemap_urls_selected") or discovery.get("urls_selected") or pages_analyzed)
    crawled = int(discovery.get("urls_crawled") or pages_analyzed)
    skipped = int(discovery.get("urls_skipped_by_cap") or 0)
    if skipped > 0:
        return f"Scraped {crawled} of {selected} ({skipped} skipped)"
    if crawled and selected:
        return f"Scraped {crawled} of {selected} pages"
    return f"Scraped {pages_analyzed} pages"


def _sitemap_details(discovery: dict[str, Any]) -> dict[str, Any]:
    return {
        "robots_txt_checked": bool(discovery.get("robots_txt_checked")),
        "sitemap_urls_found": int(discovery.get("sitemap_urls_found") or 0),
        "sitemap_files_parsed": int(discovery.get("sitemap_files_parsed") or 0),
        "sitemap_urls_discovered": int(discovery.get("sitemap_urls_discovered") or 0),
        "sitemap_urls_selected": int(discovery.get("sitemap_urls_selected") or 0),
        "useful_url_count": int(discovery.get("useful_url_count") or 0),
        "urls_crawled": int(discovery.get("urls_crawled") or 0),
        "urls_skipped_by_cap": int(discovery.get("urls_skipped_by_cap") or 0),
        "skipped_by_cap_examples": discovery.get("skipped_by_cap_examples") or [],
        "crawl_budget": discovery.get("crawl_budget") or {},
        "crawl_timing": discovery.get("crawl_timing") or {},
        "crawl_fallback_used": bool(discovery.get("crawl_fallback_used")),
        "skipped_url_counts_by_reason": discovery.get("skipped_url_counts_by_reason") or {},
    }


def _entity_relevance_message(entity_relevance: dict[str, Any], settings: Settings) -> str:
    if not getattr(settings, "entity_relevance_scoring_enabled", False):
        return "Entity relevance scoring disabled."
    if not entity_relevance:
        return "Entity relevance scoring was enabled, but no metrics were reported."
    fallback_count = int(entity_relevance.get("fallback_count") or 0)
    if fallback_count:
        return "Entity relevance scoring failed open; deterministic fallback used."
    requested = int(entity_relevance.get("entities_requested") or 0)
    scored = int(entity_relevance.get("entities_scored") or 0)
    filtered = int(entity_relevance.get("filtered_by_relevance") or 0)
    down_ranked = int(entity_relevance.get("down_ranked_by_relevance") or 0)
    return f"Scored {scored or requested} entities. Filtered {filtered}, down-ranked {down_ranked}."


def _entity_relevance_warnings(entity_relevance: dict[str, Any]) -> list[str]:
    fallback_count = int(entity_relevance.get("fallback_count") or 0)
    if not fallback_count:
        return []
    reason = entity_relevance.get("fail_open_reason") or "unknown"
    return [f"Phase 2A fallback_count={fallback_count}; reason={reason}."]


def _entity_relevance_details(entity_relevance: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "entities_requested",
        "entities_scored",
        "model_calls",
        "cache_hits",
        "cache_misses",
        "filtered_by_relevance",
        "down_ranked_by_relevance",
        "fallback_count",
        "fail_open_reason",
    ]
    return {key: entity_relevance.get(key) for key in keys if key in entity_relevance}


def _entity_relevance_status(entity_relevance: dict[str, Any], settings: Settings) -> dict[str, Any]:
    details = _entity_relevance_details(entity_relevance)
    warnings = _entity_relevance_warnings(entity_relevance)
    if not getattr(settings, "entity_relevance_scoring_enabled", False):
        return {
            "status": "skipped",
            "message": "Entity relevance scoring disabled.",
            "warnings": [],
            "details": details,
        }
    if not _has_entity_relevance_metrics(entity_relevance):
        return {
            "status": "warning",
            "message": "Entity relevance scoring was enabled, but no metrics were reported.",
            "warnings": ["Entity relevance scoring was enabled, but no metrics were reported."],
            "details": details,
        }
    if int(entity_relevance.get("fallback_count") or 0):
        reason = entity_relevance.get("fail_open_reason") or "unknown"
        return {
            "status": "warning",
            "message": "Entity relevance scoring failed open; deterministic fallback used.",
            "warnings": [f"Entity relevance scoring fail-open reason: {reason}."],
            "details": details,
        }
    return {
        "status": "succeeded",
        "message": _entity_relevance_message(entity_relevance, settings),
        "warnings": warnings,
        "details": details,
    }


def _competitor_discovery_status(discovery: dict[str, Any]) -> str:
    source = str(discovery.get("source") or "none")
    warning = str(discovery.get("warning") or "").strip()
    selected = int(discovery.get("selected_count") or discovery.get("competitors_selected") or 0)
    if source in {"provided", "discovered", "provided+discovered"} and selected:
        return "succeeded"
    if warning and not selected:
        return "warning"
    if source == "provided" and selected:
        return "succeeded"
    if warning:
        return "warning"
    return "skipped"


def _competitor_discovery_message(discovery: dict[str, Any]) -> str:
    source = str(discovery.get("source") or "none")
    provided_count = int(discovery.get("provided_count") or 0)
    discovered_count = int(discovery.get("discovered_count") or 0)
    selected_count = int(discovery.get("selected_count") or discovery.get("competitors_selected") or 0)
    source_lines = _competitor_discovery_source_lines(discovery)
    if selected_count and source_lines:
        return f"Selected {selected_count} competitor(s).\nSources:\n" + "\n".join(f"- {line}" for line in source_lines)
    if source == "provided+discovered":
        return f"Provided competitors: {provided_count}. Discovered competitors: {discovered_count}. Total analyzed: {selected_count}."
    if source == "provided" and selected_count:
        return f"Provided competitors: {provided_count}. Total analyzed: {selected_count}."
    if source == "discovered" and selected_count:
        return f"Discovered competitors: {discovered_count}. Total analyzed: {selected_count}."
    if source == "provided" and not selected_count:
        return str(discovery.get("reason_message") or discovery.get("warning") or "No valid provided competitors after filtering.")
    if not selected_count:
        return "No competitors could be identified automatically."
    return str(discovery.get("warning") or "No competitors could be identified automatically.")


def _snapshots_for_analysis_run(
    competitor_snapshots: list[dict[str, Any]],
    *,
    analysis_job_id: str,
) -> list[dict[str, Any]]:
    if not competitor_snapshots:
        return []
    if not analysis_job_id:
        return competitor_snapshots
    filtered = [
        item
        for item in competitor_snapshots
        if str(item.get("analysis_job_id") or "") in {"", analysis_job_id}
    ]
    return filtered or competitor_snapshots


def _competitor_analysis_terminal_state(
    competitor_discovery: dict[str, Any],
    competitor_seo_intelligence: dict[str, Any],
    competitor_snapshots: list[dict[str, Any]],
) -> tuple[str, str]:
    selected = int(competitor_discovery.get("selected_count") or competitor_discovery.get("competitors_selected") or 0)
    pages = competitor_seo_intelligence.get("pages_analyzed") if isinstance(competitor_seo_intelligence.get("pages_analyzed"), dict) else {}
    pages_scraped = int(pages.get("total_competitor_pages") or 0)
    gaps = competitor_seo_intelligence.get("coverage_gaps") if isinstance(competitor_seo_intelligence.get("coverage_gaps"), list) else []
    benchmark = competitor_seo_intelligence.get("benchmark_metrics") if isinstance(competitor_seo_intelligence.get("benchmark_metrics"), dict) else {}
    snapshot_domains = {
        str(item.get("competitor_url") or item.get("url") or "").strip()
        for item in competitor_snapshots
        if str(item.get("competitor_url") or item.get("url") or "").strip()
    }
    analyzed_competitors = max(selected, len(snapshot_domains))
    has_intel = pages_scraped > 0 or bool(gaps) or bool(benchmark)
    if selected and (pages_scraped > 0 or snapshot_domains or has_intel):
        if pages_scraped:
            message = f"Analyzed {analyzed_competitors} competitor(s). Scraped {pages_scraped} page(s)."
        else:
            message = f"Analyzed {analyzed_competitors} competitor(s)."
        if gaps:
            message += f" Coverage gaps detected: {len(gaps)}."
        return "succeeded", message
    if selected:
        return "warning", "Competitors were selected but competitor analysis failed."
    return "skipped", "No competitors available."


def _competitor_discovery_warnings(discovery: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    source = str(discovery.get("source") or "none")
    selected = int(discovery.get("selected_count") or discovery.get("competitors_selected") or 0)
    web_search_summary = str(discovery.get("web_search_summary") or "").strip()
    if web_search_summary and not selected:
        warnings.append(web_search_summary)
    if not selected:
        reason_message = str(discovery.get("reason_message") or "").strip()
        if reason_message:
            warnings.append(f"Reason: {reason_message}")
        warnings.extend(_competitor_discovery_source_warnings(discovery))
        candidates_found = int(discovery.get("candidates_found") or 0)
        candidates_rejected = int(discovery.get("candidates_rejected") or 0)
        if candidates_found:
            warnings.append(f"Candidates found: {candidates_found}")
        if candidates_rejected:
            warnings.append(f"Candidates rejected: {candidates_rejected}")
    warning = str(discovery.get("warning") or "").strip()
    if warning and warning not in warnings and not any(warning in item for item in warnings):
        warnings.append(warning)
    if source == "none" and not selected and not warnings:
        warnings.append("No competitors could be identified automatically.")
    return warnings


def _competitor_discovery_source_lines(discovery: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in discovery.get("source_summary") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("source") or "source")
        selected = int(item.get("selected") or 0)
        candidates = int(item.get("candidates") or 0)
        note = str(item.get("note") or "").strip()
        if note:
            lines.append(f"{label}: {note}")
        elif selected:
            lines.append(f"{label}: {selected}")
        elif candidates:
            lines.append(f"{label}: {candidates} candidate(s)")
        else:
            lines.append(f"{label}: 0")
    if lines:
        return lines
    labels = {
        "comparison_pages": "comparison pages",
        "outbound_domains": "outbound domains",
        "niche_peers": "niche peers",
        "workspace_history": "workspace history",
        "competitor_snapshots": "competitor snapshots",
        "web_search": "web search",
        "provided": "provided competitors",
    }
    for item in discovery.get("sources_checked") or []:
        lines.append(f"{labels.get(str(item), str(item))}: checked")
    for item in discovery.get("sources_skipped") or []:
        if not isinstance(item, dict):
            continue
        source = labels.get(str(item.get("source") or ""), str(item.get("source") or "source"))
        reason = str(item.get("reason") or "skipped")
        detail = str(item.get("detail") or "").strip()
        if reason == "no_results":
            lines.append(f"{source}: 0 usable results")
        elif detail:
            lines.append(f"{source}: {detail}")
        else:
            lines.append(f"{source}: {reason}")
    return lines


def _competitor_discovery_source_warnings(discovery: dict[str, Any]) -> list[str]:
    labels = {
        "comparison_pages": "Comparison pages",
        "outbound_domains": "Outbound domains",
        "niche_peers": "Historical niche peers",
        "workspace_history": "History",
        "competitor_snapshots": "Competitor snapshots",
        "web_search": "Web search",
    }
    checked = [
        labels.get(str(item), str(item))
        for item in (discovery.get("sources_checked") or [])
        if str(item).strip()
    ]
    skipped: list[str] = []
    for item in discovery.get("sources_skipped") or []:
        if not isinstance(item, dict):
            continue
        source = labels.get(str(item.get("source") or ""), str(item.get("source") or "source"))
        reason = str(item.get("reason") or "skipped")
        detail = str(item.get("detail") or "").strip()
        if reason == "disabled":
            skipped.append(f"{source} (disabled{': ' + detail if detail else ''})")
        elif reason == "no_results":
            skipped.append(f"{source} (no results)")
        else:
            skipped.append(f"{source} ({reason})")
    lines: list[str] = []
    if checked:
        lines.append("Sources checked: " + ", ".join(checked))
    if skipped:
        lines.append("Sources skipped: " + ", ".join(skipped))
    return lines


def _competitor_analysis_details(competitor_seo_intelligence: dict[str, Any]) -> dict[str, Any]:
    pages = competitor_seo_intelligence.get("pages_analyzed") if isinstance(competitor_seo_intelligence.get("pages_analyzed"), dict) else {}
    gaps = competitor_seo_intelligence.get("coverage_gaps") if isinstance(competitor_seo_intelligence.get("coverage_gaps"), list) else []
    benchmark = competitor_seo_intelligence.get("benchmark_metrics") if isinstance(competitor_seo_intelligence.get("benchmark_metrics"), dict) else {}
    return {
        "competitors_discovered": competitor_seo_intelligence.get("competitors_discovered") or [],
        "competitor_pages_analyzed": int(pages.get("total_competitor_pages") or 0),
        "coverage_gap_count": len(gaps),
        "top_gap_topics": [str(item.get("topic") or "") for item in gaps[:5] if str(item.get("topic") or "").strip()],
        "benchmark_delta": benchmark.get("delta_competitor_minus_workspace") if isinstance(benchmark, dict) else {},
    }


def _competitor_analysis_warnings(competitor_seo_intelligence: dict[str, Any], status: str) -> list[str]:
    if status != "succeeded":
        return []
    gaps = competitor_seo_intelligence.get("coverage_gaps") if isinstance(competitor_seo_intelligence.get("coverage_gaps"), list) else []
    if not gaps:
        return []
    return [f"Competitor coverage gaps detected: {len(gaps)} topic(s)."]


def _has_entity_relevance_metrics(entity_relevance: dict[str, Any]) -> bool:
    metric_keys = {
        "entities_requested",
        "entities_scored",
        "model_calls",
        "cache_hits",
        "cache_misses",
        "filtered_by_relevance",
        "down_ranked_by_relevance",
        "fallback_count",
    }
    for key in metric_keys:
        if key in entity_relevance and entity_relevance.get(key) is not None:
            return True
    return False


def _terminal_status(state: AnalyzeFlowState, key: str, desired: str) -> str:
    current = state.step(key).status
    if desired in {"failed", "warning"}:
        return desired
    if current in {"failed", "warning"}:
        return current
    return desired


def _timing_note_if_inferred(state: AnalyzeFlowState, key: str) -> str | None:
    step = state.step(key)
    if step.started_at is None and step.completed_at is None:
        return "included in analysis phase"
    return step.timing_note


def _flow_warnings(
    *,
    low_content_warning: str | None,
    url_discovery: dict[str, Any] | None,
    entity_relevance: dict[str, Any],
    competitor_discovery: dict[str, Any],
    competitor_seo_intelligence: dict[str, Any],
    settings: Settings,
    competitors: list[Any],
) -> list[str]:
    warnings: list[str] = []
    if low_content_warning:
        warnings.append(low_content_warning)
    competitor_selected = int(competitor_discovery.get("selected_count") or competitor_discovery.get("competitors_selected") or 0)
    if not competitors and not competitor_selected:
        discovery_warning = str(competitor_discovery.get("warning") or "").strip()
        if discovery_warning:
            warnings.append(discovery_warning)
        elif str(competitor_discovery.get("source") or "none") == "none":
            warnings.append("No competitors could be identified automatically.")
    if url_discovery:
        warnings.extend(_sitemap_warnings((url_discovery.get("website") or {})))
    warnings.extend(_entity_summary_warnings(entity_relevance, settings))
    warnings.extend(_competitor_discovery_warnings(competitor_discovery))
    gap_count = len(competitor_seo_intelligence.get("coverage_gaps") or []) if isinstance(competitor_seo_intelligence, dict) else 0
    if gap_count:
        warnings.append(f"Competitor intelligence identified {gap_count} coverage gap topic(s).")
    safety = publishing_safety_state(settings)
    if not safety["wordpress_configured"]:
        warnings.append("WordPress upload unavailable: WordPress is not configured.")
    if not safety["live_publish_available"]:
        warnings.append("Live publishing is disabled by safety gates.")
    return list(dict.fromkeys(warnings))


def _entity_summary_warnings(entity_relevance: dict[str, Any], settings: Settings) -> list[str]:
    status = _entity_relevance_status(entity_relevance, settings)
    return list(status.get("warnings") or [])
