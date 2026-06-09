from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from uuid import uuid4

from app.ai_opportunity_ideation.brief import build_opportunity_ideation_brief
from app.catalog.products import infer_products_from_text
from app.config import Settings
from app.manual_recommendations.duplicates import find_similar_items
from app.manual_recommendations.mapper import MANUAL_SOURCE_TYPE, manual_recommendation_to_row
from app.manual_recommendations.safety import default_safety_notes, validate_enrichment_safety
from app.prompts.context_json import context_as_json
from app.prompts.prompt_registry import get_default_prompt_registry
from app.providers.model_router import uses_max_completion_tokens
from app.repositories import Repositories

logger = logging.getLogger("trendplot.manual_recommendations")

MANUAL_STATUSES = frozenset({"draft", "enriched", "queued", "article_generated", "archived", "failed"})


class ManualRecommendationService:
    def __init__(self, settings: Settings, repositories: Repositories, openai_client: Any | None = None) -> None:
        self.settings = settings
        self.repositories = repositories
        self.openai_client = openai_client

    async def create_manual(
        self,
        workspace_id: str,
        *,
        raw_headline: str,
        raw_notes: str = "",
        content_type: str | None = None,
        target_audience: str | None = None,
        selected_products: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        headline = str(raw_headline or "").strip()
        if not headline:
            raise ValueError("raw_headline is required.")
        await self._workspace(workspace_id)
        return await self.repositories.manual_recommendations.create(
            workspace_id=workspace_id,
            raw_headline=headline,
            raw_notes=str(raw_notes or "").strip(),
            content_type_hint=str(content_type or "").strip() or None,
            target_audience_hint=str(target_audience or "").strip() or None,
            selected_products=selected_products or [],
            created_by=created_by,
        )

    async def create_and_enrich(
        self,
        workspace_id: str,
        *,
        raw_headline: str,
        raw_notes: str = "",
        content_type: str | None = None,
        target_audience: str | None = None,
        selected_products: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        manual = await self.create_manual(
            workspace_id,
            raw_headline=raw_headline,
            raw_notes=raw_notes,
            content_type=content_type,
            target_audience=target_audience,
            selected_products=selected_products,
            created_by=created_by,
        )
        return await self.enrich_manual(workspace_id, manual["id"])

    async def enrich_manual(self, workspace_id: str, manual_id: str) -> dict[str, Any]:
        manual = await self._manual(workspace_id, manual_id)
        if manual.get("status") == "archived":
            raise ValueError("Archived manual recommendations cannot be enriched.")

        workspace = await self._workspace(workspace_id)
        brief = await build_opportunity_ideation_brief(
            workspace_id=workspace_id,
            repositories=self.repositories,
            settings=self.settings,
            include_sitemap=False,
        )
        catalog_products = [
            (str(item.get("name") or "").strip() if isinstance(item, dict) else str(item or "").strip())
            for item in brief.get("catalog_products") or []
            if (str(item.get("name") or "").strip() if isinstance(item, dict) else str(item or "").strip())
        ]

        selected_products = list(manual.get("selected_products") or [])
        if not selected_products:
            selected_products = infer_products_from_text(
                f"{manual.get('raw_headline') or ''} {manual.get('raw_notes') or ''}",
                catalog_products,
            )

        enrichment, warnings = await self._call_enrichment_model(
            brief=brief,
            raw_headline=str(manual.get("raw_headline") or ""),
            raw_notes=str(manual.get("raw_notes") or ""),
            selected_products=selected_products,
            content_type_hint=str(manual.get("content_type_hint") or manual.get("content_type") or ""),
            target_audience_hint=str(manual.get("target_audience_hint") or manual.get("target_audience") or ""),
        )

        safety_violations = validate_enrichment_safety(enrichment)
        if safety_violations:
            failed = await self.repositories.manual_recommendations.update(
                manual_id,
                workspace_id=workspace_id,
                status="failed",
                enrichment_json={"payload": enrichment, "warnings": warnings, "safety_violations": safety_violations},
            )
            raise ValueError(
                f"Enrichment blocked by safety rules: {', '.join(safety_violations)}. "
                "Revise the idea and try again."
            )

        if not enrichment.get("safety_notes"):
            enrichment["safety_notes"] = default_safety_notes(content_type=str(enrichment.get("content_type") or ""))

        if selected_products and not enrichment.get("related_products"):
            enrichment["related_products"] = selected_products

        duplicate_warnings = await self._duplicate_warnings(
            workspace_id,
            str(enrichment.get("headline") or manual.get("raw_headline") or ""),
        )

        updated = await self.repositories.manual_recommendations.update(
            manual_id,
            workspace_id=workspace_id,
            status="enriched",
            enhanced_headline=str(enrichment.get("headline") or "").strip(),
            abstract=str(enrichment.get("abstract") or "").strip(),
            search_intent=str(enrichment.get("search_intent") or "").strip(),
            content_type=str(enrichment.get("content_type") or "").strip(),
            recommendation_type=str(enrichment.get("recommendation_type") or "create").strip(),
            related_products=list(enrichment.get("related_products") or []),
            related_topics=list(enrichment.get("related_topics") or []),
            target_audience=str(enrichment.get("target_audience") or "").strip(),
            priority_reason=str(enrichment.get("priority_reason") or "").strip(),
            safety_notes=list(enrichment.get("safety_notes") or []),
            enrichment_json={"payload": enrichment, "warnings": warnings},
            duplicate_warnings_json=duplicate_warnings,
            ai_enriched_at=True,
        )
        return {**updated, "duplicate_warnings": duplicate_warnings, "enrichment_warnings": warnings}

    async def queue_manual(
        self,
        workspace_id: str,
        manual_id: str,
        *,
        allow_duplicates: bool = False,
    ) -> dict[str, Any]:
        manual = await self._manual(workspace_id, manual_id)
        if manual.get("status") not in {"enriched", "queued"}:
            raise ValueError("Manual recommendation must be enriched before queueing.")
        if manual.get("recommendation_id") and manual.get("status") == "queued":
            existing = await self.repositories.opportunity_recommendations.get_by_id(
                str(manual["recommendation_id"]),
                workspace_id=workspace_id,
            )
            if existing:
                return {"manual": manual, "recommendation": existing, "duplicate_warnings": manual.get("duplicate_warnings") or []}

        duplicate_warnings = list(manual.get("duplicate_warnings") or [])
        if duplicate_warnings and not allow_duplicates:
            return {
                "manual": manual,
                "recommendation": None,
                "duplicate_warnings": duplicate_warnings,
                "requires_confirmation": True,
            }

        workspace = await self._workspace(workspace_id)
        analysis_job_id = workspace.get("last_analysis_job_id")
        recommendation_row = manual_recommendation_to_row(manual, analysis_job_id=analysis_job_id)
        created = await self.repositories.opportunity_recommendations.create_for_workspace(
            workspace_id,
            recommendation_row,
        )
        updated = await self.repositories.manual_recommendations.update(
            manual_id,
            workspace_id=workspace_id,
            status="queued",
            recommendation_id=created["id"],
        )
        return {
            "manual": updated,
            "recommendation": created,
            "duplicate_warnings": duplicate_warnings,
            "requires_confirmation": False,
        }

    async def list_catalog_products(self, workspace_id: str) -> list[str]:
        await self._workspace(workspace_id)
        brief = await build_opportunity_ideation_brief(
            workspace_id=workspace_id,
            repositories=self.repositories,
            settings=self.settings,
            include_sitemap=False,
        )
        products = [
            (str(item.get("name") or "").strip() if isinstance(item, dict) else str(item or "").strip())
            for item in brief.get("catalog_products") or []
        ]
        return sorted({name for name in products if name})

    async def list_manual(
        self,
        workspace_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        await self._workspace(workspace_id)
        return await self.repositories.manual_recommendations.list_for_workspace(
            workspace_id,
            status=status,
            limit=limit,
        )

    async def archive_manual(self, workspace_id: str, manual_id: str) -> dict[str, Any]:
        manual = await self._manual(workspace_id, manual_id)
        recommendation_id = manual.get("recommendation_id")
        if recommendation_id:
            await self.repositories.opportunity_recommendations.update_status(
                str(recommendation_id),
                workspace_id=workspace_id,
                status="archived",
            )
        return await self.repositories.manual_recommendations.update(
            manual_id,
            workspace_id=workspace_id,
            status="archived",
        )

    async def delete_manual(self, workspace_id: str, manual_id: str) -> None:
        await self.repositories.manual_recommendations.delete(manual_id, workspace_id=workspace_id)

    async def build_article_command_context(self, workspace_id: str, recommendation: dict[str, Any]) -> dict[str, Any]:
        metadata = recommendation.get("metadata") if isinstance(recommendation.get("metadata"), dict) else {}
        if metadata.get("article_brief"):
            return dict(metadata["article_brief"])
        return {
            "headline": recommendation.get("title"),
            "abstract": metadata.get("abstract") or recommendation.get("demand_summary") or "",
            "search_intent": metadata.get("search_intent") or "",
            "content_type": metadata.get("content_type") or "",
            "recommendation_type": metadata.get("recommendation_type") or "",
            "related_products": metadata.get("related_products") or [],
            "related_topics": metadata.get("related_topics") or [],
            "target_audience": metadata.get("target_audience") or "",
            "safety_notes": metadata.get("safety_notes") or [],
            "raw_notes": metadata.get("raw_notes") or "",
            "source": "manual_recommendation",
            "manual_recommendation_id": metadata.get("manual_recommendation_id"),
        }

    async def _duplicate_warnings(self, workspace_id: str, headline: str) -> list[dict[str, str]]:
        recommendations = await self.repositories.opportunity_recommendations.list_for_workspace(
            workspace_id,
            limit=200,
        )
        return find_similar_items(headline, recommendations=recommendations)

    async def _call_enrichment_model(
        self,
        *,
        brief: dict[str, Any],
        raw_headline: str,
        raw_notes: str,
        selected_products: list[str],
        content_type_hint: str,
        target_audience_hint: str,
    ) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        if self.openai_client is None:
            return self._fallback_enrichment(
                raw_headline=raw_headline,
                raw_notes=raw_notes,
                selected_products=selected_products,
                content_type_hint=content_type_hint,
                target_audience_hint=target_audience_hint,
            ), ["fallback_no_openai_client"]

        registry = get_default_prompt_registry()
        rendered = registry.render(
            "manual_recommendation_enrichment",
            {
                "workspace_brief_json": context_as_json(brief),
                "raw_headline": raw_headline,
                "raw_notes": raw_notes or "(none)",
                "selected_products_json": context_as_json(selected_products),
                "content_type_hint": content_type_hint or "auto",
                "target_audience_hint": target_audience_hint or "(unspecified)",
            },
        )
        model = self.settings.effective_ai_opportunity_ideation_model
        token_kwargs = (
            {"max_completion_tokens": 1200}
            if uses_max_completion_tokens(model)
            else {"max_tokens": 1200}
        )
        response = await asyncio.wait_for(
            self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You enrich manual SEO article ideas for research-oriented catalogs. "
                            "JSON only. No medical claims. No dosing. No combined-use recommendations."
                        ),
                    },
                    {"role": "user", "content": str(rendered.text)},
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
                **token_kwargs,
            ),
            timeout=max(30.0, float(self.settings.ai_opportunity_ideation_timeout_seconds)),
        )
        payload, parse_warnings = self._parse_json_response(response)
        warnings.extend(parse_warnings)
        return payload, warnings

    def _fallback_enrichment(
        self,
        *,
        raw_headline: str,
        raw_notes: str,
        selected_products: list[str],
        content_type_hint: str,
        target_audience_hint: str,
    ) -> dict[str, Any]:
        content_type = content_type_hint or ("relationship" if len(selected_products) > 1 else "research_overview")
        search_intent = "product_relationship" if content_type == "relationship" else content_type
        headline = raw_headline.strip()
        if not headline.endswith("?"):
            headline = headline.rstrip(".") + " in Research Literature"
        return {
            "headline": headline,
            "abstract": raw_notes.strip()
            or f"A research-focused {content_type.replace('_', ' ')} article based on the operator idea.",
            "search_intent": search_intent,
            "content_type": content_type,
            "recommendation_type": "create",
            "related_products": selected_products,
            "related_topics": ["literature comparison", "research themes"],
            "target_audience": target_audience_hint or "Research readers",
            "priority_reason": "Operator-entered idea captured manually.",
            "safety_notes": default_safety_notes(content_type=content_type),
        }

    def _parse_json_response(self, response: Any) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        content = ""
        try:
            content = response.choices[0].message.content or ""
            payload = json.loads(content)
            if not isinstance(payload, dict):
                warnings.append("response_not_object")
                return {}, warnings
            return payload, warnings
        except Exception as exc:
            logger.warning("Manual enrichment JSON parse failed: %s", exc)
            warnings.append("json_parse_failed")
            return {}, warnings

    async def _workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = await self.repositories.autopilot_workspaces.get(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return workspace

    async def _manual(self, workspace_id: str, manual_id: str) -> dict[str, Any]:
        manual = await self.repositories.manual_recommendations.get(manual_id, workspace_id=workspace_id)
        if not manual:
            raise ValueError("Manual recommendation not found.")
        return manual
