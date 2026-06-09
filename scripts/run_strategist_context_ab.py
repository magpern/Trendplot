"""Compare strategist context Mode A (legacy wide) vs Mode B (compact Site Strategy Profile)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.ai_editorial_strategist.context import build_strategist_context
from app.config import get_settings
from app.db import create_database
from app.prompt_metrics import measure_context
from app.repositories import Repositories
from app.site_strategy_profile import build_legacy_strategist_context, resolve_site_strategy_profile

ROOT = Path(__file__).resolve().parents[1]
OFF_TOPIC = ("facebook", "adhesives", "internet", "bookshelf", "characteristics")


def _alignment_rate(ideas: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, float]:
    products = {str(p).lower() for p in profile.get("known_products") or []}
    categories = {str(c).lower() for c in profile.get("known_categories") or []}
    niche = str(profile.get("primary_niche") or "").lower()
    if not ideas:
        return {"product_alignment_rate": 0.0, "category_alignment_rate": 0.0, "niche_relevance_rate": 0.0, "off_topic_rate": 0.0}
    product_hits = category_hits = niche_hits = off_topic = 0
    for idea in ideas:
        blob = f"{idea.get('title')} {idea.get('topic')} {idea.get('entity')}".lower()
        if any(term in blob for term in OFF_TOPIC):
            off_topic += 1
        if any(p in blob for p in products if p):
            product_hits += 1
        if any(c in blob for c in categories if c):
            category_hits += 1
        if niche and niche in blob:
            niche_hits += 1
    total = len(ideas)
    return {
        "product_alignment_rate": round(product_hits / total, 4),
        "category_alignment_rate": round(category_hits / total, 4),
        "niche_relevance_rate": round(niche_hits / total, 4),
        "off_topic_rate": round(off_topic / total, 4),
    }


def _mock_ideas_from_profile(profile: dict[str, Any], *, limit: int = 25) -> list[dict[str, Any]]:
    """Deterministic stand-in when OpenAI is unavailable — product-anchored titles."""
    ideas: list[dict[str, Any]] = []
    products = list(profile.get("known_products") or [])[:limit]
    for product in products:
        ideas.append({"title": f"{product} Research Overview", "topic": product, "entity": product})
        if len(ideas) >= limit:
            break
    for product in products[:5]:
        ideas.append({"title": f"What Is {product}?", "topic": product, "entity": product})
    ideas.append({"title": "Research Peptide Storage Guide", "topic": "peptide storage", "entity": "storage"})
    ideas.append({"title": "Peptide Reconstitution Guide", "topic": "reconstitution", "entity": "reconstitution"})
    return ideas[:limit]


async def run_ab(*, workspace_id: str, live: bool) -> dict[str, Any]:
    settings = get_settings()
    database = create_database(settings.database_url)
    repos = Repositories(database.session_factory)

    workspace = await repos.autopilot_workspaces.get(workspace_id)
    understanding = await repos.site_understanding.latest_for_workspace(workspace_id)
    niche = await repos.workspace_niche_profiles.get(workspace_id)
    inventory = await repos.workspace_content_inventory.list_for_workspace(workspace_id, limit=500)
    coverage = await repos.content_coverage.list_for_workspace(workspace_id, limit=200)
    competitors = await repos.competitor_snapshots.list_for_workspace(workspace_id, limit=20)

    profile = resolve_site_strategy_profile(
        understanding=understanding,
        niche_profile=niche,
        content_inventory=inventory,
    )
    mode_a = build_legacy_strategist_context(
        workspace=workspace,
        understanding=understanding,
        niche_profile=niche,
        content_inventory=inventory,
        coverage=coverage,
        competitor_snapshots=competitors,
        max_ideas=25,
    )
    mode_b = build_strategist_context(
        workspace=workspace,
        understanding=understanding,
        niche_profile=niche,
        content_inventory=inventory,
        coverage=coverage,
        competitor_snapshots=competitors,
        max_ideas=25,
    )

    report: dict[str, Any] = {
        "workspace_id": workspace_id,
        "website_url": workspace.get("website_url") if workspace else "",
        "site_strategy_profile": profile,
        "context_sizes": {
            "mode_a_legacy": measure_context("legacy_strategist", mode_a),
            "mode_b_compact": measure_context("compact_profile", mode_b),
        },
        "reduction_pct": round(
            100
            * (
                1
                - measure_context("compact_profile", mode_b)["estimated_tokens"]
                / max(1, measure_context("legacy_strategist", mode_a)["estimated_tokens"])
            ),
            1,
        ),
    }

    if live and settings.openai_api_key:
        from app.ai_editorial_strategist.service import AIEditorialStrategistService
        from app.providers.registry import build_provider_registry

        registry = build_provider_registry(settings)
        svc = AIEditorialStrategistService(settings, repos, registry.content_generation.client)
        # Mode B only live call — Mode A measured by context size
        mode_b_live = await svc.generate_for_workspace(
            workspace_id,
            workspace=workspace,
            understanding=understanding,
            niche_profile=niche,
            content_inventory=inventory,
            coverage=coverage,
            competitor_snapshots=competitors,
        )
        ideas = mode_b_live.get("ideas") or []
        report["mode_b_live_ideas"] = ideas[:25]
        report["mode_b_live_metrics"] = _alignment_rate(ideas, profile)
    else:
        mock = _mock_ideas_from_profile(profile, limit=25)
        report["mode_b_mock_ideas"] = mock
        report["mode_b_mock_metrics"] = _alignment_rate(mock, profile)

    await database.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategist context A/B experiment")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--live", action="store_true", help="Call OpenAI for Mode B ideas")
    parser.add_argument("--out", default=str(ROOT / "docs" / "analysis" / "STRATEGIST_CONTEXT_AB.json"))
    args = parser.parse_args()
    report = asyncio.run(run_ab(workspace_id=args.workspace_id, live=args.live))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
