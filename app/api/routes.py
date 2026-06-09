import logging
import asyncio
from html import escape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field, HttpUrl

from app.analyze_flow import (
    AnalyzeFlowState,
    extract_flow_summary,
    finish_overall_status,
    mark_flow_cancelled,
    mark_step,
    merge_flow_summary,
    new_analyze_flow_state,
    new_analyze_flow_state_from_parent,
    publishing_safety_state,
    skip_unstarted_flow_steps,
    summarize_steps_from_payloads,
    update_step_progress,
)
from app.analyze_flow_persistence import state_from_persisted_dict, state_to_persisted_dict
from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.autopilot import AutopilotService
from app.config import Settings
from app.connectors.wordpress import ConnectorError, TrendplotConnectorContract, TrendplotWordPressConnectorClient
from app.connectors.wordpress_schemas import ConnectorEventRequest, ConnectorMediaFromUrlRequest
from app.rendering.youtube_embed import render_local_youtube_iframes
from app.repositories import Repositories
from app.recommendations_export import export_filename, normalize_export_actions, recommendations_to_csv
from app.recommendations.explainability import build_recommendation_audit_report
from app.services.jobs import GENERATION_ACTIVE_STATUSES, GenerateArticleCommand, JobService
from app.trendplot_ui import TRENDPLOT_WORKSPACE_HTML
from app.website_analysis import AnalyzeWebsiteCommand, WebsiteAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter()


def _legacy_pipeline_removed() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy analyze pipeline endpoint removed (phase 2 cleanup).",
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return TRENDPLOT_WORKSPACE_HTML


@router.get("/app", response_class=HTMLResponse)
async def trendplot_workspace() -> str:
    return TRENDPLOT_WORKSPACE_HTML


@router.get("/app/analyze", response_class=HTMLResponse)
async def analyze_website_app() -> str:
    return ANALYZE_WEBSITE_HTML


@router.get("/app/analyze/safety")
async def analyze_website_safety(request: Request) -> dict[str, Any]:
    return publishing_safety_state(request.app.state.settings)


@router.get("/developer", response_class=HTMLResponse)
async def developer_dashboard() -> str:
    return _moved_operator_ui_page("/developer")


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard() -> str:
    return _moved_operator_ui_page("/admin")


def _moved_operator_ui_page(path: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trendplot UI Moved</title>
  <style>
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif; background: #0f172a; color: #e5e7eb; }}
    main {{ width: min(720px, 92vw); margin: 12vh auto; padding: 28px; border: 1px solid #334155; border-radius: 18px; background: #111827; }}
    a {{ color: #38bdf8; font-weight: 800; }}
    .muted {{ color: #9ca3af; }}
  </style>
</head>
<body>
  <main>
    <h1>Developer UI moved</h1>
    <p>The legacy <code>{escape(path)}</code> dashboard is deprecated. Trendplot now uses the root operator UI.</p>
    <p><a href="/">Open Trendplot Operator UI</a></p>
    <p class="muted">Backend developer APIs remain available, including <code>/developer/demand/*</code>.</p>
  </main>
</body>
</html>"""


class GenerateArticleRequest(BaseModel):
    title: str
    target_keyword: str
    product_name: str
    product_url: HttpUrl
    publish_policy: Literal[
        "manual_review",
        "draft_after_review",
        "live_after_review",
        "auto_draft",
        "auto_live",
    ] | None = None
    category_id: int | None = None
    category_slug: str | None = None
    category_name: str | None = None
    wordpress_template: str | None = None
    wordpress_category_id: int | None = None
    wordpress_category_slug: str | None = None
    wordpress_category_name: str | None = None
    wordpress_tags: list[str] = Field(default_factory=list)
    featured_image_id: int | None = None
    featured_image_url: str | None = None
    featured_image_alt: str | None = None
    unattended_mode: bool = False
    workspace_id: str | None = None
    content_plan_item_id: str | None = None
    origin_type: str | None = None
    opportunity_context: dict[str, Any] | None = None


class ManualRecommendationCreateRequest(BaseModel):
    raw_headline: str
    raw_notes: str = ""
    content_type: str | None = None
    target_audience: str | None = None
    selected_products: list[str] = Field(default_factory=list)
    created_by: str | None = None


class ManualRecommendationQueueRequest(BaseModel):
    allow_duplicates: bool = False


class WordPressConnectorEnvironmentRequest(BaseModel):
    wordpress_base_url: str | None = None
    trendplot_site_id: str | None = None
    trendplot_shared_secret: str | None = None


class WordPressConnectorSettingsRequest(BaseModel):
    connector_enabled: bool | None = None
    active_environment: str | None = None
    environment: str | None = None
    wordpress_base_url: str | None = None
    trendplot_site_id: str | None = None
    trendplot_shared_secret: str | None = None
    environments: dict[str, WordPressConnectorEnvironmentRequest] | None = None


class WordPressConnectorTestRequest(BaseModel):
    environment: str | None = None


class WordPressConnectorDraftRequest(BaseModel):
    force: bool = False


class JobSeoSaveRequest(BaseModel):
    seo_title: str | None = None
    seo_description: str | None = None
    seo_focus_keyword: str | None = None
    seo_canonical_url: str | None = None
    seo_robots: str | None = None
    seo_schema_type: str | None = None


class StartGenerationResponse(BaseModel):
    job_id: str
    status: str


class GenerateArticleResponse(BaseModel):
    job_id: str
    status: str
    human_review_required: bool
    publish_policy: str | None = None
    wordpress_post: dict[str, Any] | None
    featured_image: dict[str, Any] | None
    youtube_video: dict[str, Any] | None
    x_post: str | None
    threads_post: str | None
    quality_check: dict[str, Any] | None = None
    initial_quality_check: dict[str, Any] | None = None
    final_quality_check: dict[str, Any] | None = None
    sanity_check: dict[str, Any] | None = None
    sanity_rewrite_summary: dict[str, Any] | None = None
    repair_attempted: bool = False
    repair_pass_count: int = 0
    repair_summary: dict[str, Any] | None = None
    section_expansion_attempted: bool = False
    section_expansion_summary: dict[str, Any] | None = None
    ai_pattern_report: dict[str, Any] | None = None
    humanization_summary: dict[str, Any] | None = None
    rewritten_sections: dict[str, Any] | None = None
    rewrite_attempts: dict[str, Any] | None = None
    rewrite_strength_used: dict[str, Any] | None = None
    humanization_quality_report: dict[str, Any] | None = None
    repeated_phrases_removed: dict[str, Any] | None = None
    sections_rewritten: dict[str, Any] | None = None
    reverted_sections: dict[str, Any] | None = None
    post_humanization_redundancy_review: dict[str, Any] | None = None
    narrative_pattern_report: dict[str, Any] | None = None
    narrative_editor_summary: dict[str, Any] | None = None
    narrative_editor_edits: dict[str, Any] | None = None
    post_narrative_redundancy_review: dict[str, Any] | None = None
    model_pipeline: list[dict[str, Any]] = Field(default_factory=list)
    backlink_plan: list[dict[str, Any]] = Field(default_factory=list)
    suggested_external_references: list[dict[str, Any]] = Field(default_factory=list)
    structured_article: dict[str, Any] | None = None
    rendered_html: str | None = None
    renderer_logs: list[str] = Field(default_factory=list)
    wordpress_presentation_metadata: dict[str, Any] | None = None
    wordpress_tag_suggestions: list[str] = Field(default_factory=list)
    publish_decision_report: dict[str, Any] | None = None
    job_run_metrics: dict[str, Any] | None = None
    stage_timing_summary: dict[str, Any] | None = None
    model_cost_summary: dict[str, Any] | None = None
    image_placement_plan: dict[str, Any] | None = None
    image_generation_result: dict[str, Any] | None = None
    generated_images: dict[str, Any] | None = None
    approved_images: dict[str, Any] | None = None
    rejected_images: dict[str, Any] | None = None
    image_rendering_summary: dict[str, Any] | None = None


class JobSummary(BaseModel):
    id: str
    status: str
    request_input: dict[str, Any]
    retry_count: int
    last_error: str | None
    last_attempt_at: str | None
    human_review_required: bool
    created_at: str
    updated_at: str
    wordpress_post_id: str | None = None
    wordpress_edit_url: str | None = None
    wordpress_public_url: str | None = None
    wordpress_status: str | None = None
    wordpress_draft_created_at: str | None = None
    wordpress_draft_updated_at: str | None = None
    last_wordpress_sync_at: str | None = None
    wordpress_publish_error: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_focus_keyword: str | None = None
    seo_canonical_url: str | None = None
    seo_robots: str | None = None
    seo_schema_type: str | None = None
    seo_generated_at: str | None = None
    seo_synced_at: str | None = None
    seo_last_error: str | None = None
    rank_math_score: float | None = None


class AnalyzeWebsiteRequest(BaseModel):
    website_url: HttpUrl
    competitor_urls: list[HttpUrl] = Field(default_factory=list)
    max_pages_per_site: int = 30
    vertical: str | None = None
    vertical_mode: Literal["auto", "generic", "profile", "custom_context"] | None = None
    vertical_profile_id: str | None = None
    user_context: str | None = None


class AutopilotWorkspaceCreateRequest(BaseModel):
    website_url: HttpUrl
    name: str | None = None
    competitor_urls: list[HttpUrl] = Field(default_factory=list)
    mode: Literal["manual_review", "auto_draft", "auto_publish"] = "manual_review"
    cadence: Literal["daily", "weekly", "custom"] = "weekly"
    user_context: str = ""


class AutopilotAnalyzeRequest(BaseModel):
    max_pages_per_site: int = 30


class AnalyzeWebsiteFlowRequest(BaseModel):
    website_url: HttpUrl
    name: str | None = None
    competitor_urls: list[HttpUrl] = Field(default_factory=list)
    target_market: str | None = None
    publishing_mode: Literal["manual_review", "create_wordpress_draft", "live_publish"] = "manual_review"
    max_pages_per_site: int = 30
    notes: str | None = None


class AnalyzeFlowRerunRequest(BaseModel):
    rerun_type: Literal[
        "competitor_discovery",
        "competitor_analysis",
        "recommendations",
        "schedule",
        "full",
    ]


class AutopilotPlanRequest(BaseModel):
    horizon_days: int = 30


class DemandFetchRequest(BaseModel):
    date_start: str | None = None
    date_end: str | None = None
    limit: int | None = None


class AutopilotEnableRequest(BaseModel):
    mode: Literal["manual_review", "auto_draft", "auto_publish"] = "manual_review"


class CalendarItemPatch(BaseModel):
    state: Literal[
        "planned",
        "queued_for_generation",
        "generating",
        "draft_ready",
        "needs_review",
        "approved",
        "scheduled",
        "published",
        "skipped",
        "failed",
        "retired",
    ] | None = None
    scheduled_for: str | None = None
    title: str | None = None
    target_keyword: str | None = None
    notes: str | None = None


class RunDueItemsRequest(BaseModel):
    limit: int = 1


class WebsiteSuggestion(BaseModel):
    title: str
    target_keyword: str
    product_name: str
    product_url: str
    reason: str
    confidence: str | None = None


class AnalyzeWebsiteResponse(BaseModel):
    website: dict[str, Any]
    competitors: list[dict[str, Any]]
    summary: str
    suggestions: list[WebsiteSuggestion]
    audiences: list[dict[str, Any]] = Field(default_factory=list)
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    authority_graph: dict[str, Any] = Field(default_factory=dict)
    vertical_intelligence: dict[str, Any] = Field(default_factory=dict)
    external_research: dict[str, Any] = Field(default_factory=dict)


class AnalysisJobSummary(BaseModel):
    id: str
    website_url: str
    competitor_urls: list[str]
    status: str
    max_pages_per_site: int
    error_message: str | None = None
    summary: str | None = None
    prompt: str | None = None
    raw_response: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class AnalysisSuggestionPatch(BaseModel):
    title: str | None = None
    target_keyword: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    reason: str | None = None
    confidence: str | None = None
    status: Literal["suggested", "approved", "rejected", "generated"] | None = None


class OpportunityPatch(BaseModel):
    title: str | None = None
    target_keyword: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    status: Literal["suggested", "approved", "rejected", "generated", "planned", "bookmarked"] | None = None


class ApiKeyCheck(BaseModel):
    name: str
    configured: bool
    status: str
    masked_value: str | None = None
    detail: str


class ApiKeyCheckResponse(BaseModel):
    checks: list[ApiKeyCheck]
    note: str


class PublishJobRequest(BaseModel):
    confirm_live_publish: bool = False
    category_id: int | None = None
    wordpress_template: str | None = None
    wordpress_category_id: int | None = None
    wordpress_category_slug: str | None = None
    wordpress_category_name: str | None = None
    wordpress_tags: list[str] = Field(default_factory=list)
    featured_image_id: int | None = None
    featured_image_url: str | None = None
    featured_image_alt: str | None = None


class RunSanityCheckRequest(BaseModel):
    apply_rewrite: bool = True


@router.post(
    "/generate-article",
    response_model=GenerateArticleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_article(
    payload: GenerateArticleRequest,
    request: Request,
) -> dict[str, Any]:
    job_service: JobService = request.app.state.job_service

    try:
        return await job_service.generate_article(
            GenerateArticleCommand(
                title=payload.title,
                target_keyword=payload.target_keyword,
                product_name=payload.product_name,
                product_url=str(payload.product_url),
                publish_policy=payload.publish_policy,
                category_id=payload.category_id,
                category_slug=payload.category_slug,
                category_name=payload.category_name,
                wordpress_template=payload.wordpress_template,
                wordpress_category_id=payload.wordpress_category_id,
                wordpress_category_slug=payload.wordpress_category_slug,
                wordpress_category_name=payload.wordpress_category_name,
                wordpress_tags=payload.wordpress_tags,
                featured_image_id=payload.featured_image_id,
                featured_image_url=payload.featured_image_url,
                featured_image_alt=payload.featured_image_alt,
                unattended_mode=payload.unattended_mode,
                workspace_id=payload.workspace_id,
                content_plan_item_id=payload.content_plan_item_id,
                origin_type=payload.origin_type,
                opportunity_context=payload.opportunity_context,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("External API returned an error.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="External API request failed.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("External API request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="External API request failed.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected article generation failure.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Article generation failed.",
        ) from exc


@router.post(
    "/generate-article/async",
    response_model=StartGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_article_async(
    payload: GenerateArticleRequest,
    request: Request,
) -> dict[str, str]:
    job_service: JobService = request.app.state.job_service
    command = GenerateArticleCommand(
        title=payload.title,
        target_keyword=payload.target_keyword,
        product_name=payload.product_name,
        product_url=str(payload.product_url),
        publish_policy=payload.publish_policy,
        category_id=payload.category_id,
        category_slug=payload.category_slug,
        category_name=payload.category_name,
        wordpress_template=payload.wordpress_template,
        wordpress_category_id=payload.wordpress_category_id,
        wordpress_category_slug=payload.wordpress_category_slug,
        wordpress_category_name=payload.wordpress_category_name,
        wordpress_tags=payload.wordpress_tags,
        featured_image_id=payload.featured_image_id,
        featured_image_url=payload.featured_image_url,
        featured_image_alt=payload.featured_image_alt,
        unattended_mode=payload.unattended_mode,
        workspace_id=payload.workspace_id,
        content_plan_item_id=payload.content_plan_item_id,
        origin_type=payload.origin_type,
        opportunity_context=payload.opportunity_context,
    )
    try:
        job_id, policy = await job_service.prepare_generation_job(command)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    _start_analyze_flow_task(
        request.app,
        job_id,
        job_service.run_generation_job_task(job_id, command, policy),
    )
    return {"job_id": job_id, "status": "queued"}


@router.get("/autopilot/workspaces")
async def list_autopilot_workspaces(request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    return {"workspaces": await autopilot.list_workspaces()}


@router.post("/autopilot/workspaces", status_code=status.HTTP_201_CREATED)
async def create_autopilot_workspace(
    payload: AutopilotWorkspaceCreateRequest,
    request: Request,
) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    return await autopilot.create_workspace(
        website_url=str(payload.website_url),
        name=payload.name or "",
        competitors=[str(url) for url in payload.competitor_urls],
        mode=payload.mode,
        cadence=payload.cadence,
        user_context=payload.user_context,
    )


@router.post("/app/analyze/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_analyze_website_flow(
    payload: AnalyzeWebsiteFlowRequest,
    request: Request,
) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    if payload.publishing_mode == "live_publish" and not settings.allow_live_publish:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Live publish is disabled by safety gates.")
    state = new_analyze_flow_state(settings)
    state.website_url = str(payload.website_url)
    state.run_label = payload.name or str(payload.website_url)
    state.request_payload = payload.model_dump(mode="json")
    state.summary = {
        "publishing_safety": publishing_safety_state(settings),
        "requested_publishing_mode": payload.publishing_mode,
    }
    _analyze_flow_store(request)[state.job_id] = state
    await _persist_flow_state(request.app, state)
    _start_analyze_flow_task(
        request.app,
        state.job_id,
        _run_analyze_website_flow(request.app, state.job_id, payload),
    )
    return state.as_dict()


@router.get("/app/analyze/runs/recent")
async def list_recent_analyze_runs(request: Request, limit: int = 10) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    runs = await autopilot.repositories.analyze_flow_runs.list_recent(limit=limit)
    return {"runs": runs}


@router.get("/app/analyze/runs/{job_id}")
async def get_analyze_website_flow(job_id: str, request: Request) -> dict[str, Any]:
    state = await _get_analyze_flow_state(request, job_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyze Website run not found.")
    return state.as_dict()


@router.post("/app/analyze/runs/{job_id}/cancel")
async def cancel_analyze_website_flow(job_id: str, request: Request) -> dict[str, Any]:
    state = await _get_analyze_flow_state(request, job_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyze Website run not found.")
    if state.overall_status == "cancelled":
        return state.as_dict()
    in_progress = state.overall_status in {"queued", "running"} or any(
        step.status == "running" for step in state.steps
    )
    if not in_progress:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis is not running.")
    await _cancel_analyze_flow_run(request.app, state, "Analysis cancelled by user.")
    return state.as_dict()


@router.delete("/app/analyze/runs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analyze_website_flow(job_id: str, request: Request) -> Response:
    autopilot: AutopilotService = request.app.state.autopilot_service
    state = await _get_analyze_flow_state(request, job_id)
    if state is not None and (
        state.overall_status in {"queued", "running"}
        or any(step.status == "running" for step in state.steps)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop the analysis first, or wait for it to finish.",
        )
    deleted = await autopilot.repositories.analyze_flow_runs.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analyze Website run not found.")
    _analyze_flow_store(request).pop(job_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/app/analyze/runs/{parent_job_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
async def rerun_analyze_website_flow(
    parent_job_id: str,
    payload: AnalyzeFlowRerunRequest,
    request: Request,
) -> dict[str, Any]:
    parent = await _get_analyze_flow_state(request, parent_job_id)
    if parent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent Analyze Website run not found.")
    if payload.rerun_type == "full":
        request_payload = parent.request_payload if isinstance(parent.request_payload, dict) else {}
        if not request_payload.get("website_url"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent run is missing website URL.")
        flow_request = AnalyzeWebsiteFlowRequest.model_validate(request_payload)
        return await start_analyze_website_flow(flow_request, request)

    workspace_id = parent.workspace_id
    if not workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent run has no workspace.")

    state = new_analyze_flow_state_from_parent(
        parent,
        rerun_type=payload.rerun_type,
        settings=request.app.state.settings,
    )
    state.parent_run_id = parent_job_id
    state.rerun_type = payload.rerun_type
    state.workspace_id = workspace_id
    state.website_url = parent.website_url
    state.run_label = parent.run_label
    state.request_payload = dict(parent.request_payload)
    state.prior_summary = dict(parent.summary or {})
    state.summary = {
        "publishing_safety": publishing_safety_state(request.app.state.settings),
        "prior_run_id": parent_job_id,
        "rerun_type": payload.rerun_type,
    }
    _analyze_flow_store(request)[state.job_id] = state
    await _persist_flow_state(request.app, state)
    _start_analyze_flow_task(
        request.app,
        state.job_id,
        _run_partial_analyze_flow(request.app, state.job_id, payload.rerun_type),
    )
    return state.as_dict()


@router.get("/autopilot/workspaces/{workspace_id}")
async def get_autopilot_workspace(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.get_workspace(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/autopilot/workspaces/{workspace_id}/recommendations/export")
async def export_workspace_recommendations_csv(
    workspace_id: str,
    request: Request,
    actions: str = "create,refresh,monitor",
) -> Response:
    autopilot: AutopilotService = request.app.state.autopilot_service
    workspace = await autopilot.repositories.autopilot_workspaces.get(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    action_filter = normalize_export_actions(actions.split(","))
    recommendations = await autopilot.repositories.opportunity_recommendations.list_for_workspace(
        workspace_id,
        limit=500,
    )
    csv_body = recommendations_to_csv(recommendations, actions=action_filter)
    filename = export_filename(
        website_url=workspace.get("website_url"),
        workspace_name=workspace.get("name"),
    )
    return Response(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _manual_recommendation_service(request: Request):
    return request.app.state.manual_recommendation_service


def _wordpress_connector_service(request: Request):
    return request.app.state.wordpress_connector_service


@router.post("/workspaces/{workspace_id}/manual-recommendations")
async def create_manual_recommendation(
    workspace_id: str,
    payload: ManualRecommendationCreateRequest,
    request: Request,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    try:
        manual = await service.create_manual(
            workspace_id,
            raw_headline=payload.raw_headline,
            raw_notes=payload.raw_notes,
            content_type=payload.content_type,
            target_audience=payload.target_audience,
            selected_products=payload.selected_products,
            created_by=payload.created_by,
        )
        return {"manual_recommendation": manual}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/manual-recommendations/create-and-enrich")
async def create_and_enrich_manual_recommendation(
    workspace_id: str,
    payload: ManualRecommendationCreateRequest,
    request: Request,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    try:
        manual = await service.create_and_enrich(
            workspace_id,
            raw_headline=payload.raw_headline,
            raw_notes=payload.raw_notes,
            content_type=payload.content_type,
            target_audience=payload.target_audience,
            selected_products=payload.selected_products,
            created_by=payload.created_by,
        )
        return {"manual_recommendation": manual}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/workspaces/{workspace_id}/manual-recommendations")
async def list_manual_recommendations(
    workspace_id: str,
    request: Request,
    status: str | None = None,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    items = await service.list_manual(workspace_id, status=status)
    return {"manual_recommendations": items}


@router.get("/workspaces/{workspace_id}/manual-recommendations/catalog-products")
async def list_manual_recommendation_catalog_products(
    workspace_id: str,
    request: Request,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    try:
        products = await service.list_catalog_products(workspace_id)
        return {"catalog_products": products}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/manual-recommendations/{manual_id}/enrich")
async def enrich_manual_recommendation(
    workspace_id: str,
    manual_id: str,
    request: Request,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    try:
        manual = await service.enrich_manual(workspace_id, manual_id)
        return {"manual_recommendation": manual}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/manual-recommendations/{manual_id}/queue")
async def queue_manual_recommendation(
    workspace_id: str,
    manual_id: str,
    payload: ManualRecommendationQueueRequest,
    request: Request,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    try:
        result = await service.queue_manual(
            workspace_id,
            manual_id,
            allow_duplicates=payload.allow_duplicates,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/workspaces/{workspace_id}/wordpress-connector")
async def get_wordpress_connector_settings(workspace_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return {"settings": await service.get_settings(workspace_id)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/workspaces/{workspace_id}/wordpress-connector")
async def save_wordpress_connector_settings(
    workspace_id: str,
    payload: WordPressConnectorSettingsRequest,
    request: Request,
) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        env_payload = None
        if payload.environments:
            env_payload = {
                name: values.model_dump(exclude_none=True)
                for name, values in payload.environments.items()
            }
        settings = await service.save_settings(
            workspace_id,
            connector_enabled=payload.connector_enabled,
            active_environment=payload.active_environment,
            environment=payload.environment,
            wordpress_base_url=payload.wordpress_base_url,
            trendplot_site_id=payload.trendplot_site_id,
            trendplot_shared_secret=payload.trendplot_shared_secret,
            environments=env_payload,
        )
        return {"settings": settings}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/wordpress-connector/test")
async def test_wordpress_connector(
    workspace_id: str,
    request: Request,
    payload: WordPressConnectorTestRequest | None = None,
) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.test_wordpress_connector(
            workspace_id,
            environment=(payload or WordPressConnectorTestRequest()).environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/wordpress-connector/draft")
async def create_wordpress_connector_draft(
    job_id: str,
    request: Request,
    payload: WordPressConnectorDraftRequest | None = None,
) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.create_wordpress_draft(job_id, force=bool((payload or WordPressConnectorDraftRequest()).force))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/wordpress-connector/draft/update")
async def update_wordpress_connector_draft(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.update_wordpress_draft(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/wordpress-connector/status/refresh")
async def refresh_wordpress_connector_status(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.refresh_wordpress_status(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/seo/generate")
async def generate_job_seo(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.generate_seo_package(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/seo/package")
async def generate_seo_package(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.generate_seo_package(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/jobs/{job_id}/seo")
async def save_job_seo(job_id: str, payload: JobSeoSaveRequest, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.save_job_seo(job_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/seo/sync")
async def sync_job_seo_to_wordpress(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.sync_job_seo_to_wordpress(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/seo/refresh")
async def refresh_job_seo_from_wordpress(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.refresh_job_seo_from_wordpress(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/seo/optimize")
async def run_job_seo_optimization(job_id: str, request: Request) -> dict[str, Any]:
    service = _wordpress_connector_service(request)
    try:
        return await service.run_seo_optimization(job_id, respect_manual_seo=False)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/manual-recommendations/{manual_id}/archive")
async def archive_manual_recommendation(
    workspace_id: str,
    manual_id: str,
    request: Request,
) -> dict[str, Any]:
    service = _manual_recommendation_service(request)
    try:
        manual = await service.archive_manual(workspace_id, manual_id)
        return {"manual_recommendation": manual}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/autopilot/workspaces/{workspace_id}/recommendations/audit")
async def audit_workspace_recommendations(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    workspace = await autopilot.repositories.autopilot_workspaces.get(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    recommendations = await autopilot.repositories.opportunity_recommendations.list_for_workspace(
        workspace_id,
        limit=500,
    )
    return build_recommendation_audit_report(recommendations)


@router.get("/autopilot/workspaces/{workspace_id}/niche-profile")
async def get_autopilot_niche_profile(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        workspace = await autopilot.get_workspace(workspace_id)
        return {"niche_profile": workspace.get("niche_profile")}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/niche-profile/refresh")
async def refresh_autopilot_niche_profile(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return {"niche_profile": await autopilot.refresh_niche_profile(workspace_id)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/analyze")
async def analyze_autopilot_workspace(
    workspace_id: str,
    payload: AutopilotAnalyzeRequest,
    request: Request,
) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.analyze_workspace(
            workspace_id,
            max_pages_per_site=payload.max_pages_per_site,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot workspace analysis failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Workspace analysis external request failed.") from exc


@router.post("/autopilot/workspaces/{workspace_id}/generate-plan")
async def generate_autopilot_plan(
    workspace_id: str,
    payload: AutopilotPlanRequest,
    request: Request,
) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.generate_plan(workspace_id, horizon_days=payload.horizon_days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/autopilot/workspaces/{workspace_id}/opportunity-intelligence")
async def get_autopilot_opportunity_intelligence(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        workspace = await autopilot.get_workspace(workspace_id)
        return workspace.get("opportunity_intelligence") or {"groups": {}, "summary": {}}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/opportunity-intelligence/refresh")
async def refresh_autopilot_opportunity_intelligence(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.rerun_recommendations(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/autopilot/workspaces/{workspace_id}/demand-insights")
async def get_autopilot_demand_insights(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/developer/demand/providers")
async def get_developer_demand_providers(request: Request) -> dict[str, Any]:
    del request
    _legacy_pipeline_removed()


@router.post("/developer/demand/workspaces/{workspace_id}/fetch")
async def fetch_developer_demand_observations(
    workspace_id: str,
    payload: DemandFetchRequest,
    request: Request,
) -> dict[str, Any]:
    del workspace_id, payload, request
    _legacy_pipeline_removed()


@router.get("/developer/demand/workspaces/{workspace_id}/observations")
async def list_developer_demand_observations(
    workspace_id: str,
    request: Request,
    limit: int = 100,
    query: str | None = None,
    page_url: str | None = None,
    country: str | None = None,
    device: str | None = None,
    provider: str | None = None,
    min_impressions: float | None = None,
    min_opportunity_score: float | None = None,
) -> dict[str, Any]:
    del workspace_id, request, limit, query, page_url, country, device, provider, min_impressions, min_opportunity_score
    _legacy_pipeline_removed()


@router.get("/developer/demand/workspaces/{workspace_id}/runs")
async def list_developer_demand_runs(workspace_id: str, request: Request, limit: int = 25) -> dict[str, Any]:
    del workspace_id, request, limit
    _legacy_pipeline_removed()


@router.get("/developer/market/providers")
async def get_developer_market_providers(request: Request) -> dict[str, Any]:
    del request
    _legacy_pipeline_removed()


@router.post("/developer/market/workspaces/{workspace_id}/discover")
async def discover_developer_market_intelligence(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/developer/market/workspaces/{workspace_id}/signals")
async def list_developer_market_signals(workspace_id: str, request: Request, limit: int = 100) -> dict[str, Any]:
    del workspace_id, request, limit
    _legacy_pipeline_removed()


@router.get("/developer/market/workspaces/{workspace_id}/candidates")
async def list_developer_market_candidates(workspace_id: str, request: Request, limit: int = 200) -> dict[str, Any]:
    del workspace_id, request, limit
    _legacy_pipeline_removed()


@router.get("/developer/market/workspaces/{workspace_id}/runs")
async def list_developer_market_runs(workspace_id: str, request: Request, limit: int = 25) -> dict[str, Any]:
    del workspace_id, request, limit
    _legacy_pipeline_removed()


@router.get("/autopilot/workspaces/{workspace_id}/market-insights")
async def get_autopilot_market_insights(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.post("/autopilot/workspaces/{workspace_id}/market-intelligence/refresh")
async def refresh_autopilot_market_intelligence(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.post("/developer/editorial/workspaces/{workspace_id}/generate")
async def generate_developer_editorial_concepts(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/developer/editorial/workspaces/{workspace_id}/concepts")
async def list_developer_editorial_concepts(
    workspace_id: str,
    request: Request,
    limit: int = 200,
    finalists_only: bool = False,
) -> dict[str, Any]:
    del workspace_id, request, limit, finalists_only
    _legacy_pipeline_removed()


@router.post("/autopilot/workspaces/{workspace_id}/discover-trends")
async def discover_autopilot_trends(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/autopilot/workspaces/{workspace_id}/trend-insights")
async def get_autopilot_trend_insights(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    return {
        "trend_discovery_run": None,
        "trend_discovery_queries": [],
        "trend_signals": [],
        "provider_status": [],
    }


@router.post("/autopilot/workspaces/{workspace_id}/publishing-memory/refresh")
async def refresh_autopilot_publishing_memory(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/autopilot/workspaces/{workspace_id}/coverage")
async def get_autopilot_coverage(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/autopilot/workspaces/{workspace_id}/refresh-candidates")
async def get_autopilot_refresh_candidates(workspace_id: str, request: Request) -> dict[str, Any]:
    del workspace_id, request
    _legacy_pipeline_removed()


@router.get("/autopilot/workspaces/{workspace_id}/calendar")
async def get_autopilot_calendar(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.get_calendar(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/enable")
async def enable_autopilot_workspace(
    workspace_id: str,
    payload: AutopilotEnableRequest,
    request: Request,
) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.enable_workspace(workspace_id, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/pause")
async def pause_autopilot_workspace(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.pause_workspace(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/reassess")
async def reassess_autopilot_workspace(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.reassess_workspace(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/performance-refresh")
async def refresh_autopilot_performance(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.refresh_performance_feedback(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/autopilot/workspaces/{workspace_id}/connector-sync")
async def sync_autopilot_connector_inventory(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.sync_connector_inventory(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector inventory sync failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector inventory sync failed.") from exc


@router.post("/autopilot/workspaces/{workspace_id}/run-due")
async def run_due_autopilot_items(
    workspace_id: str,
    payload: RunDueItemsRequest,
    request: Request,
) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.run_due_items(workspace_id, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/autopilot/calendar-items/{item_id}")
async def update_autopilot_calendar_item(
    item_id: str,
    payload: CalendarItemPatch,
    request: Request,
) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.update_calendar_item(item_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/autopilot/calendar-items/{item_id}/generate")
async def generate_autopilot_calendar_item(item_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.generate_calendar_item(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot plan item generation failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External API request failed.") from exc


@router.get("/autopilot/connector/capabilities")
async def trendplot_connector_capabilities(request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    return await autopilot.connector_capabilities()


@router.get("/autopilot/workspaces/{workspace_id}/connector/capabilities")
async def trendplot_workspace_connector_capabilities(workspace_id: str, request: Request) -> dict[str, Any]:
    autopilot: AutopilotService = request.app.state.autopilot_service
    try:
        return await autopilot.connector_capabilities(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/connectors/wordpress/contract")
async def wordpress_connector_contract() -> dict[str, Any]:
    return TrendplotConnectorContract().capabilities()


@router.get("/connectors/wordpress/health")
async def wordpress_connector_health(request: Request) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).health()
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector health check failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector health check failed.") from exc


@router.get("/connectors/wordpress/capabilities")
async def wordpress_connector_capability_discovery(request: Request) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).capabilities()
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector capability discovery failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector capability discovery failed.") from exc


@router.get("/connectors/wordpress/site-summary")
async def wordpress_connector_site_summary(request: Request) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).site_summary()
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector site summary failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector site summary failed.") from exc


@router.get("/connectors/wordpress/templates")
async def wordpress_connector_templates(request: Request) -> dict[str, Any]:
    try:
        return {"templates": await _wordpress_connector(request).list_templates()}
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector template listing failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector template listing failed.") from exc


@router.get("/connectors/wordpress/taxonomies/categories")
async def wordpress_connector_categories(request: Request) -> dict[str, Any]:
    try:
        return {"categories": await _wordpress_connector(request).list_categories()}
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector category listing failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector category listing failed.") from exc


@router.get("/connectors/wordpress/taxonomies/tags")
async def wordpress_connector_tags(request: Request, search: str = "") -> dict[str, Any]:
    try:
        return {"tags": await _wordpress_connector(request).list_tags(search=search)}
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector tag listing failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector tag listing failed.") from exc


@router.get("/connectors/wordpress/inventory/content")
async def wordpress_connector_content_inventory(
    request: Request,
    post_type: str = "post,page,product",
    updated_after: str | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).content_inventory(
            post_type=post_type,
            updated_after=updated_after,
            limit=limit,
            cursor=cursor,
        )
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector content inventory failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector content inventory failed.") from exc


@router.get("/connectors/wordpress/inventory/products")
async def wordpress_connector_product_inventory(
    request: Request,
    updated_after: str | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).product_inventory(
            updated_after=updated_after,
            limit=limit,
            cursor=cursor,
        )
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector product inventory failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector product inventory failed.") from exc


@router.get("/connectors/wordpress/metrics/content")
async def wordpress_connector_content_metrics(
    request: Request,
    updated_after: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).content_metrics(updated_after=updated_after, limit=limit)
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector content metrics failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector content metrics failed.") from exc


@router.post("/connectors/wordpress/media/from-url")
async def wordpress_connector_media_from_url(
    payload: ConnectorMediaFromUrlRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return await _wordpress_connector(request).upload_media_from_url(payload)
    except (ValueError, ConnectorError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("Trendplot Connector media-from-url upload failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Connector media upload failed.") from exc


@router.post("/api/connectors/wordpress/events")
async def ingest_wordpress_connector_event(payload: ConnectorEventRequest, request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    _verify_connector_event_auth(request, settings, payload.site_id)
    repositories: Repositories = request.app.state.repositories
    workspace_id = await _workspace_id_for_connector_site(repositories, payload.site_id)
    event = await repositories.connector_events.create(payload.model_dump(), workspace_id=workspace_id)
    if workspace_id:
        await repositories.approval_events.create(
            workspace_id=workspace_id,
            event_type=f"connector_{payload.event_type}",
            actor="wordpress-plugin",
            notes=f"Received connector event {payload.event_type}.",
            metadata={"connector_event_id": event["id"], "post": payload.post.model_dump() if payload.post else None},
        )
        if payload.event_type in {"post_created", "post_updated", "post_published"} and payload.post:
            await repositories.published_content.upsert_from_connector(
                workspace_id,
                {
                    "external_id": str(payload.post.id),
                    "url": payload.post.url,
                    "status": payload.post.status or "unknown",
                    "channel": "wordpress",
                    "published_at": payload.occurred_at if payload.event_type == "post_published" else None,
                    "metrics": {"source_event_id": payload.event_id},
                },
            )
    return {"ok": True, "event": event}


@router.get("/connectors/wordpress/events")
async def list_wordpress_connector_events(
    request: Request,
    workspace_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    repositories: Repositories = request.app.state.repositories
    return {"events": await repositories.connector_events.list_recent(workspace_id=workspace_id, limit=limit)}


@router.post("/analyze-website", response_model=AnalyzeWebsiteResponse)
async def analyze_website(
    payload: AnalyzeWebsiteRequest,
    request: Request,
) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    settings: Settings = request.app.state.settings

    try:
        return await analysis_service.analyze(
            AnalyzeWebsiteCommand(
                website_url=str(payload.website_url),
                competitor_urls=[str(url) for url in payload.competitor_urls],
                max_pages_per_site=payload.max_pages_per_site,
                vertical=_analysis_vertical(payload, settings),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Website analysis external request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Website analysis request failed.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected website analysis failure.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Website analysis failed.",
        ) from exc


@router.post("/analysis-jobs")
async def create_analysis_job(
    payload: AnalyzeWebsiteRequest,
    request: Request,
) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    settings: Settings = request.app.state.settings

    try:
        return await analysis_service.create_analysis_job(
            AnalyzeWebsiteCommand(
                website_url=str(payload.website_url),
                competitor_urls=[str(url) for url in payload.competitor_urls],
                max_pages_per_site=payload.max_pages_per_site,
                vertical=_analysis_vertical(payload, settings),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Persisted website analysis failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Website analysis failed.",
        ) from exc


@router.get("/analysis-jobs", response_model=list[AnalysisJobSummary])
async def list_analysis_jobs(request: Request, limit: int = 10) -> list[dict[str, Any]]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    safe_limit = max(1, min(limit, 50))
    return await analysis_service.list_analysis_jobs(safe_limit)


@router.post("/analysis-jobs/cancel-active")
async def cancel_active_analysis_jobs(request: Request) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    cancelled = await analysis_service.cancel_active_analyses()
    return {
        "cancelled_count": len(cancelled),
        "cancelled": cancelled,
    }


@router.post("/analysis-jobs/{analysis_job_id}/cancel")
async def cancel_analysis_job(request: Request, analysis_job_id: str) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    try:
        return await analysis_service.cancel_analysis_job(analysis_job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/analysis-jobs/{analysis_job_id}")
async def get_analysis_job(request: Request, analysis_job_id: str) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    try:
        return await analysis_service.get_analysis_job(analysis_job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/analysis-jobs/{analysis_job_id}/opportunities")
async def list_analysis_opportunities(
    request: Request,
    analysis_job_id: str,
    cluster_id: str | None = None,
    audience_id: str | None = None,
    opportunity_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    _legacy_pipeline_removed()
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    opportunities = await analysis_service.list_opportunities(
        analysis_job_id,
        cluster_id=cluster_id,
        audience_id=audience_id,
        opportunity_type=opportunity_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "analysis_job_id": analysis_job_id,
        "limit": max(1, min(limit, 500)),
        "offset": max(0, offset),
        "opportunities": opportunities,
    }


@router.get("/analysis-jobs/{analysis_job_id}/audiences")
async def list_analysis_audiences(request: Request, analysis_job_id: str) -> dict[str, Any]:
    _legacy_pipeline_removed()
    repositories: Repositories = request.app.state.repositories
    return {
        "analysis_job_id": analysis_job_id,
        "audiences": await repositories.audience_profiles.list_for_job(analysis_job_id),
    }


@router.get("/analysis-jobs/{analysis_job_id}/clusters")
async def list_analysis_clusters(request: Request, analysis_job_id: str) -> dict[str, Any]:
    _legacy_pipeline_removed()
    repositories: Repositories = request.app.state.repositories
    return {
        "analysis_job_id": analysis_job_id,
        "clusters": await repositories.opportunity_clusters.list_for_job(analysis_job_id),
    }


@router.get("/analysis-jobs/{analysis_job_id}/authority-graph")
async def get_analysis_authority_graph(request: Request, analysis_job_id: str) -> dict[str, Any]:
    _legacy_pipeline_removed()
    repositories: Repositories = request.app.state.repositories
    graph = await repositories.authority_graph.list_for_job(analysis_job_id)
    return {
        "analysis_job_id": analysis_job_id,
        "authority_graph": graph,
    }


@router.get("/opportunities/{opportunity_id}/relationships")
async def list_opportunity_relationships(request: Request, opportunity_id: str) -> dict[str, Any]:
    repositories: Repositories = request.app.state.repositories
    opportunity = await repositories.opportunities.get(opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found.")
    return {
        "opportunity_id": opportunity_id,
        "relationships": await repositories.opportunity_relationships.list_for_opportunity(opportunity_id),
    }


@router.patch("/analysis-suggestions/{suggestion_id}")
async def update_analysis_suggestion(
    suggestion_id: str,
    payload: AnalysisSuggestionPatch,
    request: Request,
) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    try:
        return await analysis_service.update_suggestion(
            suggestion_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(
    opportunity_id: str,
    payload: OpportunityPatch,
    request: Request,
) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    try:
        return await analysis_service.update_opportunity(
            opportunity_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/opportunities/{opportunity_id}/generate-article")
async def generate_article_from_opportunity(
    opportunity_id: str,
    request: Request,
) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    try:
        return await analysis_service.generate_article_from_opportunity(opportunity_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("External API returned an error.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="External API request failed.",
        ) from exc


@router.post("/analysis-suggestions/{suggestion_id}/generate-article")
async def generate_article_from_suggestion(
    suggestion_id: str,
    request: Request,
) -> dict[str, Any]:
    analysis_service: WebsiteAnalysisService = request.app.state.website_analysis_service
    try:
        return await analysis_service.generate_article_from_suggestion(suggestion_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("External API returned an error.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="External API request failed.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("External API request failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="External API request failed.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected suggestion generation failure.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Article generation from suggestion failed.",
        ) from exc


@router.get("/config/api-keys", response_model=ApiKeyCheckResponse)
async def check_api_keys(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    checks = [
        _check_secret(
            name="OpenAI",
            value=settings.openai_api_key,
            placeholders=("sk-your-openai-api-key", "your-openai-api-key"),
        ),
        _check_secret(
            name="YouTube Data API",
            value=settings.youtube_api_key,
            placeholders=("your-youtube-data-api-key", "youtube-api-key"),
        ),
        _check_wordpress(settings),
    ]

    return {
        "checks": checks,
        "note": "This checks values loaded by the running app. Restart after changing .env.",
    }


@router.get("/config/unattended-status")
async def unattended_status(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    repositories: Repositories = request.app.state.repositories
    last_report = None
    for job in await repositories.jobs.list_recent(10):
        artifacts = await repositories.artifacts.list_for_job(job["id"])
        reports = [artifact for artifact in artifacts if artifact.get("artifact_type") == "publish_decision_report"]
        if reports:
            last_report = reports[-1].get("content_json")
            break
    return {
        "enabled": settings.unattended_mode_enabled,
        "default_publish_policy": settings.unattended_default_publish_policy,
        "auto_live_allowed": settings.unattended_allow_auto_live and settings.allow_auto_live and settings.allow_live_publish,
        "require_quality_pass": settings.unattended_require_quality_pass,
        "require_sanity_pass": settings.unattended_require_sanity_pass,
        "default_template": settings.wordpress_default_template,
        "default_category_id": settings.wordpress_default_category_id,
        "default_category_slug": settings.wordpress_default_category_slug,
        "default_tags": settings.wordpress_default_tags,
        "last_decision_report": last_report,
    }


@router.get("/jobs/recent", response_model=list[JobSummary])
async def recent_jobs(
    request: Request,
    limit: int = 10,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    repositories: Repositories = request.app.state.repositories
    safe_limit = max(1, min(limit, 50))
    return await repositories.jobs.list_recent(safe_limit, workspace_id=workspace_id)


def _cancel_background_job_task(app: Any, job_id: str) -> None:
    task = _analyze_flow_tasks(app).get(job_id)
    if task is not None and not task.done():
        task.cancel()


@router.post("/jobs/{job_id}/cancel")
async def cancel_article_generation_job(job_id: str, request: Request) -> dict[str, Any]:
    job_service: JobService = request.app.state.job_service
    try:
        result = await job_service.cancel_generation_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _cancel_background_job_task(request.app, job_id)
    return result


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article_generation_job(job_id: str, request: Request) -> None:
    job_service: JobService = request.app.state.job_service
    _cancel_background_job_task(request.app, job_id)
    try:
        await job_service.delete_generation_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/generation-result")
async def job_generation_result(request: Request, job_id: str) -> dict[str, Any]:
    job_service: JobService = request.app.state.job_service
    repositories: Repositories = request.app.state.repositories
    job = await repositories.jobs.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )
    result = await job_service.get_generation_result(job_id)
    if result is None:
        status_value = str(job.get("status") or "")
        if status_value in GENERATION_ACTIVE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Article generation is still running.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation result is not available for this job.",
        )
    return result


@router.get("/jobs/{job_id}")
async def job_detail(request: Request, job_id: str) -> dict[str, Any]:
    repositories: Repositories = request.app.state.repositories
    job = await repositories.jobs.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    return {
        "job": job,
        "artifacts": await repositories.artifacts.list_for_job(job_id),
        "logs": await repositories.logs.list_for_job(job_id),
    }


@router.get("/jobs/{job_id}/preview", response_class=HTMLResponse)
async def job_preview(request: Request, job_id: str, surface: str = "publishable") -> str:
    repositories: Repositories = request.app.state.repositories
    job = await repositories.jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    artifact_type = "article_html_editorial" if surface.strip().lower() in {"editorial", "editorial_full", "full"} else "publishable_html"
    rendered = await repositories.artifacts.get_latest_artifact(job_id, artifact_type)
    if rendered is None or not rendered.get("content_text"):
        fallback_type = "rendered_html" if artifact_type == "publishable_html" else "article_html"
        rendered = await repositories.artifacts.get_latest_artifact(job_id, fallback_type)
    if rendered is None or not rendered.get("content_text"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered preview not found.")
    title = escape(str(job.get("request_input", {}).get("title") or "Article Preview"))
    preview_html = render_local_youtube_iframes(str(rendered["content_text"]))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin: 0; background: #f6f7fb; color: #1f2933; font-family: Arial, sans-serif; line-height: 1.65; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 64px; background: #fff; }}
    .bp-ai-article h1, .bp-ai-article h2, .bp-ai-article h3 {{ line-height: 1.25; color: #111827; }}
    .bp-ai-article img {{ max-width: 100%; height: auto; border-radius: 12px; }}
    .bp-ai-section {{ margin: 28px 0; }}
    .bp-ai-key-takeaways, .bp-ai-faq, .bp-ai-references, .bp-ai-related-video {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; margin: 24px 0; }}
    a {{ color: #2563eb; }}
    iframe {{ max-width: 100%; }}
  </style>
</head>
<body><main>{preview_html}</main></body>
</html>"""


@router.get("/generated-images/{filename}")
async def generated_image(request: Request, filename: str) -> FileResponse:
    settings: Settings = request.app.state.settings
    image_dir = Path(settings.ai_image_output_dir).resolve()
    image_path = (image_dir / Path(filename).name).resolve()
    if image_path.parent != image_dir or not image_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated image not found.")
    return FileResponse(image_path)


@router.post("/jobs/{job_id}/publish-draft")
async def publish_job_draft(
    job_id: str,
    payload: PublishJobRequest,
    request: Request,
) -> dict[str, Any]:
    job_service: JobService = request.app.state.job_service
    try:
        return await job_service.publish_existing_job(
            job_id=job_id,
            status="draft",
            category_id=payload.category_id,
            wordpress_template=payload.wordpress_template,
            wordpress_category_id=payload.wordpress_category_id,
            wordpress_category_slug=payload.wordpress_category_slug,
            wordpress_category_name=payload.wordpress_category_name,
            wordpress_tags=payload.wordpress_tags,
            featured_image_id=payload.featured_image_id,
            featured_image_url=payload.featured_image_url,
            featured_image_alt=payload.featured_image_alt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.exception("WordPress draft publish failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="WordPress publish failed.") from exc


@router.post("/jobs/{job_id}/rerun")
async def rerun_job(job_id: str, request: Request) -> dict[str, Any]:
    job_service: JobService = request.app.state.job_service
    try:
        return await job_service.rerun_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        logger.exception("External API returned an error during rerun.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External API request failed.") from exc
    except httpx.HTTPError as exc:
        logger.exception("External API request failed during rerun.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="External API request failed.") from exc


@router.post("/jobs/{job_id}/run-sanity-check")
async def run_job_sanity_check(
    job_id: str,
    payload: RunSanityCheckRequest,
    request: Request,
) -> dict[str, Any]:
    job_service: JobService = request.app.state.job_service
    try:
        return await job_service.run_sanity_check_for_job(
            job_id=job_id,
            apply_rewrite=payload.apply_rewrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/publish-live")
async def publish_job_live(job_id: str, request: Request) -> dict[str, Any]:
    del job_id, request
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Live publishing is not supported. Use the Trendplot Connector plugin to create WordPress drafts.",
    )


@router.get("/wordpress/categories")
async def wordpress_categories(request: Request) -> dict[str, Any]:
    try:
        categories = await request.app.state.job_service.registry.wordpress.list_categories()
    except httpx.HTTPError as exc:
        logger.exception("WordPress category listing failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="WordPress category listing failed.") from exc
    return {"categories": categories}


@router.get("/wordpress/tags")
async def wordpress_tags(request: Request, search: str = "") -> dict[str, Any]:
    try:
        tags = await request.app.state.job_service.registry.wordpress.list_tags(search=search)
    except httpx.HTTPError as exc:
        logger.exception("WordPress tag listing failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="WordPress tag listing failed.") from exc
    return {"tags": tags}


@router.get("/wordpress/templates")
async def wordpress_templates(request: Request) -> dict[str, Any]:
    try:
        templates = await request.app.state.job_service.registry.wordpress.list_templates()
    except httpx.HTTPError as exc:
        logger.exception("WordPress template listing failed.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="WordPress template listing failed.") from exc
    return {"templates": templates}


async def _get_analyze_flow_state(request: Request, job_id: str) -> AnalyzeFlowState | None:
    state = _analyze_flow_store(request).get(job_id)
    if state is None:
        autopilot: AutopilotService = request.app.state.autopilot_service
        persisted = await autopilot.repositories.analyze_flow_runs.get(job_id)
        if not persisted:
            return None
        state = state_from_persisted_dict(persisted)
        _analyze_flow_store(request)[job_id] = state
    previous_overall = state.overall_status
    finish_overall_status(state)
    if (
        previous_overall in {"running", "queued"}
        and state.overall_status in {"succeeded", "failed", "warning"}
        and not any(step.status == "running" for step in state.steps)
    ):
        try:
            await _persist_flow_state(request.app, state)
        except Exception:
            logger.exception("Failed to heal Analyze Website flow overall_status.")
    return state


async def _persist_flow_state(app: Any, state: AnalyzeFlowState) -> None:
    try:
        autopilot: AutopilotService = app.state.autopilot_service
        await autopilot.repositories.analyze_flow_runs.upsert(state_to_persisted_dict(state))
    except Exception:
        logger.exception("Failed to persist Analyze Website flow state.")


def _analyze_flow_store(request: Request) -> dict[str, AnalyzeFlowState]:
    if not hasattr(request.app.state, "analyze_flows"):
        request.app.state.analyze_flows = {}
    return request.app.state.analyze_flows


def _analyze_flow_store_from_app(app: Any) -> dict[str, AnalyzeFlowState]:
    if not hasattr(app.state, "analyze_flows"):
        app.state.analyze_flows = {}
    return app.state.analyze_flows


def _analyze_flow_tasks(app: Any) -> dict[str, asyncio.Task[None]]:
    if not hasattr(app.state, "analyze_flow_tasks"):
        app.state.analyze_flow_tasks = {}
    return app.state.analyze_flow_tasks


def _start_analyze_flow_task(app: Any, job_id: str, coro: Any) -> None:
    tasks = _analyze_flow_tasks(app)
    existing = tasks.get(job_id)
    if existing is not None and not existing.done():
        existing.cancel()
    task = asyncio.create_task(coro)
    tasks[job_id] = task

    def _clear_task(_task: asyncio.Task[None]) -> None:
        tasks.pop(job_id, None)

    task.add_done_callback(_clear_task)


async def _cancel_analyze_flow_run(
    app: Any,
    state: AnalyzeFlowState,
    reason: str = "Analysis cancelled by user.",
) -> None:
    state.cancel_requested = True
    mark_flow_cancelled(state, reason)
    if state.workspace_id:
        try:
            autopilot: AutopilotService = app.state.autopilot_service
            workspace_payload = await autopilot.get_workspace(str(state.workspace_id))
            workspace = workspace_payload.get("workspace") or {}
            analysis_job_id = str(workspace.get("last_analysis_job_id") or "")
            if analysis_job_id:
                website_analysis: WebsiteAnalysisService = app.state.website_analysis_service
                await website_analysis.cancel_analysis_job(analysis_job_id, reason)
        except ValueError:
            pass
        except Exception:
            logger.exception("Failed to cancel underlying analysis job for Analyze Website flow.")
    task = _analyze_flow_tasks(app).get(state.job_id)
    if task is not None and not task.done():
        task.cancel()
    await _persist_flow_state(app, state)


async def _run_analyze_website_flow(app: Any, flow_job_id: str, payload: AnalyzeWebsiteFlowRequest) -> None:
    store = _analyze_flow_store_from_app(app)
    state = store[flow_job_id]
    settings: Settings = app.state.settings
    autopilot: AutopilotService = app.state.autopilot_service
    state.overall_status = "running"
    analysis_payload: dict[str, Any] | None = None
    plan_payload: dict[str, Any] | None = None

    try:
        mark_step(state, "workspace_setup", "running", "Creating or reusing workspace.")
        workspace_payload = await _create_or_reuse_workspace_for_flow(autopilot, payload)
        workspace = workspace_payload.get("workspace") or {}
        workspace_id = str(workspace.get("id") or "")
        state.workspace_id = workspace_id
        mark_step(state, "workspace_setup", "succeeded", f"Workspace ready: {workspace.get('name') or workspace.get('website_url')}.")

        analysis_payload = await autopilot.analyze_workspace(
            workspace_id,
            max_pages_per_site=max(1, min(payload.max_pages_per_site, settings.max_pages_per_site)),
            progress_callback=_analyze_flow_progress_callback(app, state),
            provided_competitor_urls=[str(url) for url in payload.competitor_urls],
        )
        workspace_payload = await autopilot.get_workspace(workspace_id)
        summarize_steps_from_payloads(
            state,
            analysis_payload=analysis_payload,
            workspace_payload=workspace_payload,
            settings=settings,
        )

        mark_step(state, "content_calendar", "running", "Generating proposed content calendar.")
        plan_payload = await autopilot.generate_plan(workspace_id, horizon_days=30)
        mark_step(
            state,
            "content_calendar",
            "succeeded",
            f"Generated {len(plan_payload.get('items') or [])} scheduled content items.",
        )

        draft_message = "Select a recommendation or schedule item to generate a draft."
        if payload.publishing_mode == "create_wordpress_draft":
            draft_message = "Draft creation is ready, but requires an explicit operator action."
        mark_step(state, "draft_generation", "skipped", draft_message)

        safety = publishing_safety_state(settings)
        if payload.publishing_mode == "create_wordpress_draft" and not safety["draft_upload_available"]:
            mark_step(state, "wordpress_upload", "warning", safety["draft_disabled_reason"] or "WordPress draft upload is unavailable.")
        else:
            mark_step(state, "wordpress_upload", "skipped", "WordPress upload requires an explicit operator action.")

        workspace_payload = await autopilot.get_workspace(workspace_id)
        state.summary = extract_flow_summary(
            workspace_payload=workspace_payload,
            analysis_payload=analysis_payload,
            plan_payload=plan_payload,
            settings=settings,
        )
        state.summary["requested_publishing_mode"] = payload.publishing_mode
        if state.cancel_requested:
            return
        finish_overall_status(state)
        await _persist_flow_state(app, state)
    except asyncio.CancelledError:
        if not state.cancel_requested:
            mark_flow_cancelled(state, "Analysis cancelled.")
        state.summary.setdefault("publishing_safety", publishing_safety_state(settings))
        await _persist_flow_state(app, state)
    except Exception as exc:  # noqa: BLE001 - surfaced through polling status.
        if state.cancel_requested:
            await _persist_flow_state(app, state)
            return
        _mark_active_step_failed(state, str(exc))
        state.summary.setdefault("publishing_safety", publishing_safety_state(settings))
        state.summary["error"] = str(exc)
        state.overall_status = "failed"
        await _persist_flow_state(app, state)
        logger.exception("Analyze Website flow failed.")


async def _run_partial_analyze_flow(app: Any, flow_job_id: str, rerun_type: str) -> None:
    store = _analyze_flow_store_from_app(app)
    state = store[flow_job_id]
    settings: Settings = app.state.settings
    autopilot: AutopilotService = app.state.autopilot_service
    workspace_id = str(state.workspace_id or "")
    state.overall_status = "running"
    await _persist_flow_state(app, state)
    request_payload = state.request_payload if isinstance(state.request_payload, dict) else {}
    max_pages = max(1, min(int(request_payload.get("max_pages_per_site") or 30), settings.max_pages_per_site))
    request_competitors = [
        str(item).strip()
        for item in (request_payload.get("competitor_urls") or [])
        if str(item).strip()
    ]
    if request_competitors:
        await autopilot.merge_workspace_competitors(workspace_id, request_competitors)

    try:
        if rerun_type == "recommendations":
            mark_step(state, "opportunity_ranking", "running", "Re-running recommendations.")
            await autopilot.rerun_recommendations(
                workspace_id,
                progress_callback=_analyze_flow_progress_callback(app, state),
            )
            workspace_payload = await autopilot.get_workspace(workspace_id)
            patch = extract_flow_summary(workspace_payload=workspace_payload, settings=settings)
            state.summary = merge_flow_summary(state.prior_summary, patch)
            state.summary["prior_run_id"] = state.parent_run_id
            state.summary["rerun_type"] = rerun_type
            state.summary["publishing_safety"] = publishing_safety_state(settings)
        elif rerun_type == "schedule":
            mark_step(state, "content_calendar", "running", "Re-generating content schedule.")
            plan_payload = await autopilot.generate_plan(workspace_id, horizon_days=30)
            workspace_payload = await autopilot.get_workspace(workspace_id)
            patch = extract_flow_summary(
                workspace_payload=workspace_payload,
                plan_payload=plan_payload,
                settings=settings,
            )
            state.summary = merge_flow_summary(state.prior_summary, patch)
            state.summary["prior_run_id"] = state.parent_run_id
            state.summary["rerun_type"] = rerun_type
            state.summary["publishing_safety"] = publishing_safety_state(settings)
        if state.cancel_requested:
            return
        skip_unstarted_flow_steps(state, note="Not part of this partial rerun.")
        finish_overall_status(state)
        await _persist_flow_state(app, state)
    except asyncio.CancelledError:
        if not state.cancel_requested:
            mark_flow_cancelled(state, "Analysis cancelled.")
        state.summary.setdefault("publishing_safety", publishing_safety_state(settings))
        await _persist_flow_state(app, state)
    except ValueError as exc:
        if state.cancel_requested:
            await _persist_flow_state(app, state)
            return
        _mark_active_step_failed(state, str(exc))
        state.summary["error"] = str(exc)
        finish_overall_status(state)
        await _persist_flow_state(app, state)
    except Exception as exc:  # noqa: BLE001
        if state.cancel_requested:
            await _persist_flow_state(app, state)
            return
        _mark_active_step_failed(state, str(exc))
        state.summary["error"] = str(exc)
        finish_overall_status(state)
        await _persist_flow_state(app, state)
        logger.exception("Analyze Website partial rerun failed.")


async def _create_or_reuse_workspace_for_flow(
    autopilot: AutopilotService,
    payload: AnalyzeWebsiteFlowRequest,
) -> dict[str, Any]:
    website_url = str(payload.website_url)
    provided_competitors = [str(url) for url in payload.competitor_urls]
    existing = await _find_workspace_by_url(autopilot, website_url)
    if existing:
        workspace_id = str(existing["id"])
        if provided_competitors:
            await autopilot.merge_workspace_competitors(workspace_id, provided_competitors)
        return await autopilot.get_workspace(workspace_id)
    context_parts = []
    if payload.target_market:
        context_parts.append(f"Target market/language: {payload.target_market}")
    if payload.notes:
        context_parts.append(str(payload.notes))
    return await autopilot.create_workspace(
        website_url=website_url,
        name=payload.name or "",
        competitors=[str(url) for url in payload.competitor_urls],
        mode="manual_review",
        cadence="weekly",
        user_context="\n".join(context_parts),
    )


def _analyze_flow_progress_callback(app: Any, state: AnalyzeFlowState):
    async def _callback(event: dict[str, Any]) -> None:
        if state.cancel_requested:
            return
        step_key = str(event.get("step") or "").strip()
        if not step_key:
            return
        valid_keys = {step.key for step in state.steps}
        if step_key not in valid_keys:
            return
        message = str(event.get("message") or state.step(step_key).message or "")
        details = event.get("details") if isinstance(event.get("details"), dict) else None
        status = str(event.get("status") or "running")
        kwargs = {
            "progress_current": _optional_int(event.get("progress_current")),
            "progress_total": _optional_int(event.get("progress_total")),
            "progress_label": str(event["progress_label"]) if event.get("progress_label") is not None else None,
            "details": details,
            "timing_note": str(event["timing_note"]) if event.get("timing_note") is not None else None,
        }
        if status in {"succeeded", "failed", "warning", "skipped", "disabled"}:
            mark_step(state, step_key, status, message, error=event.get("error"), warnings=event.get("warnings"), **kwargs)
        else:
            update_step_progress(state, step_key, message, **kwargs)
        finish_overall_status(state)
        await _persist_flow_state(app, state)

    return _callback


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _find_workspace_by_url(autopilot: AutopilotService, website_url: str) -> dict[str, Any] | None:
    target = _canonical_url_for_compare(website_url)
    for workspace in await autopilot.list_workspaces():
        if _canonical_url_for_compare(str(workspace.get("website_url") or "")) == target:
            return workspace
    return None


def _canonical_url_for_compare(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    normalized = parsed._replace(
        scheme=(parsed.scheme or "https").lower(),
        netloc=parsed.netloc.lower().lstrip("www."),
        path=(parsed.path or "/").rstrip("/") or "/",
        params="",
        query="",
        fragment="",
    )
    return urlunparse(normalized)


def _mark_active_step_failed(state: AnalyzeFlowState, error: str) -> None:
    for step in state.steps:
        if step.status == "running":
            mark_step(state, step.key, "failed", step.message or "Step failed.", error=error)
            return
    if state.rerun_type:
        return
    for step in state.steps:
        if step.status == "queued":
            mark_step(state, step.key, "failed", step.message or "Step failed.", error=error)
            return


def _analysis_vertical(payload: AnalyzeWebsiteRequest, settings: Settings) -> str:
    if payload.vertical_profile_id:
        return payload.vertical_profile_id
    if payload.vertical and payload.vertical not in {"", "auto"}:
        return payload.vertical
    if payload.vertical_mode in {"generic", "auto"}:
        return str(payload.vertical_mode)
    return settings.opportunity_vertical


def _wordpress_connector(request: Request) -> TrendplotWordPressConnectorClient:
    settings: Settings = request.app.state.settings
    if not settings.wordpress_connector_enabled:
        raise ValueError("Trendplot Connector is disabled. Set WORDPRESS_CONNECTOR_ENABLED=true to use connector endpoints.")
    return TrendplotWordPressConnectorClient(settings)


def _verify_connector_event_auth(request: Request, settings: Settings, site_id: str) -> None:
    if settings.wordpress_connector_site_id and site_id != settings.wordpress_connector_site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Connector site_id is not allowed.")


async def _workspace_id_for_connector_site(repositories: Repositories, site_id: str) -> str | None:
    for workspace in await repositories.autopilot_workspaces.list_recent(100):
        connections = await repositories.workspace_connections.list_for_workspace(workspace["id"])
        for connection in connections:
            metadata = connection.get("metadata") if isinstance(connection.get("metadata"), dict) else {}
            if metadata.get("site_id") == site_id:
                return workspace["id"]
    return None


def _check_secret(
    name: str,
    value: str,
    placeholders: tuple[str, ...],
) -> dict[str, Any]:
    cleaned = value.strip()
    if not cleaned:
        return {
            "name": name,
            "configured": False,
            "status": "missing",
            "masked_value": None,
            "detail": "No value is loaded.",
        }

    if cleaned in placeholders or cleaned.lower().startswith("your-"):
        return {
            "name": name,
            "configured": False,
            "status": "placeholder",
            "masked_value": _mask_secret(cleaned),
            "detail": "A placeholder value is loaded.",
        }

    return {
        "name": name,
        "configured": True,
        "status": "configured",
        "masked_value": _mask_secret(cleaned),
        "detail": "A non-placeholder value is loaded.",
    }


def _check_wordpress(settings: Settings) -> dict[str, Any]:
    missing = []
    if not settings.wordpress_connector_enabled:
        missing.append("WORDPRESS_CONNECTOR_ENABLED")
    if not settings.wordpress_connector_base_url.strip():
        missing.append("WORDPRESS_CONNECTOR_BASE_URL")
    if not settings.wordpress_connector_site_id.strip():
        missing.append("WORDPRESS_CONNECTOR_SITE_ID")
    if not settings.wordpress_connector_secret.strip():
        missing.append("WORDPRESS_CONNECTOR_SECRET")

    if missing:
        return {
            "name": "WordPress Connector",
            "configured": False,
            "status": "missing",
            "masked_value": None,
            "detail": f"Missing: {', '.join(missing)}.",
        }

    return {
        "name": "WordPress Connector",
        "configured": True,
        "status": "configured",
        "masked_value": _mask_secret(settings.wordpress_connector_secret),
        "detail": f"Connector base URL loaded: {settings.wordpress_connector_base_url.rstrip('/')}.",
    }


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
