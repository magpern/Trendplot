"""Trace recommendation lineage for specific topics."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.db import create_database
from app.repositories import Repositories

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS = (
    "Bookshelf",
    "Adhesives",
    "Facebook",
    "BPC-157",
    "GHK-CU",
    "MOTS-C",
    "Kisspeptin",
)


def _match_topic(rec: dict[str, Any], topic: str) -> bool:
    blob = f"{rec.get('title')} {rec.get('topic')} {rec.get('target_keyword')}".lower()
    return topic.lower() in blob


async def trace_workspace(workspace_id: str, topics: list[str]) -> dict[str, Any]:
    settings = get_settings()
    database = create_database(settings.database_url)
    repos = Repositories(database.session_factory)
    workspace = await repos.autopilot_workspaces.get(workspace_id)
    job_id = str(workspace.get("last_analysis_job_id") or "") if workspace else ""
    recommendations = await repos.opportunity_recommendations.list_for_workspace(workspace_id, limit=200)
    opportunities = await repos.opportunities.list_for_job(job_id, limit=500) if job_id else []
    strategist_ideas = await repos.ai_editorial_strategist_ideas.list_for_workspace(workspace_id, limit=200)
    editorial = await repos.editorial_opportunity_concepts.list_finalists_for_workspace(workspace_id, limit=200)
    market = await repos.market_opportunity_candidates.list_for_workspace(workspace_id, limit=200)
    understanding = await repos.site_understanding.latest_for_workspace(workspace_id)
    profile = (understanding or {}).get("source", {}).get("strategy_profile") if understanding else None

    traces: dict[str, Any] = {}
    for topic in topics:
        rec_hits = [r for r in recommendations if _match_topic(r, topic)]
        opp_hits = [o for o in opportunities if _match_topic(o, topic)]
        strat_hits = [i for i in strategist_ideas if _match_topic(i, topic)]
        eog_hits = [e for e in editorial if _match_topic(e, topic)]
        market_hits = [m for m in market if _match_topic(m, topic)]
        traces[topic] = {
            "final_recommendations": [{"id": r.get("id"), "title": r.get("title"), "action": r.get("action"), "source_type": r.get("source_type"), "score": r.get("score")} for r in rec_hits[:5]],
            "analysis_opportunities": [{"id": o.get("id"), "title": o.get("title")} for o in opp_hits[:5]],
            "strategist_ideas": [{"title": i.get("title"), "entity": i.get("entity")} for i in strat_hits[:5]],
            "editorial_concepts": [{"title": e.get("title")} for e in eog_hits[:5]],
            "market_candidates": [{"topic": m.get("topic"), "title": m.get("title")} for m in market_hits[:5]],
            "reached_final_queue": bool(rec_hits),
            "likely_source": _infer_source(rec_hits, strat_hits, eog_hits, market_hits, opp_hits),
        }

    report = {
        "workspace_id": workspace_id,
        "website_url": workspace.get("website_url") if workspace else "",
        "analysis_job_id": job_id,
        "site_strategy_profile_products": (profile or {}).get("known_products") if isinstance(profile, dict) else [],
        "traces": traces,
    }
    await database.close()
    return report


def _infer_source(rec, strat, eog, market, opp) -> str:
    if not rec:
        return "not_in_final_queue"
    source = str((rec[0] or {}).get("source_type") or "")
    if source:
        return source
    if strat:
        return "ai_editorial_strategist (inferred)"
    if eog:
        return "editorial_opportunity (inferred)"
    if market:
        return "market_intelligence (inferred)"
    if opp:
        return "website_analysis_opportunity_engine (inferred)"
    return "opportunity_intelligence_unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--topics", nargs="*", default=list(DEFAULT_TOPICS))
    parser.add_argument("--out", default=str(ROOT / "docs" / "analysis" / "RECOMMENDATION_LINEAGE_TRACE.json"))
    args = parser.parse_args()
    report = asyncio.run(trace_workspace(args.workspace_id, list(args.topics)))
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
