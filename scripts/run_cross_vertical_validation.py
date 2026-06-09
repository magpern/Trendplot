"""
Create and analyze 4 cross-vertical validation workspaces.
Produces CROSS_VERTICAL_WORKSPACE_SETUP.md and per-workspace data.
Does not modify EOG/OI logic, does not enable AI refinement.
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when running as `python scripts/<name>.py`
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.autopilot.service import AutopilotService
from app.config import get_settings
from app.db import create_database
from app.demand import DemandIntelligenceService
from app.editorial_opportunity import EditorialOpportunityService
from app.market_intelligence import MarketIntelligenceService
from app.repositories import Repositories
from app.services.jobs import JobService
from app.providers.registry import build_provider_registry
from app.website_analysis import WebsiteAnalysisService

ROOT = Path(__file__).resolve().parents[1]
DOCS_OUT = ROOT / "docs" / "validation"

WORKSPACES = [
    {
        "vertical": "SaaS / software",
        "name": "Plausible Analytics",
        "website_url": "https://plausible.io",
        "competitors": [
            "https://usefathom.com",
            "https://simpleanalytics.com",
            "https://matomo.org",
        ],
    },
    {
        "vertical": "Ecommerce",
        "name": "Tortuga Backpacks",
        "website_url": "https://www.tortugabackpacks.com",
        "competitors": [
            "https://www.nomatic.com",
            "https://www.peakdesign.com",
            "https://aersf.com",
        ],
    },
    {
        "vertical": "Local business",
        "name": "Denver Plumbing Consultants",
        "website_url": "https://www.denverplumbingconsultants.com",
        "competitors": [
            "https://www.neffandassociatesplumbing.com",
            "https://www.denverplumbing.com",
        ],
    },
    {
        "vertical": "Content publisher",
        "name": "The Pragmatic Engineer",
        "website_url": "https://blog.pragmaticengineer.com",
        "competitors": [
            "https://martinfowler.com",
            "https://www.infoq.com",
            "https://newsletter.pragmaticengineer.com",
        ],
    },
]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


async def _find_existing(repos: Repositories, website_url: str) -> dict[str, Any] | None:
    workspaces = await repos.autopilot_workspaces.list_recent(100)
    for ws in workspaces:
        if (ws.get("website_url") or "").rstrip("/") == website_url.rstrip("/"):
            return ws
    return None


async def _setup_workspace(
    autopilot: AutopilotService,
    repos: Repositories,
    spec: dict[str, Any],
) -> dict[str, Any]:
    url = spec["website_url"]
    existing = await _find_existing(repos, url)
    if existing:
        print(f"  [reuse] {url} → {existing['id']}")
        return {
            **spec,
            "workspace_id": existing["id"],
            "action": "reused",
            "status": existing.get("status", "unknown"),
        }

    workspace = await autopilot.create_workspace(
        website_url=url,
        name=spec["name"],
        competitors=spec["competitors"],
        mode="manual_review",
        cadence="weekly",
    )
    wid = workspace["workspace"]["id"]
    print(f"  [created] {url} → {wid}")
    return {
        **spec,
        "workspace_id": wid,
        "action": "created",
        "status": "setup",
    }


async def _analyze_workspace(
    autopilot: AutopilotService,
    repos: Repositories,
    spec: dict[str, Any],
) -> dict[str, Any]:
    wid = spec["workspace_id"]
    url = spec["website_url"]
    print(f"\n[{_ts()}] Analyzing {url} ({spec['vertical']}) …")

    ws = await repos.autopilot_workspaces.get(wid)
    if ws and ws.get("status") == "analyzed":
        print(f"  Already analyzed, skipping re-analysis.")
        return {**spec, "analysis_outcome": "already_analyzed", "error": None}

    try:
        result = await autopilot.analyze_workspace(wid, max_pages_per_site=5)
        ws_after = await repos.autopilot_workspaces.get(wid)
        status = (ws_after or {}).get("status", "unknown")

        pages = await _count_pages_for_workspace(repos, wid)
        recs = await repos.opportunity_recommendations.list_for_workspace(wid, limit=120)
        niche = await repos.workspace_niche_profiles.get(wid)

        print(f"  [{_ts()}] Done — status={status}, pages={pages}, recs={len(recs)}, niche={niche and niche.get('primary_niche')}")
        return {
            **spec,
            "analysis_outcome": "success",
            "final_status": status,
            "pages_scraped": pages,
            "recommendations": len(recs),
            "niche": niche and niche.get("primary_niche"),
            "error": None,
        }
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"  [{_ts()}] FAILED: {exc}")
        print(tb)
        return {
            **spec,
            "analysis_outcome": "failed",
            "error": str(exc),
            "traceback": tb,
        }


async def _count_pages_for_workspace(repos: Repositories, workspace_id: str) -> int:
    ws = await repos.autopilot_workspaces.get(workspace_id)
    if not ws:
        return 0
    job_id = ws.get("last_analysis_job_id")
    if not job_id:
        return 0
    pages = await repos.analysis_pages.list_for_job(job_id)
    return len(pages)


def _write_setup_doc(results: list[dict[str, Any]]) -> None:
    lines = [
        "# Cross-Vertical Workspace Setup",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "**Purpose:** Record workspace IDs and setup outcomes for the 4 cross-vertical validation sites.",
        "",
        "---",
        "",
        "## Workspace registry",
        "",
        "| Vertical | Site | Workspace ID | Created/Reused | Analysis outcome | Pages | Recs | Niche detected |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        pages = r.get("pages_scraped", "—")
        recs = r.get("recommendations", "—")
        niche = r.get("niche") or "—"
        lines.append(
            f"| {r['vertical']} | {r['website_url']} | `{r.get('workspace_id','—')}` "
            f"| {r.get('action','—')} | {r.get('analysis_outcome','—')} "
            f"| {pages} | {recs} | {niche} |"
        )

    lines += ["", "---", "", "## Competitor URLs used", ""]
    for r in results:
        lines.append(f"### {r['name']} ({r['vertical']})")
        lines.append(f"- **Site:** {r['website_url']}")
        for c in r.get("competitors", []):
            lines.append(f"- **Competitor:** {c}")
        lines.append("")

    lines += ["---", "", "## Failures and notes", ""]
    any_failures = False
    for r in results:
        if r.get("error"):
            any_failures = True
            lines.append(f"### {r['name']}")
            lines.append(f"- **Outcome:** {r.get('analysis_outcome')}")
            lines.append(f"- **Error:** `{r['error']}`")
            lines.append("")

    if not any_failures:
        lines.append("No failures.")

    out = DOCS_OUT / "CROSS_VERTICAL_WORKSPACE_SETUP.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSetup doc written to {out}")


async def main() -> None:
    print("=== Cross-vertical validation workspace setup ===")
    settings = get_settings()
    database = create_database(settings.database_url)
    repos = Repositories(database.session_factory)
    registry = build_provider_registry(settings)
    job_service = JobService(settings, registry, repos)
    website_analysis = WebsiteAnalysisService(
        registry.content_generation,
        repos,
        job_service,
        settings,
        registry.video,
    )
    market = MarketIntelligenceService(settings, repos)
    editorial = EditorialOpportunityService(settings, repos)
    autopilot = AutopilotService(
        settings=settings,
        repositories=repos,
        website_analysis=website_analysis,
        job_service=job_service,
        market_intelligence=market,
        editorial_opportunity=editorial,
    )
    _ = DemandIntelligenceService(settings, repos)

    # Step 1: create/find workspaces
    print("\n--- Step 1: Workspace setup ---")
    results: list[dict[str, Any]] = []
    for spec in WORKSPACES:
        result = await _setup_workspace(autopilot, repos, spec)
        results.append(result)

    # Step 2: analyze sequentially
    print("\n--- Step 2: Analysis ---")
    analyzed: list[dict[str, Any]] = []
    for spec in results:
        outcome = await _analyze_workspace(autopilot, repos, spec)
        analyzed.append(outcome)

    # Write setup doc
    _write_setup_doc(analyzed)

    # Summary
    print("\n=== Summary ===")
    for r in analyzed:
        print(f"  {r['vertical']:25s} {r['website_url']:45s} → {r.get('analysis_outcome','?')}")

    # Write raw results for inspection
    raw_out = DOCS_OUT / "cross_vertical_setup_raw.json"
    raw_out.write_text(
        json.dumps(analyzed, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nRaw results: {raw_out}")
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
