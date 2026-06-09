"""
Export opportunity quality validation snapshots and automated metrics.
Does not modify intelligence pipelines.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
RUN_ID = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
OUT = ROOT / "docs" / "validation" / "runs" / RUN_ID

NAV_BLOCKLIST = re.compile(
    r"\b(shop|store|contact|why us|product variations|products|cart|checkout|privacy|terms|login|home|about us)\b",
    re.I,
)
BANNED_TITLE_PATTERN = re.compile(r":\s*questions answered\s*$", re.I)
OFF_TOPIC_PATTERN = re.compile(r"\b(facebook|adhesives|internet|characteristics)\b", re.I)

COHORT_URL_PATTERNS = (
    "example-lab",
    "plausible",
    "tortuga",
    "pragmatic",
)

TOPIC_CLASS_HINTS = {
    "glossary": re.compile(r"\bwhat is\b|definition|glossary", re.I),
    "comparison": re.compile(r"\bvs\b|comparison|alternatives|compare", re.I),
    "trend": re.compile(r"\btrend\b|what changed|rising|news", re.I),
    "educational": re.compile(r"\bguide\b|explainer|beginner|how to|faq", re.I),
    "ecosystem": re.compile(r"\bcompetitor\b|ecosystem|landscape|entity", re.I),
}


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def _off_topic_rate(recommendations: list[dict[str, Any]], *, action: str = "create") -> float:
    filtered = [r for r in recommendations if str(r.get("action") or "").lower() == action]
    if not filtered:
        return 0.0
    hits = sum(1 for r in filtered if OFF_TOPIC_PATTERN.search(f"{r.get('title')} {r.get('topic')}"))
    return round(hits / len(filtered), 4)


def _product_category_alignment_rate(recommendations: list[dict[str, Any]], niche: dict[str, Any] | None) -> float:
    products = {str(p).lower() for p in (niche or {}).get("known_products") or [] if str(p).strip()}
    categories = {str(c).lower() for c in (niche or {}).get("known_categories") or [] if str(c).strip()}
    primary = str((niche or {}).get("primary_niche") or "").lower()
    creates = [r for r in recommendations if str(r.get("action") or "").lower() == "create"]
    if not creates:
        return 0.0
    aligned = 0
    for rec in creates:
        blob = f"{rec.get('title')} {rec.get('topic')}".lower()
        if primary and primary in blob:
            aligned += 1
            continue
        if any(p in blob for p in products):
            aligned += 1
            continue
        if any(c in blob for c in categories):
            aligned += 1
    return round(aligned / len(creates), 4)


def _ai_reviewed_count(recommendations: list[dict[str, Any]]) -> int:
    count = 0
    for rec in recommendations:
        meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
        if isinstance(meta.get("ai_review"), dict):
            count += 1
    return count


def _cohort_workspace(url: str) -> bool:
    lower = (url or "").lower()
    return any(pattern in lower for pattern in COHORT_URL_PATTERNS)


def _topic_class(rec: dict[str, Any]) -> str:
    action = str(rec.get("action") or "").lower()
    if action == "refresh":
        return "refresh"
    if action == "expand":
        return "expand"
    if action == "merge":
        return "merge"
    if action == "monitor":
        return "monitor"
    blob = f"{rec.get('title')} {rec.get('topic')} {rec.get('explanation')}"
    for name, pattern in TOPIC_CLASS_HINTS.items():
        if pattern.search(blob):
            return name
    return "other"


def _failure_tags(rec: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    topic = f"{rec.get('topic')} {rec.get('title')}"
    if NAV_BLOCKLIST.search(topic):
        tags.append("NAV_LABEL")
    if BANNED_TITLE_PATTERN.search(str(rec.get("title") or "")):
        tags.append("TEMPLATE_TITLE")
    source = str(rec.get("source_type") or "")
    action = str(rec.get("action") or "").lower()
    evidence = rec.get("evidence") or []
    meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
    if action == "create" and source not in {"editorial_opportunity", "market_intelligence", "trend_signal", "competitor", "demand_observation"}:
        if source in {"niche_profile", "existing_opportunity", "coverage"}:
            tags.append("WEBSITE_LED_CREATE")
    if action == "create" and not rec.get("has_external_evidence") and not meta.get("market_candidate_id"):
        if not evidence:
            tags.append("WEAK_EVIDENCE")
    expl = str(rec.get("explanation") or "")
    if len(expl) < 20 and action == "create":
        tags.append("GENERIC_FILLER")
    return tags


def _explainability_pass(rec: dict[str, Any]) -> dict[str, bool]:
    meta = rec.get("metadata") if isinstance(rec.get("metadata"), dict) else {}
    action = str(rec.get("action") or "").lower()
    evidence = rec.get("evidence") or []
    return {
        "why_matters": bool(rec.get("explanation") or (rec.get("reasons") and len(rec.get("reasons")) >= 2)),
        "evidence": bool(evidence or rec.get("demand_summary") or meta.get("market_candidate_id")),
        "audience": bool(meta.get("audience") or rec.get("audience_relevance", 0) >= 0.6),
        "why_now": bool(meta.get("why_now") or _topic_class(rec) in {"trend", "news_theme"} or action != "create"),
        "site_fit": bool(rec.get("business_relevance") or rec.get("niche_relevance") or rec.get("coverage_id")),
    }


async def _refresh_pipeline(
    autopilot: AutopilotService,
    repos: Repositories,
    workspace_id: str,
    *,
    refresh_market: bool,
    market_enabled: bool,
) -> None:
    ws = await repos.autopilot_workspaces.get(workspace_id)
    if not ws or ws.get("status") not in {"analyzed", "planned", "active"}:
        return
    if refresh_market and market_enabled:
        await autopilot.refresh_market_intelligence(workspace_id)
    else:
        await autopilot.refresh_opportunity_intelligence(workspace_id, create_event=False)


async def main() -> None:
    global settings
    import sys

    argv = sys.argv
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

    OUT.mkdir(parents=True, exist_ok=True)
    workspaces = await repos.autopilot_workspaces.list_recent(limit=100)
    registry: list[dict[str, Any]] = []
    cohort_rows: list[dict[str, Any]] = []

    refresh_market = "--refresh" in argv
    ab_strategist_reviewer = "--ab-strategist-reviewer" in argv
    if ab_strategist_reviewer:
        global OUT
        OUT = ROOT / "docs" / "validation" / "runs" / RUN_ID / "strategist_reviewer_ab"

    for ws in workspaces:
        wid = ws["id"]
        url = ws.get("website_url") or ""
        if ab_strategist_reviewer and not _cohort_workspace(url):
            continue
        if refresh_market:
            try:
                await _refresh_pipeline(
                    autopilot,
                    repos,
                    wid,
                    refresh_market=True,
                    market_enabled=settings.market_intelligence_enabled,
                )
            except Exception as exc:
                print(f"refresh failed {wid}: {exc}")
        ws_dir = OUT / wid
        ws_dir.mkdir(parents=True, exist_ok=True)

        niche = await repos.workspace_niche_profiles.get(wid)
        market_run = await repos.market_intelligence_runs.latest_for_workspace(wid)
        signals = await repos.market_signals.list_for_workspace(wid, limit=500)
        clusters = await repos.market_topic_clusters.top_for_workspace(wid, limit=50)
        market_candidates = await repos.market_opportunity_candidates.list_for_workspace(wid, limit=500)
        editorial_run = await repos.editorial_generation_runs.latest_for_workspace(wid)
        editorial_concepts = await repos.editorial_opportunity_concepts.list_for_workspace(wid, limit=500)
        editorial_finalists = await repos.editorial_opportunity_concepts.list_finalists_for_workspace(wid, limit=200)
        strategist_ideas = await repos.ai_editorial_strategist_ideas.list_for_workspace(wid, limit=200)
        recommendations = await repos.opportunity_recommendations.list_for_workspace(wid, limit=120)

        snapshots = {
            "workspace": ws,
            "niche_profile": niche,
            "market_run": market_run,
            "market_signals": signals,
            "market_clusters": clusters,
            "market_candidates": market_candidates,
            "editorial_run": editorial_run,
            "editorial_concepts": editorial_concepts,
            "editorial_finalists": editorial_finalists,
            "strategist_ideas": strategist_ideas,
            "recommendations": recommendations,
        }
        for name, payload in snapshots.items():
            (ws_dir / f"{name}.json").write_text(
                json.dumps(payload, indent=2, default=_json_default),
                encoding="utf-8",
            )

        top25 = sorted(recommendations, key=lambda r: float(r.get("score") or 0), reverse=True)[:25]
        analyzed: list[dict[str, Any]] = []
        tag_counter: Counter[str] = Counter()
        class_counter: Counter[str] = Counter()
        explain_pass = 0

        for i, rec in enumerate(top25, 1):
            tags = _failure_tags(rec)
            tag_counter.update(tags)
            tc = _topic_class(rec)
            class_counter[tc] += 1
            exp = _explainability_pass(rec)
            action = str(rec.get("action") or "").lower()
            need = 4 if action == "create" else 3
            if sum(1 for v in exp.values() if v) >= need:
                explain_pass += 1
            analyzed.append(
                {
                    "rank": i,
                    "title": rec.get("title"),
                    "topic": rec.get("topic"),
                    "action": rec.get("action"),
                    "source_type": rec.get("source_type"),
                    "score": rec.get("score"),
                    "failure_tags": tags,
                    "topic_class": tc,
                    "explainability": exp,
                }
            )

        creates = [r for r in top25 if str(r.get("action")).lower() == "create"]
        market_led = sum(
            1 for r in creates if r.get("source_type") in {"market_intelligence", "editorial_opportunity"}
        )
        junk = sum(1 for r in analyzed if any(t in r["failure_tags"] for t in ("NAV_LABEL", "CATEGORY_LABEL", "GENERIC_FILLER")))

        row = {
            "workspace_id": wid,
            "website_url": url,
            "primary_niche": (niche or {}).get("primary_niche"),
            "counts": {
                "market_signals": len(signals),
                "market_clusters": len(clusters),
                "market_candidates": len(market_candidates),
                "editorial_concepts": len(editorial_concepts),
                "editorial_finalists": len(editorial_finalists),
                "recommendations": len(recommendations),
                "top25": len(top25),
            },
            "funnel": {
                "concepts_per_recommendation": round(len(editorial_concepts) / max(len(recommendations), 1), 2),
                "finalists_per_recommendation": round(len(editorial_finalists) / max(len(recommendations), 1), 2),
                "candidates_per_recommendation": round(len(market_candidates) / max(len(recommendations), 1), 2),
                "signals_per_candidate": round(len(signals) / max(len(market_candidates), 1), 2),
            },
            "top25_metrics": {
                "market_led_create_share": round(market_led / max(len(creates), 1), 2) if creates else 0,
                "junk_rate": round(junk / max(len(top25), 1), 2),
                "explainability_pass_rate": round(explain_pass / max(len(top25), 1), 2),
                "product_category_alignment_rate": _product_category_alignment_rate(recommendations, niche),
                "off_topic_create_rate": _off_topic_rate(recommendations, action="create"),
                "weird_create_count": sum(
                    1
                    for r in creates
                    if OFF_TOPIC_PATTERN.search(f"{r.get('title')} {r.get('topic')}")
                ),
                "ai_reviewed_count": _ai_reviewed_count(recommendations),
                "topic_classes": dict(class_counter),
                "failure_tags": dict(tag_counter),
            },
            "ai_layers": {
                "strategist_enabled": settings.ai_editorial_strategist_enabled,
                "reviewer_enabled": settings.ai_recommendation_review_enabled,
                "strategist_ideas": len(strategist_ideas),
            },
            "market_intelligence_enabled": settings.market_intelligence_enabled,
        }
        cohort_rows.append(row)
        (ws_dir / "top25_analysis.json").write_text(json.dumps(analyzed, indent=2), encoding="utf-8")
        (ws_dir / "metrics.json").write_text(json.dumps(row, indent=2), encoding="utf-8")

        registry.append(
            {
                "workspace_id": wid,
                "website_url": url,
                "primary_niche": (niche or {}).get("primary_niche"),
                "status": ws.get("status"),
            }
        )

    (OUT / "workspace_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    (OUT / "cohort_summary.json").write_text(json.dumps(cohort_rows, indent=2), encoding="utf-8")

    report_lines = [
        f"# Validation Run Report — {RUN_ID}",
        "",
        "## Cohort overview",
        "",
        f"- Workspaces evaluated: **{len(cohort_rows)}**",
        f"- Market intelligence enabled (env): **{settings.market_intelligence_enabled}**",
        "",
        "## Per-workspace metrics",
        "",
        "| URL | Niche | Recs | Concepts | Finalists | MI CREATE % | Junk % | Explain % |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in cohort_rows:
        m = row["top25_metrics"]
        report_lines.append(
            f"| {row['website_url'][:40]} | {row.get('primary_niche') or '—'} | "
            f"{row['counts']['recommendations']} | {row['counts']['editorial_concepts']} | "
            f"{row['counts']['editorial_finalists']} | "
            f"{m['market_led_create_share']*100:.0f}% | {m['junk_rate']*100:.0f}% | "
            f"{m['explainability_pass_rate']*100:.0f}% |"
        )

    report_lines.extend(
        [
            "",
            "## Top issues (automated tags in top 25)",
            "",
        ]
    )
    all_tags: Counter[str] = Counter()
    for row in cohort_rows:
        all_tags.update(row["top25_metrics"]["failure_tags"])
    for tag, count in all_tags.most_common():
        report_lines.append(f"- `{tag}`: {count}")

    report_lines.extend(
        [
            "",
            "## Sample recommendations (rank 1–5 per workspace)",
            "",
        ]
    )
    for row in cohort_rows:
        wid = row["workspace_id"]
        analysis = json.loads((OUT / wid / "top25_analysis.json").read_text(encoding="utf-8"))
        report_lines.append(f"### {row['website_url']}")
        for item in analysis[:5]:
            tags = ", ".join(item["failure_tags"]) or "—"
            report_lines.append(
                f"- **#{item['rank']}** [{item['action']}] {item['title']} "
                f"(`{item['source_type']}`, class={item['topic_class']}, tags={tags})"
            )
        report_lines.append("")

    report_lines.extend(
        [
            "## Next steps (human rubric)",
            "",
            "1. Open each `top25_analysis.json` and score dimensions 1–5 per validation plan.",
            "2. Compare junk_rate and market_led_create_share against success thresholds.",
            "3. Do not add intelligence layers until publishable_rate ≥ 60% on treatment cohort.",
            "",
        ]
    )

    (OUT / "REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    await database.close()
    print(f"Validation export written to: {OUT}")
    print(f"Workspaces: {len(cohort_rows)}")


if __name__ == "__main__":
    asyncio.run(main())
