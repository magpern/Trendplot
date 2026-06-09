"""Generate a fixed-size ideation sample and print category distribution."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._analyze_ideation_bias import classify_ideation_opportunity, summarize_category_distribution

WORKSPACE_ID = "48c761a6-2698-4a1d-8022-f23bfd1d5cb6"
SAMPLE_SIZE = 25


async def main() -> None:
    from app.ai_opportunity_ideation.service import AIOpportunityIdeationService
    from app.config import get_settings
    from app.db import create_database
    from app.providers.registry import build_provider_registry
    from app.repositories import Repositories

    settings = get_settings()
    settings.ai_opportunity_ideation_min_ideas = SAMPLE_SIZE
    settings.ai_opportunity_ideation_max_ideas = SAMPLE_SIZE
    settings.ai_opportunity_ideation_batch_size = SAMPLE_SIZE

    database = create_database(settings.database_url)
    repos = Repositories(database.session_factory)
    registry = build_provider_registry(settings)
    service = AIOpportunityIdeationService(
        settings,
        repos,
        openai_client=registry.content_generation.client if settings.openai_api_key else None,
    )
    result = await service.generate_for_workspace(WORKSPACE_ID, force_refresh=True)
    await database.close()

    opps = result.get("opportunities") or []
    summary = summarize_category_distribution(opps)
    print(json.dumps({"total": len(opps), "summary": summary, "warnings": result.get("warnings")}, indent=2))
    for index, row in enumerate(opps[:20], start=1):
        category = classify_ideation_opportunity(row)
        print(f"{index}. [{category}] {row.get('headline')}")


if __name__ == "__main__":
    asyncio.run(main())
