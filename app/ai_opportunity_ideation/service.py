from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.prompts.context_json import context_as_json
from app.ai_opportunity_ideation.brief import build_opportunity_ideation_brief
from app.ai_opportunity_ideation.models import AIOpportunity
from app.ai_opportunity_ideation.parser import (
    brief_cache_key,
    loads_ideation_payload,
    merge_opportunity_lists,
    parse_opportunities_response,
)
from app.catalog.products import product_coverage
from app.config import Settings
from app.prompts.prompt_registry import get_default_prompt_registry
from app.providers.model_router import uses_max_completion_tokens
from app.repositories import Repositories, utc_now

logger = logging.getLogger("trendplot.ai_opportunity_ideation")

_SYSTEM_MESSAGE = (
    "You generate diverse SEO article opportunities for research-oriented ecommerce sites. "
    "Enforce category mix quotas in the user prompt. Handling/storage/reconstitution must not exceed 25% of ideas. "
    "Each catalog product needs at least one science/research overview and one comparison or relationship article. "
    "Science-first editorial: prioritize mechanism, biology, signaling, and literature context — not supplier listings, "
    "catalog navigation, or documentation quality. "
    "Do not put RUO in headlines unless the topic is labeling, compliance, documentation, or regulatory terminology; "
    "use abstracts and safety_notes for research-use-only framing. "
    "No medical claims. No human consumption or dosing. JSON only."
)

_TOPUP_SYSTEM_MESSAGE = (
    "You generate additional diverse SEO article opportunities. No medical claims. No human consumption or dosing. "
    "Prioritize science overviews, comparisons, product relationships, and mechanism explainers — "
    "not repeated storage/handling/reconstitution variants. "
    "Do not append (RUO) to headlines; keep research-use-only framing in abstracts and safety_notes. "
    "Never repeat or closely paraphrase existing headlines. Respond with JSON only."
)


class AIOpportunityIdeationService:
    """Catalog-aware article opportunity generation. Fail-open when disabled or on failure."""

    def __init__(self, settings: Settings, repositories: Repositories, openai_client: Any | None = None) -> None:
        self.settings = settings
        self.repositories = repositories
        self.openai_client = openai_client

    @property
    def enabled(self) -> bool:
        return bool(self.settings.ai_opportunity_ideation_enabled and self.openai_client)

    async def generate_for_workspace(
        self,
        workspace_id: str,
        *,
        workspace: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "enabled": self.settings.ai_opportunity_ideation_enabled,
            "opportunities_created": 0,
            "cache_hit": False,
            "fallback_count": 0,
            "fail_open_reason": "",
            "model": self.settings.effective_ai_opportunity_ideation_model,
        }
        if not self.settings.ai_opportunity_ideation_enabled:
            return {"opportunities": [], "run": None, "warnings": ["Ideation disabled."], "metrics": metrics}
        if self.openai_client is None:
            metrics["fallback_count"] = 1
            metrics["fail_open_reason"] = "no_client"
            return {"opportunities": [], "run": None, "warnings": ["No OpenAI client."], "metrics": metrics}

        workspace = workspace or await self.repositories.autopilot_workspaces.get(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")

        brief = await build_opportunity_ideation_brief(
            workspace_id=workspace_id,
            repositories=self.repositories,
            settings=self.settings,
            include_sitemap=self.settings.ai_opportunity_ideation_include_sitemap,
        )
        cache_key = brief_cache_key(brief)
        min_ideas = self.settings.ai_opportunity_ideation_min_ideas
        max_ideas = self.settings.ai_opportunity_ideation_max_ideas

        if (
            not force_refresh
            and self.settings.ai_opportunity_ideation_cache_enabled
        ):
            cached = await self._load_cached_opportunities(workspace_id, cache_key)
            if cached:
                metrics["cache_hit"] = True
                metrics["opportunities_created"] = len(cached["opportunities"])
                return cached

        run = await self.repositories.ai_opportunity_ideation_runs.create_started(
            workspace_id=workspace_id,
            metadata={"brief_cache_key": cache_key, "model": metrics["model"]},
        )
        run_id = run["id"]
        warnings: list[str] = []

        try:
            parsed, warnings = await self._generate_opportunities(
                brief,
                min_ideas=min_ideas,
                max_ideas=max_ideas,
                catalog_products=brief.get("catalog_products") or [],
            )
        except asyncio.TimeoutError:
            metrics["fallback_count"] = 1
            metrics["fail_open_reason"] = "timeout"
            await self.repositories.ai_opportunity_ideation_runs.mark_failed(run_id, error_message="timeout")
            return {"opportunities": [], "run": run, "warnings": warnings + ["Ideation timed out."], "metrics": metrics}
        except Exception as exc:
            metrics["fallback_count"] = 1
            metrics["fail_open_reason"] = str(exc)[:120]
            logger.warning("ai_opportunity_ideation_failed", exc_info=exc)
            await self.repositories.ai_opportunity_ideation_runs.mark_failed(run_id, error_message=str(exc)[:500])
            return {"opportunities": [], "run": run, "warnings": warnings + [str(exc)[:200]], "metrics": metrics}

        now = utc_now()
        rows: list[dict[str, Any]] = []
        for draft in parsed:
            opportunity_id = str(uuid4())
            rows.append(draft.as_row(workspace_id=workspace_id, run_id=run_id, opportunity_id=opportunity_id, created_at=now))

        persisted = await self.repositories.ai_opportunity_ideation_opportunities.replace_for_run(
            workspace_id, run_id, rows
        )
        coverage = product_coverage(persisted, brief.get("catalog_products") or [])
        completed = await self.repositories.ai_opportunity_ideation_runs.mark_completed(
            run_id,
            opportunities_created=len(persisted),
            warnings=warnings,
            metadata={**metrics, "brief_cache_key": cache_key, "product_coverage": coverage},
        )
        metrics["opportunities_created"] = len(persisted)
        metrics["product_coverage"] = coverage
        return {
            "opportunities": persisted,
            "run": completed,
            "warnings": warnings,
            "metrics": metrics,
            "brief": brief,
        }

    async def _load_cached_opportunities(self, workspace_id: str, cache_key: str) -> dict[str, Any] | None:
        run = await self.repositories.ai_opportunity_ideation_runs.latest_completed_for_cache(
            workspace_id,
            brief_cache_key=cache_key,
            ttl_hours=self.settings.ai_opportunity_ideation_cache_ttl_hours,
        )
        if not run:
            return None
        opportunities = await self.repositories.ai_opportunity_ideation_opportunities.list_for_run(
            str(run.get("id") or ""),
        )
        if not opportunities:
            return None
        return {
            "opportunities": opportunities,
            "run": run,
            "warnings": ["cache_hit"],
            "metrics": {
                "enabled": True,
                "opportunities_created": len(opportunities),
                "cache_hit": True,
                "fallback_count": 0,
                "fail_open_reason": "",
                "model": self.settings.effective_ai_opportunity_ideation_model,
                "brief_cache_key": cache_key,
            },
        }

    async def _generate_opportunities(
        self,
        brief: dict[str, Any],
        *,
        min_ideas: int,
        max_ideas: int,
        catalog_products: list[str],
    ) -> tuple[list[AIOpportunity], list[str]]:
        warnings: list[str] = []
        batch_size = self._ideation_batch_size(max_ideas=max_ideas)
        payload, json_warnings = await self._call_model(
            brief,
            min_ideas=batch_size,
            max_ideas=batch_size,
        )
        warnings.extend(json_warnings)
        parsed, parse_warnings = parse_opportunities_response(
            payload,
            min_ideas=min_ideas,
            max_ideas=max_ideas,
            catalog_products=catalog_products,
        )
        warnings.extend(parse_warnings)

        top_up_rounds = 0
        max_rounds = max(0, self.settings.ai_opportunity_ideation_max_top_up_rounds)
        while len(parsed) < min_ideas and top_up_rounds < max_rounds:
            top_up_rounds += 1
            need = self._top_up_count(parsed_count=len(parsed), min_ideas=min_ideas, max_ideas=max_ideas)
            if need <= 0:
                break
            top_up_payload, top_json_warnings = await self._call_model_topup(
                brief,
                existing=parsed,
                count=need,
                min_total=min_ideas,
                max_total=max_ideas,
            )
            warnings.extend(top_json_warnings)
            supplemental, top_warnings = parse_opportunities_response(
                top_up_payload,
                min_ideas=1,
                max_ideas=need,
                catalog_products=[],
            )
            warnings.extend(top_warnings)
            parsed, merge_warnings = merge_opportunity_lists(parsed, supplemental, max_ideas=max_ideas)
            warnings.extend(merge_warnings)
            warnings.append(f"top_up_round_{top_up_rounds}:{len(supplemental)}_new_{len(parsed)}_total")

        if len(parsed) < min_ideas:
            warnings.append(f"below_min_ideas:{len(parsed)}<{min_ideas}")

        return parsed[:max_ideas], warnings

    def _completion_token_kwargs(self, *, max_output_tokens: int) -> dict[str, Any]:
        model = self.settings.effective_ai_opportunity_ideation_model
        tokens = max(1024, max_output_tokens)
        if uses_max_completion_tokens(model):
            return {"max_completion_tokens": tokens}
        return {"max_tokens": tokens}

    def _call_timeout_seconds(self, *, expected_ideas: int) -> float:
        """Scale per-call timeout with batch size — large ideation JSON often exceeds 90s."""
        configured = max(30.0, float(self.settings.ai_opportunity_ideation_timeout_seconds))
        scaled = max(configured, float(max(1, expected_ideas)) * 4.0)
        return min(scaled, 900.0)

    def _ideation_batch_size(self, *, max_ideas: int) -> int:
        cap = max(10, int(self.settings.ai_opportunity_ideation_batch_size))
        return min(max_ideas, cap)

    def _top_up_count(self, *, parsed_count: int, min_ideas: int, max_ideas: int) -> int:
        remaining_to_max = max_ideas - parsed_count
        if remaining_to_max <= 0:
            return 0
        batch_cap = max(10, int(self.settings.ai_opportunity_ideation_batch_size))
        remaining_to_min = max(0, min_ideas - parsed_count)
        target = max(remaining_to_min, min(20, batch_cap))
        return min(remaining_to_max, target, batch_cap)

    async def _call_model(self, brief: dict[str, Any], *, min_ideas: int, max_ideas: int) -> tuple[dict[str, Any], list[str]]:
        registry = get_default_prompt_registry()
        rendered = registry.render(
            "ai_opportunity_ideation",
            {
                "opportunity_ideation_brief_json": context_as_json(brief),
                "min_ideas": str(min_ideas),
                "max_ideas": str(max_ideas),
            },
        )
        response = await asyncio.wait_for(
            self.openai_client.chat.completions.create(
                model=self.settings.effective_ai_opportunity_ideation_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_MESSAGE},
                    {"role": "user", "content": str(rendered.text)},
                ],
                temperature=self.settings.ai_opportunity_ideation_temperature,
                response_format={"type": "json_object"},
                **self._completion_token_kwargs(
                    max_output_tokens=self.settings.ai_opportunity_ideation_max_output_tokens,
                ),
            ),
            timeout=self._call_timeout_seconds(expected_ideas=max_ideas),
        )
        return self._parse_json_response(response)

    async def _call_model_topup(
        self,
        brief: dict[str, Any],
        *,
        existing: list[AIOpportunity],
        count: int,
        min_total: int,
        max_total: int,
    ) -> tuple[dict[str, Any], list[str]]:
        existing_headlines = [opp.headline for opp in existing]
        user_message = (
            f"Generate exactly {count} NEW article opportunities for the same website.\n"
            f"You already produced {len(existing)} opportunities. The final library must reach "
            f"{min_total}–{max_total} total unique headlines.\n\n"
            "Do NOT repeat or closely paraphrase any existing headline:\n"
            f"{json.dumps(existing_headlines[:120], ensure_ascii=True)}\n\n"
            "Use the same JSON schema as before (`opportunities` array with headline, abstract, "
            "search_intent, content_type, recommendation_type, related_products, related_topics, "
            "target_audience, priority_reason, safety_notes).\n"
            "Prioritize deficits in category mix: science/research overviews, comparisons, product relationships, "
            "mechanism/background explainers, then FAQ/calculator support. "
            "Use `suggested_themes` and `theme_mix_targets` from the brief. "
            "Do not add more storage, handling, or reconstitution variants unless handling share is already below 25%.\n\n"
            f"Site brief JSON:\n{context_as_json(brief)}"
        )
        response = await asyncio.wait_for(
            self.openai_client.chat.completions.create(
                model=self.settings.effective_ai_opportunity_ideation_model,
                messages=[
                    {"role": "system", "content": _TOPUP_SYSTEM_MESSAGE},
                    {"role": "user", "content": user_message},
                ],
                temperature=min(0.5, self.settings.ai_opportunity_ideation_temperature + 0.1),
                response_format={"type": "json_object"},
                **self._completion_token_kwargs(
                    max_output_tokens=min(
                        self.settings.ai_opportunity_ideation_max_output_tokens,
                        max(4096, count * 280),
                    ),
                ),
            ),
            timeout=self._call_timeout_seconds(expected_ideas=count),
        )
        return self._parse_json_response(response)

    def _parse_json_response(self, response: Any) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        if getattr(choice, "finish_reason", None) == "length":
            warnings.append("response_truncated:length")
        payload, load_warnings = loads_ideation_payload(content)
        warnings.extend(load_warnings)
        return payload, warnings
