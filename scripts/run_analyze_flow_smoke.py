"""Run product analyze path in-process (no HTTP server required)."""
from __future__ import annotations

import asyncio
import json
import sys

from app.analyze_flow import finish_overall_status, new_analyze_flow_state
from app.api.routes import AnalyzeWebsiteFlowRequest, _run_analyze_website_flow
from app.autopilot import AutopilotService
from app.config import get_settings
from app.db import create_database
from app.migration_runner import run_pending_migrations
from app.providers.registry import build_provider_registry
from app.repositories import Repositories
from app.services.jobs import JobService
from app.website_analysis import WebsiteAnalysisService


async def main() -> int:
    settings = get_settings()
    run_pending_migrations(settings.database_url)
    database = create_database(settings.database_url)
    repositories = Repositories(database.session_factory)
    registry = build_provider_registry(settings)
    job_service = JobService(settings, registry, repositories)
    website_analysis = WebsiteAnalysisService(
        registry.content_generation,
        repositories,
        job_service,
        settings,
        registry.video,
    )

    from types import SimpleNamespace

    app = SimpleNamespace()
    app.state = SimpleNamespace()
    app.state.settings = settings
    app.state.repositories = repositories
    app.state.job_service = job_service
    app.state.website_analysis_service = website_analysis
    app.state.autopilot_service = AutopilotService(
        settings=settings,
        repositories=repositories,
        website_analysis=website_analysis,
        job_service=job_service,
    )
    app.state.analyze_flows = {}

    payload = AnalyzeWebsiteFlowRequest(
        website_url="https://www.example.com/",
        name="in-process-smoke",
        competitor_urls=[],
        max_pages_per_site=int(sys.argv[1]) if len(sys.argv) > 1 else 10,
        publishing_mode="manual_review",
    )
    state = new_analyze_flow_state(settings)
    state.website_url = str(payload.website_url)
    state.run_label = payload.name or state.website_url
    state.request_payload = payload.model_dump(mode="json")
    app.state.analyze_flows[state.job_id] = state

    await _run_analyze_website_flow(app, state.job_id, payload)
    finish_overall_status(state)
    steps = {s.key: s.status for s in state.steps}
    print("overall_status", state.overall_status)
    print("steps", json.dumps(steps, indent=2))
    err = (state.summary or {}).get("error")
    if err:
        print("error", err)
    recs = (state.summary or {}).get("recommendations") or {}
    if isinstance(recs, dict):
        print("recommendations_total", recs.get("total"))
    await database.close()
    return 0 if state.overall_status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
