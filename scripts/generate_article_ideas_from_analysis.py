"""Generate AI article opportunities from existing website analysis (ideation service)."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from app.ai_opportunity_ideation.brief import build_opportunity_ideation_brief
from app.ai_opportunity_ideation.service import AIOpportunityIdeationService
from app.catalog.products import product_coverage
from app.config import get_settings
from app.db import create_database
from app.providers.registry import build_provider_registry
from app.repositories import Repositories

ROOT = Path(__file__).resolve().parents[1]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or "workspace"


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    brief = result.get("brief") or {}
    opportunities = result.get("opportunities") or []
    coverage = result.get("product_coverage") or {}
    catalog = brief.get("catalog_products") or brief.get("products") or []
    sitemap_meta = brief.get("sitemap_catalog") or {}

    lines = [
        f"# AI opportunity ideation — {brief.get('site_name') or brief.get('workspace_id')}",
        "",
        f"- Workspace: `{brief.get('workspace_id')}`",
        f"- URL: {brief.get('website_url') or 'n/a'}",
        f"- Niche: {brief.get('niche') or 'n/a'}",
        f"- Catalog products in brief: {len(catalog)}",
        f"- Opportunities generated: {len(opportunities)}",
        f"- Product coverage: {coverage.get('coverage_rate', 0)} ({len(coverage.get('mentioned') or [])}/{coverage.get('catalog_count', 0)})",
        "",
        "## Catalog products",
        "",
    ]
    if catalog:
        for product in catalog:
            lines.append(f"- {product}")
    else:
        lines.append("- _(none detected)_")

    lines.extend(["", "## Opportunities", ""])
    for index, row in enumerate(opportunities, start=1):
        headline = row.get("headline") or row.get("title") or "Untitled"
        abstract = row.get("abstract") or ""
        lines.append(f"{index}. **{headline}**")
        if abstract:
            lines.append(f"   {abstract}")

    missing = coverage.get("missing") or []
    if missing:
        lines.extend(["", "## Catalog products not mentioned", ""])
        for product in missing:
            lines.append(f"- {product}")

    if result.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in result["warnings"]:
            lines.append(f"- {warning}")

    if sitemap_meta:
        lines.extend(
            [
                "",
                "## Sitemap catalog",
                "",
                f"- Source: {sitemap_meta.get('source', 'n/a')}",
                f"- Product URLs: {sitemap_meta.get('product_urls_found', 0)}",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(
    *,
    workspace_id: str | None,
    analysis_job_id: str | None,
    min_ideas: int,
    max_ideas: int,
    dry_run: bool,
) -> dict[str, Any]:
    settings = get_settings()
    database = create_database(settings.database_url)
    repos = Repositories(database.session_factory)

    brief = await build_opportunity_ideation_brief(
        workspace_id=workspace_id,
        analysis_job_id=analysis_job_id,
        repositories=repos,
        settings=settings,
    )

    if dry_run:
        await database.close()
        return {"brief": brief, "opportunities": [], "warnings": ["dry_run"], "skipped": True}

    registry = build_provider_registry(settings)
    service = AIOpportunityIdeationService(
        settings,
        repos,
        openai_client=registry.content_generation.client if settings.openai_api_key else None,
    )
    ws_id = str(brief.get("workspace_id") or workspace_id or "")
    result = await service.generate_for_workspace(ws_id, force_refresh=True)
    opportunities = result.get("opportunities") or []
    coverage = product_coverage(opportunities, brief.get("catalog_products") or [])
    await database.close()
    return {
        **result,
        "brief": brief,
        "product_coverage": coverage,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI opportunity ideation from website analysis.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--workspace-id", dest="workspace_id", default=None)
    group.add_argument("--analysis-job-id", dest="analysis_job_id", default=None)
    parser.add_argument("--min", dest="min_ideas", type=int, default=40)
    parser.add_argument("--max", dest="max_ideas", type=int, default=60)
    parser.add_argument("--out-json", dest="out_json", default=None)
    parser.add_argument("--out-md", dest="out_md", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Build brief only; no OpenAI call.")
    args = parser.parse_args()

    settings = get_settings()
    min_ideas = max(args.min_ideas, settings.ai_opportunity_ideation_min_ideas)
    max_ideas = min(args.max_ideas, settings.ai_opportunity_ideation_max_ideas)
    if min_ideas > max_ideas:
        raise SystemExit("--min must be <= --max")

    result = asyncio.run(
        run(
            workspace_id=args.workspace_id,
            analysis_job_id=args.analysis_job_id,
            min_ideas=min_ideas,
            max_ideas=max_ideas,
            dry_run=args.dry_run,
        )
    )

    brief = result.get("brief") or {}
    ws_id = str(brief.get("workspace_id") or args.workspace_id or args.analysis_job_id or "unknown")
    slug = _slug(brief.get("site_name") or ws_id)

    out_json = Path(args.out_json or ROOT / "data" / "article-ideas" / f"{ws_id}.json")
    out_md = Path(args.out_md or ROOT / "docs" / "validation" / f"article_ideas_{slug}.md")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(out_md, result)

    if args.dry_run:
        print(f"Dry-run complete. JSON: {out_json}")
        print(f"Markdown: {out_md}")
        return

    opportunities = result.get("opportunities") or []
    print(f"Generated {len(opportunities)} opportunities.")
    print(f"Saved JSON: {out_json}")
    print(f"Saved markdown: {out_md}")


if __name__ == "__main__":
    main()
