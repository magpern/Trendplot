from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai_opportunity_ideation.recommendations import (
    IDEATION_ONLY_SOURCE_TYPE,
    ideation_opportunities_to_recommendation_rows,
    validate_ideation_only_recommendation_rows,
)
from app.analyze_flow import partial_rerun_step_keys
from app.config import Settings


def test_validate_ideation_only_rejects_legacy_source() -> None:
    with pytest.raises(ValueError, match="source_type"):
        validate_ideation_only_recommendation_rows(
            [{"source_type": "niche_profile", "title": "x"}],
        )


def test_ideation_rows_all_ai_opportunity_ideation_source() -> None:
    rows = ideation_opportunities_to_recommendation_rows(
        [
            {
                "id": "opp-1",
                "headline": "TB-500 Storage Guide",
                "abstract": "Lab storage overview.",
                "search_intent": "storage",
                "content_type": "guide",
                "recommendation_type": "create",
                "related_products": ["TB-500"],
            }
        ],
        analysis_job_id="job-1",
    )
    assert len(rows) == 1
    assert rows[0]["source_type"] == IDEATION_ONLY_SOURCE_TYPE


def test_partial_rerun_step_keys_ideation_only() -> None:
    settings = Settings(_env_file=None, ai_opportunity_ideation_enabled=True)
    assert settings.is_ai_ideation_only_mode
    keys = partial_rerun_step_keys("recommendations", settings)
    assert keys == ("ai_opportunity_ideation", "opportunity_ranking")


def test_article_idea_experiment_package_removed() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not (root / "app" / "article_idea_experiment").exists()
    if "app.article_idea_experiment" in sys.modules:
        del sys.modules["app.article_idea_experiment"]
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.article_idea_experiment")


def test_rerun_recommendations_uses_ideation_path() -> None:
    from app.autopilot.service import AutopilotService

    settings = Settings(_env_file=None, ai_opportunity_ideation_enabled=True)
    service = MagicMock()
    service.settings = settings
    service._rerun_ideation_recommendations = AsyncMock(
        return_value={"opportunity_intelligence": {"recommendations": [], "summary": {"total": 0}}},
    )

    async def _run() -> None:
        await AutopilotService.rerun_recommendations(service, "ws-1")

    asyncio.run(_run())
    service._rerun_ideation_recommendations.assert_awaited_once()
