from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analyze_ui import ANALYZE_WEBSITE_HTML
from app.catalog.products import infer_products_from_text
from app.manual_recommendations.duplicates import find_similar_items
from app.manual_recommendations.mapper import MANUAL_SOURCE_TYPE, manual_recommendation_to_row
from app.manual_recommendations.safety import validate_enrichment_safety
from app.manual_recommendations.service import ManualRecommendationService
from app.prompts.prompt_registry import get_default_prompt_registry
from app.services.jobs import _opportunity_context_json


def _workspace() -> dict[str, Any]:
    return {"id": "ws-1", "website_url": "https://example.com", "last_analysis_job_id": "job-1"}


def _manual_enriched() -> dict[str, Any]:
    return {
        "id": "manual-1",
        "workspace_id": "ws-1",
        "status": "enriched",
        "raw_headline": "BPC-157 and TB-500 are often discussed together. Why?",
        "raw_notes": "Explain literature themes and differences. Avoid combined-use advice.",
        "enhanced_headline": "Why BPC-157 and TB-500 Are Often Discussed Together in Research Literature",
        "abstract": "A research-focused relationship article explaining overlapping themes and evidence boundaries.",
        "search_intent": "product_relationship",
        "content_type": "relationship",
        "recommendation_type": "create",
        "related_products": ["BPC-157", "TB-500"],
        "related_topics": ["tissue repair research", "peptide comparison"],
        "target_audience": "Research readers comparing related peptide topics",
        "priority_reason": "Captures a common cross-product question.",
        "safety_notes": [
            "Research-use-only framing; no combined-use recommendations; no dosing or treatment guidance."
        ],
        "duplicate_warnings": [],
    }


def _service_with_mocks(
    *,
    workspace: dict[str, Any] | None = None,
    manual: dict[str, Any] | None = None,
    openai_client: Any | None = None,
) -> tuple[ManualRecommendationService, MagicMock]:
    repositories = MagicMock()
    repositories.autopilot_workspaces.get = AsyncMock(return_value=workspace or _workspace())
    repositories.manual_recommendations.create = AsyncMock(
        return_value={
            "id": "manual-1",
            "workspace_id": "ws-1",
            "status": "draft",
            "raw_headline": "BPC-157 and TB-500 are often discussed together. Why?",
            "raw_notes": "",
            "selected_products": [],
        }
    )
    repositories.manual_recommendations.get = AsyncMock(return_value=manual or _manual_enriched())
    repositories.manual_recommendations.update = AsyncMock(side_effect=lambda _id, **kwargs: {**(manual or _manual_enriched()), **kwargs})
    repositories.manual_recommendations.list_for_workspace = AsyncMock(return_value=[])
    repositories.opportunity_recommendations.list_for_workspace = AsyncMock(return_value=[])
    repositories.opportunity_recommendations.create_for_workspace = AsyncMock(
        return_value={"id": "rec-1", "title": "Queued manual rec", "source_type": MANUAL_SOURCE_TYPE, "metadata": {}}
    )
    repositories.opportunity_recommendations.get_by_id = AsyncMock(return_value=None)
    repositories.opportunity_recommendations.update_status = AsyncMock(return_value={"status": "archived"})
    service = ManualRecommendationService(MagicMock(), repositories, openai_client=openai_client)
    return service, repositories


def test_create_manual_recommendation() -> None:
    service, repositories = _service_with_mocks()

    async def _run() -> dict[str, Any]:
        return await service.create_manual(
            "ws-1",
            raw_headline="BPC-157 and TB-500",
            raw_notes="",
        )

    manual = asyncio.run(_run())
    repositories.manual_recommendations.create.assert_awaited_once()
    assert manual["status"] == "draft"


def test_enrich_manual_recommendation_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    service, repositories = _service_with_mocks(
        manual={
            "id": "manual-1",
            "workspace_id": "ws-1",
            "status": "draft",
            "raw_headline": "BPC-157 and TB-500 are often discussed together. Why?",
            "raw_notes": "Explain literature themes.",
            "selected_products": ["BPC-157", "TB-500"],
            "content_type_hint": "relationship",
        }
    )
    monkeypatch.setattr(
        "app.manual_recommendations.service.build_opportunity_ideation_brief",
        AsyncMock(return_value={"catalog_products": ["BPC-157", "TB-500"]}),
    )

    async def _run() -> dict[str, Any]:
        return await service.enrich_manual("ws-1", "manual-1")

    enriched = asyncio.run(_run())
    repositories.manual_recommendations.update.assert_awaited()
    assert enriched["status"] == "enriched"
    assert enriched["related_products"] == ["BPC-157", "TB-500"]
    assert enriched["content_type"] == "relationship"


def test_product_inference_from_selected_products(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = _service_with_mocks(
        manual={
            "id": "manual-1",
            "workspace_id": "ws-1",
            "status": "draft",
            "raw_headline": "Peptide comparison idea",
            "raw_notes": "",
            "selected_products": ["BPC-157", "TB-500"],
        }
    )
    monkeypatch.setattr(
        "app.manual_recommendations.service.build_opportunity_ideation_brief",
        AsyncMock(return_value={"catalog_products": ["BPC-157", "TB-500"]}),
    )

    async def _run() -> dict[str, Any]:
        return await service.enrich_manual("ws-1", "manual-1")

    enriched = asyncio.run(_run())
    assert enriched["related_products"] == ["BPC-157", "TB-500"]


def test_product_inference_from_raw_headline() -> None:
    catalog = ["BPC-157", "TB-500", "Tirzepatide"]
    found = infer_products_from_text("BPC-157 and TB-500 are often discussed together. Why?", catalog)
    assert found == ["BPC-157", "TB-500"]


def test_safety_guard_blocks_medical_and_combined_use_phrasing() -> None:
    violations = validate_enrichment_safety(
        {
            "headline": "BPC-157 dosing protocol for recovery",
            "abstract": "How to treat injuries with a combined stack.",
            "priority_reason": "Users should combine BPC-157 and TB-500 for best results.",
            "safety_notes": [],
            "related_topics": [],
        }
    )
    assert "dosing" not in violations
    assert "treatment" in violations
    assert "combined_use_recommendation" in violations


def test_queue_enriched_manual_recommendation() -> None:
    service, repositories = _service_with_mocks()

    async def _run() -> dict[str, Any]:
        return await service.queue_manual("ws-1", "manual-1")

    result = asyncio.run(_run())
    repositories.opportunity_recommendations.create_for_workspace.assert_awaited_once()
    assert result["recommendation"]["id"] == "rec-1"
    assert result["requires_confirmation"] is False


def test_article_generation_receives_manual_recommendation_metadata() -> None:
    row = manual_recommendation_to_row(_manual_enriched(), analysis_job_id="job-1")
    metadata = row["metadata"]
    assert row["source_type"] == MANUAL_SOURCE_TYPE
    assert metadata["manual_source"] is True
    assert metadata["article_brief"]["source"] == "manual_recommendation"
    assert metadata["article_brief"]["raw_notes"]
    assert metadata["article_brief"]["related_products"] == ["BPC-157", "TB-500"]

    context_json = _opportunity_context_json(metadata["article_brief"])
    payload = json.loads(context_json)
    assert payload["source"] == "manual_recommendation"
    assert payload["raw_notes"]
    assert payload["science_focus"] is True


def test_duplicate_warning_on_queue() -> None:
    service, repositories = _service_with_mocks(
        manual={**_manual_enriched(), "duplicate_warnings": [{"type": "recommendation", "title": "Similar headline"}]}
    )
    repositories.opportunity_recommendations.list_for_workspace = AsyncMock(
        return_value=[{"id": "rec-old", "title": "Why BPC-157 and TB-500 Are Discussed Together", "topic": "bpc tb"}]
    )

    async def _run() -> dict[str, Any]:
        return await service.queue_manual("ws-1", "manual-1", allow_duplicates=False)

    result = asyncio.run(_run())
    assert result["requires_confirmation"] is True
    assert result["duplicate_warnings"]


def test_duplicate_detection_helper() -> None:
    matches = find_similar_items(
        "Why BPC-157 and TB-500 Are Often Discussed Together",
        recommendations=[
            {"id": "1", "title": "BPC-157 and TB-500 research relationship overview"},
            {"id": "2", "title": "Unrelated peptide FAQ"},
        ],
    )
    assert matches
    assert matches[0]["type"] == "recommendation"


def test_analyze_ui_manual_modal_renders() -> None:
    assert "+ Manual idea" in ANALYZE_WEBSITE_HTML
    assert "manual-idea-modal" in ANALYZE_WEBSITE_HTML
    assert "Improve with AI" in ANALYZE_WEBSITE_HTML
    assert "Add to recommendations" in ANALYZE_WEBSITE_HTML
    assert "A similar recommendation or article may already exist." in ANALYZE_WEBSITE_HTML
    assert "manual_recommendation" in ANALYZE_WEBSITE_HTML
    assert "Search products to add" in ANALYZE_WEBSITE_HTML
    assert "AI will infer products from your headline" in ANALYZE_WEBSITE_HTML
    assert "manual-product-suggestions" in ANALYZE_WEBSITE_HTML
    assert 'name="manual-product"' not in ANALYZE_WEBSITE_HTML


def test_manual_recommendation_row_appears_in_mapper_list_shape() -> None:
    row = manual_recommendation_to_row(_manual_enriched())
    assert row["action"] == "create"
    assert row["title"].startswith("Why BPC-157")
    assert row["metadata"]["source_label"] == "Manual · AI-enhanced"


def test_archiving_removes_from_active_queue() -> None:
    service, repositories = _service_with_mocks(
        manual={**_manual_enriched(), "status": "queued", "recommendation_id": "rec-1"}
    )

    async def _run() -> dict[str, Any]:
        return await service.archive_manual("ws-1", "manual-1")

    archived = asyncio.run(_run())
    repositories.opportunity_recommendations.update_status.assert_awaited_once_with(
        "rec-1",
        workspace_id="ws-1",
        status="archived",
    )
    assert archived["status"] == "archived"


def test_manual_enrichment_prompt_constraints() -> None:
    rendered = get_default_prompt_registry().render(
        "manual_recommendation_enrichment",
        {
            "workspace_brief_json": "{}",
            "raw_headline": "BPC-157 and TB-500",
            "raw_notes": "Why together?",
            "selected_products_json": "[]",
            "content_type_hint": "relationship",
            "target_audience_hint": "Researchers",
        },
    )
    text = str(rendered.text).lower()
    assert "no dosing" in text or "do not" in text
    assert "related_products" in text
    assert "relationship" in text


def test_bpc_tb500_fallback_enrichment_shape() -> None:
    service, _ = _service_with_mocks(openai_client=None)
    payload, warnings = asyncio.run(
        service._call_enrichment_model(
            brief={"catalog_products": ["BPC-157", "TB-500"]},
            raw_headline="BPC-157 and TB-500 are often discussed together. Why?",
            raw_notes="Explain literature themes. Avoid combined-use advice.",
            selected_products=["BPC-157", "TB-500"],
            content_type_hint="relationship",
            target_audience_hint="Research readers",
        )
    )
    assert payload["content_type"] == "relationship"
    assert payload["related_products"] == ["BPC-157", "TB-500"]
    blob = f"{payload.get('headline', '')} {payload.get('abstract', '')} {payload.get('priority_reason', '')}".lower()
    assert "dose" not in blob
    assert "protocol" not in blob
    assert "combine" not in blob or "do not recommend" in " ".join(payload.get("safety_notes") or []).lower()
    assert "fallback_no_openai_client" in warnings
