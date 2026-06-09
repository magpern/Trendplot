import asyncio
import json
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from time import perf_counter
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.analysis_prompts import build_website_analysis_prompt
from app.config import Settings
from app.competitor_seo_intelligence import build_competitor_seo_intelligence
from app.intelligence.providers import VideoProviderYouTubeSearchAdapter
from app.intelligence.research_enrichment import ResearchEnrichmentConfig, ResearchEnrichmentService
from app.opportunities.verticals import detect_vertical
from app.providers.base import ContentGenerationProvider
from app.repositories import Repositories
from app.services.jobs import GenerateArticleCommand, JobService
from app.concurrent_crawl import CrawlHttpClient, HttpFetchResult
from app.crawl_budget import resolve_crawl_budget
from app.sitemap_discovery import SitemapDiscoveryResult, SitemapDiscoveryService
from app.site_strategy_profile import build_site_strategy_profile, strip_ideation_from_extraction


logger = logging.getLogger("trendplot.website_analysis")
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


COMMERCIAL_PATH_HINTS = (
    "product",
    "products",
    "shop",
    "store",
    "category",
    "collections",
    "service",
    "services",
    "pricing",
)


@dataclass(slots=True)
class AnalyzeWebsiteCommand:
    website_url: str
    competitor_urls: list[str]
    max_pages_per_site: int = 30
    vertical: str = "auto"
    workspace_id: str | None = None
    progress_callback: ProgressCallback | None = None
    prefetched_website: dict[str, Any] | None = None


class PageSignalParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.meta_description = ""
        self.canonical_url = ""
        self.headings: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.text_chunks: list[str] = []
        self.schema_types: list[str] = []
        self.image_count = 0
        self._active_tag: str | None = None
        self._active_href: str | None = None
        self._skip_depth = 0
        self._in_json_ld_script = False
        self._json_ld_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()

        if tag == "script":
            script_type = attributes.get("type", "").lower()
            if "application/ld+json" in script_type:
                self._in_json_ld_script = True
                self._json_ld_chunks = []
            self._skip_depth += 1
            return

        if tag in {"style", "noscript"}:
            self._skip_depth += 1
            return

        if tag == "title" or tag in {"h1", "h2", "h3"}:
            self._active_tag = tag

        if tag == "meta":
            name = attributes.get("name", "").lower()
            prop = attributes.get("property", "").lower()
            if name == "description" or prop == "og:description":
                self.meta_description = self.meta_description or attributes.get("content", "")

        if tag == "link" and "canonical" in attributes.get("rel", "").lower():
            self.canonical_url = attributes.get("href", "")

        if tag == "a":
            href = attributes.get("href", "")
            self._active_href = urljoin(self.base_url, href) if href else None

        if tag == "img":
            self.image_count += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script" and self._in_json_ld_script:
            self._record_schema_types(" ".join(self._json_ld_chunks))
            self._json_ld_chunks = []
            self._in_json_ld_script = False

        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == self._active_tag:
            self._active_tag = None
        if tag == "a":
            self._active_href = None

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if self._in_json_ld_script and text:
            self._json_ld_chunks.append(text)
        if not text or self._skip_depth:
            return

        if self._active_tag == "title":
            self.title = f"{self.title} {text}".strip()
        elif self._active_tag in {"h1", "h2", "h3"}:
            self.headings.append({"level": self._active_tag, "text": text})
        elif self._active_href:
            self.links.append({"text": text, "url": self._active_href})

        if len(text) > 2:
            self.text_chunks.append(text)

    def _record_schema_types(self, payload: str) -> None:
        try:
            parsed = json.loads(payload)
        except Exception:
            return
        for schema_type in _schema_types_from_json_ld(parsed):
            if schema_type and schema_type not in self.schema_types:
                self.schema_types.append(schema_type)


def _usage_dict(generated: Any) -> dict[str, Any] | None:
    usage = getattr(generated, "usage", None)
    if usage is None:
        return None
    return {
        "token_input": usage.token_input,
        "token_output": usage.token_output,
        "estimated_cost": usage.estimated_cost,
    }


def _discovery_summary(site: dict[str, Any]) -> dict[str, Any]:
    discovery = site.get("url_discovery") if isinstance(site.get("url_discovery"), dict) else {}
    return {
        "domain": site.get("domain"),
        "sitemap_discovery_enabled": discovery.get("sitemap_discovery_enabled", False),
        "robots_txt_checked": discovery.get("robots_txt_checked", False),
        "sitemap_urls_found": discovery.get("sitemap_urls_found", 0),
        "sitemap_files_parsed": discovery.get("sitemap_files_parsed", 0),
        "sitemap_urls_discovered": discovery.get("sitemap_urls_discovered", 0),
        "sitemap_urls_selected": discovery.get("sitemap_urls_selected", 0),
        "useful_url_count": discovery.get("useful_url_count", 0),
        "urls_crawled": discovery.get("urls_crawled", 0),
        "urls_skipped_by_cap": discovery.get("urls_skipped_by_cap", 0),
        "skipped_by_cap_examples": discovery.get("skipped_by_cap_examples", []),
        "crawl_budget": discovery.get("crawl_budget", {}),
        "crawl_timing": discovery.get("crawl_timing", {}),
        "crawl_fallback_used": discovery.get("crawl_fallback_used", False),
        "skipped_url_counts_by_reason": discovery.get("skipped_url_counts_by_reason", {}),
        "selected_urls": discovery.get("selected_urls", []),
    }


def _crawl_progress_event(
    url: str,
    current: int,
    total: int,
    *,
    source_type: str,
    selected_url_count: int | None = None,
    crawl_fallback_used: bool | None = None,
    crawl_budget: dict[str, Any] | None = None,
    active_requests: int | None = None,
    crawl_timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = urlparse(url)
    display_path = parsed.path or "/"
    step = "competitor_analysis" if source_type == "competitor" else "website_crawl"
    label = "competitor page" if source_type == "competitor" else "page"
    selected = selected_url_count if selected_url_count is not None else total
    progress_label = f"Scraped {current} of {max(1, selected)} pages"
    if active_requests:
        progress_label += f" ({active_requests} active)"
    message = f"Scraped {current} of {max(1, selected)} pages."
    if active_requests:
        message += f" {active_requests} requests active."
    if display_path and current == total:
        message = f"{message.rstrip('.')} Last: {display_path}"
    return {
        "step": step,
        "message": message,
        "progress_current": current,
        "progress_total": max(1, selected),
        "progress_label": progress_label,
        "details": {
            "current_url": url,
            "current_path": display_path,
            "selected_url_count": selected_url_count,
            "crawl_fallback_used": crawl_fallback_used,
            "crawl_budget": crawl_budget or {},
            "active_requests": active_requests,
            "crawl_timing": crawl_timing or {},
        },
    }


def _crawl_completion_message(
    *,
    pages_crawled: int,
    selected_count: int,
    skipped_by_cap: int,
    source_type: str,
) -> tuple[str, str]:
    label = "competitor " if source_type == "competitor" else ""
    if skipped_by_cap > 0:
        message = (
            f"Scraped {pages_crawled} of {selected_count} selected {label}pages. "
            f"{skipped_by_cap} skipped due to page limit."
        )
        progress_label = f"Scraped {pages_crawled} of {selected_count} ({skipped_by_cap} skipped)"
    elif pages_crawled == selected_count:
        message = f"Scraped {pages_crawled} of {selected_count} {label}pages."
        progress_label = f"Scraped {pages_crawled} of {selected_count} pages"
    else:
        message = f"Scraped {pages_crawled} {label}page(s)."
        progress_label = f"Scraped {pages_crawled} page(s)"
    return message, progress_label


def _schema_types_from_json_ld(payload: Any) -> list[str]:
    found: list[str] = []

    def _visit(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("@type")
            if isinstance(value, str) and value.strip():
                found.append(value.strip())
            elif isinstance(value, list):
                for item in value:
                    text = str(item).strip()
                    if text:
                        found.append(text)
            for child in node.values():
                _visit(child)
            return
        if isinstance(node, list):
            for child in node:
                _visit(child)

    _visit(payload)
    return list(dict.fromkeys(found))[:30]


def _build_research_enrichment(settings: Settings, video_provider: Any | None) -> ResearchEnrichmentService:
    return ResearchEnrichmentService(
        ResearchEnrichmentConfig(
            enabled=settings.enable_external_research,
            max_queries=max(1, settings.external_research_max_queries),
            max_results_per_query=max(1, settings.external_research_max_results_per_query),
            enable_academic=settings.enable_academic_research,
            enable_reddit=settings.enable_reddit_research,
            enable_trend=getattr(settings, "enable_trend_research", False),
            enable_youtube=bool(video_provider),
        ),
        youtube_provider=VideoProviderYouTubeSearchAdapter(video_provider) if video_provider else None,
    )


class WebsiteAnalysisService:
    def __init__(
        self,
        content_provider: ContentGenerationProvider,
        repositories: Repositories | None = None,
        job_service: JobService | None = None,
        settings: Settings | None = None,
        video_provider: Any | None = None,
    ) -> None:
        self.content_provider = content_provider
        self.repositories = repositories
        self.job_service = job_service
        self.settings = settings or Settings()
        self._active_analysis_tasks: dict[str, asyncio.Task[Any]] = {}
        self.research_enrichment = _build_research_enrichment(settings, video_provider) if settings else None

    async def analyze(self, command: AnalyzeWebsiteCommand) -> dict[str, Any]:
        website, competitors, analysis, prompt = await self._run_analysis(command)
        competitor_seo_intelligence = build_competitor_seo_intelligence(
            workspace_site=website,
            competitor_sites=competitors,
        )
        content_json = analysis.content_json or {}
        suggestions = self._normalize_suggestions(
            [item for item in (content_json.get("topics") or content_json.get("suggestions") or []) if isinstance(item, dict)],
            fallback_url=website["url"],
        )

        return {
            "website": website,
            "competitors": competitors,
            "summary": content_json.get("summary", ""),
            "suggestions": suggestions,
            "audiences": [],
            "clusters": [],
            "opportunities": [],
            "authority_graph": {"nodes": [], "edges": []},
            "vertical_intelligence": {},
            "external_research": {},
            "competitor_seo_intelligence": competitor_seo_intelligence,
        }

    async def crawl_website_for_discovery(
        self,
        *,
        website_url: str,
        max_pages_per_site: int = 30,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        max_pages = self._effective_max_pages(max_pages_per_site)
        return await self._fetch_site(
            website_url,
            max_pages,
            progress_callback=progress_callback,
            source_type="website",
        )

    async def create_analysis_job(self, command: AnalyzeWebsiteCommand) -> dict[str, Any]:
        repositories = self._require_repositories()
        max_pages = self._effective_max_pages(command.max_pages_per_site)
        analysis_job_id = await repositories.analysis_jobs.create(
            website_url=command.website_url,
            competitor_urls=command.competitor_urls[:5],
            max_pages_per_site=max_pages,
            workspace_id=command.workspace_id,
        )
        metrics: dict[str, Any] = {"started_at": perf_counter(), "stages": []}
        await self._mark_analysis_progress(analysis_job_id, "running_crawl", "Collecting website signals.", metrics)
        current_task = asyncio.current_task()
        if current_task is not None:
            self._active_analysis_tasks[analysis_job_id] = current_task

        try:
            website, competitors, analysis, prompt = await self._run_analysis(
                AnalyzeWebsiteCommand(
                    website_url=command.website_url,
                    competitor_urls=command.competitor_urls[:5],
                    max_pages_per_site=max_pages,
                    vertical=command.vertical,
                    workspace_id=command.workspace_id,
                    progress_callback=command.progress_callback,
                    prefetched_website=command.prefetched_website,
                )
            )
            metrics["url_discovery"] = {
                "website": _discovery_summary(website),
                "competitors": [_discovery_summary(competitor) for competitor in competitors],
            }
            self._finish_stage(metrics, "crawl")

            await self._mark_analysis_progress(analysis_job_id, "running_signal_extraction", "Saving crawl signals.", metrics)
            await self._emit_progress(
                command.progress_callback,
                {"step": "website_analysis", "message": "Saving crawl signals and site profile"},
            )
            await self._save_pages(analysis_job_id, "website", website)
            if command.workspace_id:
                await self.sync_content_inventory(str(command.workspace_id), website)
            for competitor in competitors:
                await self._save_pages(analysis_job_id, "competitor", competitor)
            competitor_seo_intelligence = build_competitor_seo_intelligence(
                workspace_site=website,
                competitor_sites=competitors,
            )
            await repositories.analysis_intelligence_artifacts.create(
                analysis_job_id,
                "url_discovery",
                metrics["url_discovery"],
                provider="system",
            )
            await repositories.analysis_intelligence_artifacts.create(
                analysis_job_id,
                "competitor_seo_intelligence",
                competitor_seo_intelligence,
                provider="system",
            )
            logger.info(
                "competitor_seo_intelligence_summary",
                extra={
                    "competitor_seo": {
                        "competitors_analyzed": len(competitor_seo_intelligence.get("competitors_discovered") or []),
                        "coverage_gaps": len(competitor_seo_intelligence.get("coverage_gaps") or []),
                        "competitor_pages": int((competitor_seo_intelligence.get("pages_analyzed") or {}).get("total_competitor_pages") or 0),
                    }
                },
            )
            self._finish_stage(metrics, "signal_extraction")

            await self._mark_analysis_progress(analysis_job_id, "running_opportunity_generation", "Finalizing site strategy profile.", metrics)
            content_json = strip_ideation_from_extraction(analysis.content_json or {})
            inventory_rows = []
            if command.workspace_id:
                inventory_rows = await repositories.workspace_content_inventory.list_for_workspace(
                    str(command.workspace_id), limit=500
                )
            strategy_profile = build_site_strategy_profile(
                ai_extraction=analysis.content_json or {},
                website=website,
                competitors=competitors,
                content_inventory=inventory_rows,
                vertical=command.vertical,
            )
            await repositories.analysis_intelligence_artifacts.create(
                analysis_job_id,
                "site_strategy_profile",
                strategy_profile,
                provider="system",
            )
            persisted_discovery = {"opportunities": [], "clusters": [], "audiences": []}
            self._finish_stage(metrics, "opportunity_generation")

            summary = str(content_json.get("summary") or "").strip() or f"Analyzed {website['url']}"
            suggestions = self._normalize_suggestions(
                [item for item in (content_json.get("topics") or content_json.get("suggestions") or []) if isinstance(item, dict)],
                fallback_url=website["url"],
            )
            saved_suggestions = await repositories.analysis_suggestions.create_many(
                analysis_job_id,
                suggestions,
            )
            await repositories.analysis_jobs.save_artifacts(
                analysis_job_id,
                summary=summary,
                prompt=prompt,
                raw_response={
                    "task_type": analysis.task_type,
                    "model": analysis.model,
                    "usage": _usage_dict(analysis),
                    "reasoning": {
                        "enabled": getattr(analysis, "reasoning_enabled", False),
                        "supported": getattr(analysis, "reasoning_supported", False),
                        "effort": getattr(analysis, "reasoning_effort", None),
                        "source": getattr(analysis, "reasoning_source", None),
                    },
                    "prompt_metadata": getattr(prompt, "prompt_metadata", {}),
                    "response": analysis.raw_response,
                    "opportunity_discovery": persisted_discovery,
                },
            )
            metrics["total_runtime_seconds"] = round(perf_counter() - metrics.pop("started_at"), 3)
            await repositories.analysis_intelligence_artifacts.create(
                analysis_job_id,
                "analysis_stage_metrics",
                metrics,
                provider="system",
            )
            await repositories.analysis_jobs.mark_status(analysis_job_id, "completed")
            await self._emit_progress(
                command.progress_callback,
                {"step": "website_analysis", "status": "succeeded", "message": "Website analysis completed"},
            )

            return await self.get_analysis_job(analysis_job_id, suggestions=saved_suggestions)
        except asyncio.CancelledError:
            await repositories.analysis_jobs.mark_status(
                analysis_job_id,
                "cancelled",
                "Analysis cancelled by user or application shutdown.",
            )
            raise
        except Exception as exc:
            await repositories.analysis_jobs.mark_status(analysis_job_id, "failed", str(exc))
            raise
        finally:
            self._active_analysis_tasks.pop(analysis_job_id, None)

    async def cancel_analysis_job(
        self,
        analysis_job_id: str,
        reason: str = "Analysis cancelled by user.",
    ) -> dict[str, Any]:
        repositories = self._require_repositories()
        job = await repositories.analysis_jobs.get(analysis_job_id)
        if job is None:
            raise ValueError("Analysis job not found.")

        task = self._active_analysis_tasks.get(analysis_job_id)
        if task is not None and not task.done():
            task.cancel()
        if job["status"] in {"pending", "queued", "running", "running_crawl", "running_signal_extraction", "running_opportunity_generation"}:
            await repositories.analysis_jobs.mark_status(analysis_job_id, "cancelled", reason)
        return await repositories.analysis_jobs.get(analysis_job_id) or job

    async def cancel_active_analyses(
        self,
        reason: str = "Analysis cancelled by user.",
    ) -> list[dict[str, Any]]:
        cancelled = []
        for analysis_job_id in list(self._active_analysis_tasks):
            cancelled.append(await self.cancel_analysis_job(analysis_job_id, reason))
        return cancelled

    async def list_analysis_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        repositories = self._require_repositories()
        return await repositories.analysis_jobs.list_recent(limit)

    async def get_analysis_job(
        self,
        analysis_job_id: str,
        suggestions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        repositories = self._require_repositories()
        job = await repositories.analysis_jobs.get(analysis_job_id)
        if job is None:
            raise ValueError("Analysis job not found.")

        pages = await repositories.analysis_pages.list_for_job(analysis_job_id)
        stored_suggestions = (
            suggestions
            if suggestions is not None
            else await repositories.analysis_suggestions.list_for_job(analysis_job_id)
        )
        opportunities: list[dict[str, Any]] = []
        clusters: list[dict[str, Any]] = []
        audiences: list[dict[str, Any]] = []
        authority_graph: dict[str, Any] = {"nodes": [], "edges": []}
        intelligence_artifacts = await repositories.analysis_intelligence_artifacts.list_for_job(analysis_job_id)

        strategy_profile = next(
            (artifact.get("content") for artifact in intelligence_artifacts if artifact.get("artifact_type") == "site_strategy_profile"),
            None,
        )

        return {
            "analysis_job": job,
            "pages": pages,
            "artifacts": self._analysis_artifacts(job) + self._intelligence_artifacts(intelligence_artifacts),
            "suggestions": stored_suggestions,
            "opportunities": opportunities,
            "clusters": clusters,
            "audiences": audiences,
            "authority_graph": authority_graph,
            "strategy_profile": strategy_profile if isinstance(strategy_profile, dict) else None,
        }

    def _analysis_artifacts(self, job: dict[str, Any]) -> list[dict[str, Any]]:
        artifacts = []
        if job.get("prompt"):
            artifacts.append(
                {
                    "artifact_type": "website_analysis_prompt",
                    "content_text": job["prompt"],
                }
            )
        if job.get("raw_response"):
            artifacts.append(
                {
                    "artifact_type": "website_analysis_raw_response",
                    "content_json": job["raw_response"],
                }
            )
        if job.get("summary"):
            artifacts.append(
                {
                    "artifact_type": "website_analysis_summary",
                    "content_text": job["summary"],
                }
            )
        return artifacts

    def _intelligence_artifacts(self, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "artifact_type": artifact["artifact_type"],
                "content_json": artifact.get("content"),
                "provider": artifact.get("provider"),
            }
            for artifact in artifacts
        ]

    async def update_suggestion(
        self,
        suggestion_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        repositories = self._require_repositories()
        if "status" in fields and fields["status"] not in {
            "suggested",
            "approved",
            "rejected",
            "generated",
        }:
            raise ValueError("Invalid suggestion status.")

        suggestion = await repositories.analysis_suggestions.update(suggestion_id, fields)
        if suggestion is None:
            raise ValueError("Suggestion not found.")
        return suggestion

    async def generate_article_from_suggestion(self, suggestion_id: str) -> dict[str, Any]:
        repositories = self._require_repositories()
        job_service = self._require_job_service()
        suggestion = await repositories.analysis_suggestions.get(suggestion_id)
        if suggestion is None:
            raise ValueError("Suggestion not found.")
        if suggestion["status"] != "approved":
            raise ValueError("Suggestion must be approved before generating an article draft.")

        result = await job_service.generate_article(
            GenerateArticleCommand(
                title=suggestion["title"],
                target_keyword=suggestion["target_keyword"],
                product_name=suggestion["product_name"],
                product_url=suggestion["product_url"],
                publish_policy="manual_review",
            )
        )
        if result.get("job_id") and not str(result.get("status", "")).startswith("failed"):
            updated = await repositories.analysis_suggestions.mark_generated(
                suggestion_id,
                result["job_id"],
            )
        else:
            updated = suggestion

        return {
            "suggestion": updated,
            "article_job": result,
        }

    async def update_opportunity(
        self,
        opportunity_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        repositories = self._require_repositories()
        if "status" in fields and fields["status"] not in {
            "suggested",
            "approved",
            "rejected",
            "generated",
            "planned",
            "bookmarked",
        }:
            raise ValueError("Invalid opportunity status.")
        opportunity = await repositories.opportunities.update(opportunity_id, fields)
        if opportunity is None:
            raise ValueError("Opportunity not found.")
        return opportunity

    async def list_opportunities(
        self,
        analysis_job_id: str,
        *,
        cluster_id: str | None = None,
        audience_id: str | None = None,
        opportunity_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        repositories = self._require_repositories()
        return await repositories.opportunities.list_for_job(
            analysis_job_id,
            cluster_id=cluster_id,
            audience_id=audience_id,
            opportunity_type=opportunity_type,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def generate_article_from_opportunity(self, opportunity_id: str) -> dict[str, Any]:
        repositories = self._require_repositories()
        job_service = self._require_job_service()
        opportunity = await repositories.opportunities.get(opportunity_id)
        if opportunity is None:
            raise ValueError("Opportunity not found.")
        if opportunity["status"] not in {"approved", "planned"}:
            raise ValueError("Opportunity must be approved or planned before generating an article draft.")

        result = await job_service.generate_article(
            GenerateArticleCommand(
                title=opportunity["title"],
                target_keyword=opportunity["target_keyword"],
                product_name=opportunity["product_name"] or opportunity["target_keyword"],
                product_url=opportunity["product_url"],
                publish_policy="manual_review",
            )
        )
        if result.get("job_id") and not str(result.get("status", "")).startswith("failed"):
            opportunity = await repositories.opportunities.update(
                opportunity_id,
                {"status": "generated", "generated_job_id": result["job_id"]},
            ) or opportunity

        return {
            "opportunity": opportunity,
            "article_job": result,
        }

    async def _run_analysis(
        self,
        command: AnalyzeWebsiteCommand,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], Any, str]:
        max_pages = self._effective_max_pages(command.max_pages_per_site)
        if command.prefetched_website:
            website = command.prefetched_website
        else:
            website = await self._fetch_site(
                command.website_url,
                max_pages,
                progress_callback=command.progress_callback,
                source_type="website",
            )
        competitors: list[dict[str, Any]] = []

        await self._emit_progress(
            command.progress_callback,
            {"step": "website_analysis", "message": "Sending crawled content to OpenAI"},
        )
        active_profile, detection_report = detect_vertical(
            website=website,
            competitors=competitors,
            override=command.vertical,
        )
        prompt = build_website_analysis_prompt(
            website,
            competitors,
            vertical_context={
                "detected_vertical": detection_report["detected_vertical"],
                "vertical_confidence": detection_report["detected_vertical_confidence"],
                "vertical_detection_report": detection_report,
                "vertical_profile_summary": active_profile.summary(),
                "vertical_entity_expansions": active_profile.entity_expansion_map,
                "vertical_audience_examples": active_profile.audience_examples,
                "vertical_adjacent_niches": active_profile.adjacent_niche_map,
            },
            max_digest_pages=self.settings.website_analysis_digest_max_pages,
        )
        await self._emit_progress(
            command.progress_callback,
            {"step": "website_analysis", "message": "Waiting for model response"},
        )
        analysis = await self.content_provider.generate_website_analysis(prompt)
        await self._emit_progress(
            command.progress_callback,
            {"step": "website_analysis", "message": "Processing analysis results"},
        )
        return website, competitors, analysis, prompt

    async def sync_content_inventory(self, workspace_id: str, site: dict[str, Any]) -> int:
        from app.content_inventory import inventory_item_from_page

        repositories = self._require_repositories()
        count = 0
        for page in site.get("pages", []):
            if not isinstance(page, dict) or str(page.get("status") or "") == "error":
                continue
            item = inventory_item_from_page(page, workspace_id=workspace_id)
            await repositories.workspace_content_inventory.upsert_page(workspace_id, item)
            count += 1
        return count

    async def _save_pages(
        self,
        analysis_job_id: str,
        source_type: str,
        site: dict[str, Any],
    ) -> None:
        repositories = self._require_repositories()
        for page in site.get("pages", []):
            await repositories.analysis_pages.create(
                analysis_job_id=analysis_job_id,
                source_type=source_type,
                source_url=site["url"],
                page=page,
            )

    async def _persist_opportunity_discovery(
        self,
        analysis_job_id: str,
        discovery: Any,
        model_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        repositories = self._require_repositories()
        audiences = await repositories.audience_profiles.create_many(
            analysis_job_id,
            [item.model_dump() for item in discovery.audiences],
        )
        clusters = await repositories.opportunity_clusters.create_many(
            analysis_job_id,
            [item.model_dump() for item in discovery.clusters],
        )
        opportunities = await repositories.opportunities.create_many(
            analysis_job_id,
            [item.model_dump() for item in discovery.opportunities],
        )

        audience_rows = []
        for opportunity in opportunities:
            if opportunity.get("primary_audience_id"):
                audience_rows.append(
                    {
                        "opportunity_id": opportunity["id"],
                        "audience_id": opportunity["primary_audience_id"],
                        "role": "primary",
                        "rationale": opportunity.get("audience_rationale", ""),
                    }
                )
            for audience_id in opportunity.get("secondary_audience_ids", []):
                audience_rows.append(
                    {
                        "opportunity_id": opportunity["id"],
                        "audience_id": audience_id,
                        "role": "secondary",
                    }
                )
        await repositories.opportunity_audiences.create_many(analysis_job_id, audience_rows)

        graph_nodes = await repositories.authority_graph.create_nodes(
            analysis_job_id,
            [item.model_dump() for item in discovery.authority_graph.nodes],
        )
        node_ids = {
            str((node.get("source_signals") or {}).get("source_node_id") or node["id"]).removeprefix(f"{analysis_job_id}:")
            for node in graph_nodes
        }
        graph_edges = await repositories.authority_graph.create_edges(
            analysis_job_id,
            [
                edge.model_dump()
                for edge in discovery.authority_graph.edges
                if edge.source_node_id in node_ids and edge.target_node_id in node_ids
            ],
        )
        relationships = await repositories.opportunity_relationships.create_many(
            analysis_job_id,
            [item.model_dump() for item in discovery.relationships],
        )

        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "opportunity_discovery_result",
            discovery.model_dump(),
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "niche_intelligence",
            discovery.niche_intelligence,
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "product_intelligence",
            discovery.product_intelligence,
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "extracted_entity_intelligence",
            {
                "extracted_entities": discovery.product_intelligence.get("extracted_entities", []),
                "extracted_products": discovery.product_intelligence.get("extracted_products", []),
                "extracted_mechanisms": discovery.product_intelligence.get("extracted_mechanisms", []),
                "extracted_concepts": discovery.product_intelligence.get("extracted_concepts", []),
                "product_families": discovery.product_intelligence.get("product_families", []),
            },
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "competitor_intelligence",
            discovery.competitor_intelligence,
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "semantic_expansion",
            discovery.semantic_expansion,
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "vertical_detection",
            discovery.vertical_intelligence,
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "external_research_enrichment",
            discovery.external_research,
            provider="opportunity-engine",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "opportunity_model_metadata",
            model_metadata,
            provider="openai",
        )
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "campaign_mode_seed",
            discovery.campaign_seed,
            provider="opportunity-engine",
        )

        return {
            "audiences": len(audiences),
            "clusters": len(clusters),
            "opportunities": len(opportunities),
            "authority_graph_nodes": len(graph_nodes),
            "authority_graph_edges": len(graph_edges),
            "relationships": len(relationships),
        }

    async def _mark_analysis_progress(
        self,
        analysis_job_id: str,
        status: str,
        message: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        repositories = self._require_repositories()
        await repositories.analysis_jobs.mark_status(analysis_job_id, status)
        await repositories.analysis_intelligence_artifacts.create(
            analysis_job_id,
            "analysis_progress_log",
            {"status": status, "message": message},
            provider="system",
        )
        if metrics is not None:
            metrics.setdefault("stages", []).append({"status": status, "message": message, "started_at": perf_counter()})

    def _finish_stage(self, metrics: dict[str, Any], stage_name: str) -> None:
        stages = metrics.get("stages") or []
        if not stages:
            return
        stages[-1]["name"] = stage_name
        stages[-1]["runtime_seconds"] = round(perf_counter() - stages[-1].pop("started_at", perf_counter()), 3)

    def _require_repositories(self) -> Repositories:
        if self.repositories is None:
            raise RuntimeError("Repositories are required for persisted analysis operations.")
        return self.repositories

    def _require_job_service(self) -> JobService:
        if self.job_service is None:
            raise RuntimeError("Job service is required for generating articles from suggestions.")
        return self.job_service

    def _normalize_suggestions(
        self,
        suggestions: Any,
        fallback_url: str,
    ) -> list[dict[str, str]]:
        if not isinstance(suggestions, list):
            return []

        normalized = []
        for suggestion in suggestions[:100]:
            if not isinstance(suggestion, dict):
                continue
            normalized.append(
                {
                    "title": str(suggestion.get("title") or "Untitled article idea"),
                    "target_keyword": str(suggestion.get("target_keyword") or ""),
                    "product_name": str(suggestion.get("product_name") or ""),
                    "product_url": str(suggestion.get("product_url") or fallback_url),
                    "reason": str(suggestion.get("reason") or suggestion.get("rationale") or ""),
                    "confidence": str(suggestion.get("confidence") or "medium"),
                }
            )
        return normalized

    async def _fetch_site(
        self,
        start_url: str,
        max_pages: int,
        *,
        progress_callback: ProgressCallback | None = None,
        source_type: str = "website",
    ) -> dict[str, Any]:
        normalized_start = self._normalize_url(start_url)
        sitemap_progress_callback = progress_callback if source_type == "website" else None
        async with CrawlHttpClient.from_app_settings(self.settings) as crawl_client:
            try:
                discovery = await self._discover_sitemap_urls(
                    normalized_start,
                    max_pages,
                    progress_callback=sitemap_progress_callback,
                    crawl_client=crawl_client,
                )
            except TypeError as exc:
                if "progress_callback" not in str(exc):
                    raise
                discovery = await self._discover_sitemap_urls(
                    normalized_start,
                    max_pages,
                    crawl_client=crawl_client,
                )
            selected_urls = [item.url for item in discovery.selected_urls]
            selected_reasons = {item.url: item.reason for item in discovery.selected_urls}
            useful_count = int(discovery.useful_url_count or len(selected_urls))
            budget = resolve_crawl_budget(
                useful_url_count=useful_count,
                max_pages=max_pages,
                settings=self.settings,
            )
            discovery.crawl_budget = budget.as_dict()
            crawl_limit = budget.crawl_limit if source_type == "website" else max_pages
            urls_to_crawl = selected_urls[:crawl_limit]
            skipped_by_cap = selected_urls[crawl_limit:]
            crawl_items = [(url, selected_reasons.get(url, "sitemap-selected page")) for url in urls_to_crawl]

            async def _on_progress(completed: int, total: int, active: int) -> None:
                await self._emit_progress(
                    progress_callback,
                    _crawl_progress_event(
                        normalized_start,
                        completed,
                        total,
                        source_type=source_type,
                        selected_url_count=len(selected_urls),
                        crawl_fallback_used=False,
                        crawl_budget=budget.as_dict(),
                        active_requests=active,
                        crawl_timing=crawl_client.metrics.as_dict(),
                    ),
                )

            pages = await crawl_client.fetch_pages_ordered(
                crawl_items,
                self._build_page_from_fetch,
                on_progress=_on_progress if progress_callback else None,
            )
            seen = {self._normalize_url(page.get("url") or "") for page in pages}

            homepage = next((page for page in pages if self._normalize_url(page.get("url", "")) == normalized_start), None)
            if homepage is None:
                homepage = await self._fetch_page_with_client(
                    crawl_client,
                    normalized_start,
                    "homepage",
                )
                if normalized_start not in seen and len(pages) < crawl_limit:
                    pages.insert(0, homepage)
                    seen.add(normalized_start)

            if self.settings.crawl_fallback_enabled and len(pages) < crawl_limit and homepage:
                discovery.crawl_fallback_used = True
                fallback_items: list[tuple[str, str]] = []
                for url in self._candidate_urls(homepage, normalized_start):
                    if len(pages) + len(fallback_items) >= crawl_limit:
                        break
                    normalized_url = self._normalize_url(url)
                    if normalized_url in seen:
                        continue
                    fallback_items.append((normalized_url, "internal crawl fallback"))
                if fallback_items:
                    fallback_pages = await crawl_client.fetch_pages_ordered(
                        fallback_items,
                        self._build_page_from_fetch,
                        on_progress=_on_progress if progress_callback else None,
                    )
                    for page in fallback_pages:
                        if len(pages) >= crawl_limit:
                            break
                        pages.append(page)
                        seen.add(self._normalize_url(page.get("url") or ""))

            if not pages:
                homepage = await self._fetch_page_with_client(
                    crawl_client,
                    normalized_start,
                    "homepage fallback",
                )
                pages = [homepage]

            timing = crawl_client.metrics.as_dict()
            timing["crawl_duration_seconds"] = round(
                timing.get("sitemap_fetch_duration_seconds", 0) + timing.get("page_crawl_duration_seconds", 0),
                3,
            )

        metrics = discovery.metrics()
        metrics["useful_url_count"] = useful_count
        metrics["urls_crawled"] = len(pages)
        metrics["urls_skipped_by_cap"] = len(skipped_by_cap)
        metrics["skipped_by_cap_examples"] = [
            {"url": url, "path": urlparse(url).path or "/"} for url in skipped_by_cap[:8]
        ]
        metrics["crawl_budget"] = budget.as_dict()
        metrics["crawl_timing"] = timing
        completion_message, completion_label = _crawl_completion_message(
            pages_crawled=len(pages),
            selected_count=len(selected_urls),
            skipped_by_cap=len(skipped_by_cap),
            source_type=source_type,
        )
        logger.info(
            "sitemap_discovery_summary",
            extra={
                "domain": urlparse(normalized_start).netloc,
                "sitemap_discovery": {key: value for key, value in metrics.items() if key != "selected_urls"},
            },
        )
        await self._emit_progress(
            progress_callback,
            {
                "step": "competitor_analysis" if source_type == "competitor" else "website_crawl",
                "status": "succeeded",
                "message": completion_message,
                "progress_current": len(pages),
                "progress_total": max(len(selected_urls), len(pages)),
                "progress_label": completion_label,
                "details": {
                    "urls_discovered": metrics.get("sitemap_urls_discovered", 0),
                    "urls_selected": len(selected_urls),
                    "urls_crawled": len(pages),
                    "urls_skipped_by_cap": len(skipped_by_cap),
                    "skipped_by_cap_examples": metrics["skipped_by_cap_examples"],
                    "useful_url_count": useful_count,
                    "crawl_budget": budget.as_dict(),
                    "crawl_timing": timing,
                },
            },
        )

        return {
            "url": normalized_start,
            "domain": urlparse(normalized_start).netloc,
            "pages": pages,
            "url_discovery": metrics,
        }

    async def _discover_sitemap_urls(
        self,
        normalized_start: str,
        max_pages: int,
        *,
        progress_callback: ProgressCallback | None = None,
        crawl_client: CrawlHttpClient | None = None,
    ) -> SitemapDiscoveryResult:
        discovery = SitemapDiscoveryService(
            enabled=self.settings.sitemap_discovery_enabled,
            max_urls_to_parse=self.settings.sitemap_max_urls_to_parse,
            max_sitemaps_to_parse=self.settings.sitemap_max_sitemaps_to_parse,
            progress_callback=progress_callback,
            crawl_client=crawl_client,
        )
        provisional = await discovery.discover(normalized_start, max_pages=max_pages)
        budget = resolve_crawl_budget(
            useful_url_count=int(provisional.useful_url_count or 0),
            max_pages=max_pages,
            settings=self.settings,
        )
        if budget.selection_limit != len(provisional.selected_urls):
            return await discovery.discover(
                normalized_start,
                max_pages=max_pages,
                selection_limit=budget.selection_limit,
            )  # same discovery service retains crawl_client
        provisional.crawl_budget = budget.as_dict()
        return provisional

    async def _emit_progress(self, callback: ProgressCallback | None, event: dict[str, Any]) -> None:
        if callback is None:
            return
        try:
            await callback(event)
        except Exception:  # noqa: BLE001 - progress reporting must never affect analysis.
            logger.debug("analysis_progress_callback_failed", exc_info=True)

    async def _fetch_page_with_client(
        self,
        crawl_client: CrawlHttpClient,
        url: str,
        discovery_reason: str,
    ) -> dict[str, Any]:
        fetch = await crawl_client.fetch_http(url, context="page")
        page = self._build_page_from_fetch(url, fetch)
        page["discovery_reason"] = discovery_reason
        return page

    async def _fetch_page(self, url: str) -> dict[str, Any]:
        async with CrawlHttpClient.from_app_settings(self.settings) as crawl_client:
            return await self._fetch_page_with_client(crawl_client, url, "direct fetch")

    def _build_page_from_fetch(self, url: str, fetch: HttpFetchResult) -> dict[str, Any]:
        if fetch.content is None:
            return {
                "url": url,
                "status": "error",
                "error": fetch.error or "fetch failed",
                "title": "",
                "meta_description": "",
                "canonical_url": "",
                "headings": [],
                "commercial_links": [],
                "navigation_links": [],
                "outbound_links": [],
                "schema_types": [],
                "url_structure": {"path": urlparse(url).path or "/", "depth": self._url_depth(url)},
                "questions": [],
                "entities": [],
                "faq_present": False,
                "word_count": 0,
                "image_count": 0,
                "content_type": "error",
                "text_sample": "",
            }

        page_url = fetch.url or url
        charset = "utf-8"
        if "charset=" in (fetch.content_type or "").lower():
            charset = fetch.content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            html = fetch.content.decode(charset, errors="replace")
        except LookupError:
            html = fetch.content.decode("utf-8", errors="replace")

        parser = PageSignalParser(page_url)
        parser.feed(html)
        h1 = [heading["text"] for heading in parser.headings if heading.get("level") == "h1"][:10]
        h2 = [heading["text"] for heading in parser.headings if heading.get("level") == "h2"][:20]
        h3 = [heading["text"] for heading in parser.headings if heading.get("level") == "h3"][:20]
        faq_present = self._has_faq_signal(parser, h1=h1, h2=h2, h3=h3)

        return {
            "url": page_url,
            "status": "ok",
            "title": parser.title[:200],
            "meta_description": parser.meta_description[:320],
            "canonical_url": parser.canonical_url,
            "headings": parser.headings[:20],
            "h1": h1,
            "h2": h2,
            "h3": h3,
            "url_structure": {"path": urlparse(page_url).path or "/", "depth": self._url_depth(page_url)},
            "schema_types": parser.schema_types[:20],
            "commercial_links": self._commercial_links(parser.links, page_url)[:20],
            "navigation_links": self._navigation_links(parser.links, page_url)[:40],
            "outbound_links": self._outbound_links(parser.links, page_url)[:40],
            "questions": self._page_questions(parser)[:20],
            "entities": self._page_entities(parser)[:30],
            "faq_present": faq_present,
            "word_count": self._word_count(parser),
            "image_count": int(parser.image_count),
            "content_type": self._content_type(page_url, h1=h1, h2=h2, h3=h3, faq_present=faq_present),
            "text_sample": " ".join(parser.text_chunks)[:3000],
        }

    def _candidate_urls(self, homepage: dict[str, Any], start_url: str) -> list[str]:
        urls = [
            link["url"]
            for link in homepage.get("commercial_links", [])
            if self._same_domain(link["url"], start_url)
        ]
        return list(dict.fromkeys(urls))

    def _effective_max_pages(self, requested: int) -> int:
        configured_max = max(1, int(self.settings.max_pages_per_site))
        requested_max = requested if requested and requested > 0 else configured_max
        return max(1, min(requested_max, configured_max))

    def _commercial_links(
        self,
        links: list[dict[str, str]],
        base_url: str,
    ) -> list[dict[str, str]]:
        results = []
        for link in links:
            url = self._normalize_url(link["url"])
            if not self._same_domain(url, base_url):
                continue
            path = urlparse(url).path.lower()
            if any(hint in path for hint in COMMERCIAL_PATH_HINTS):
                results.append({"text": link["text"][:120], "url": url})
        return results

    def _navigation_links(
        self,
        links: list[dict[str, str]],
        base_url: str,
    ) -> list[dict[str, str]]:
        results = []
        for link in links:
            url = self._normalize_url(link["url"])
            if not self._same_domain(url, base_url):
                continue
            text = " ".join(str(link.get("text", "")).split())[:120]
            if text:
                results.append({"text": text, "url": url})
        return list({item["url"]: item for item in results}.values())

    def _outbound_links(
        self,
        links: list[dict[str, str]],
        base_url: str,
    ) -> list[dict[str, str]]:
        results = []
        for link in links:
            url = self._normalize_url(link["url"])
            if self._same_domain(url, base_url):
                continue
            text = " ".join(str(link.get("text", "")).split())[:120]
            if text:
                results.append({"text": text, "url": url})
        return list({item["url"]: item for item in results}.values())

    def _page_questions(self, parser: PageSignalParser) -> list[str]:
        chunks = [parser.title, parser.meta_description]
        chunks.extend(heading["text"] for heading in parser.headings)
        questions = []
        for chunk in chunks:
            text = chunk.strip()
            lower = text.lower()
            if text.endswith("?") or lower.startswith(("what ", "how ", "why ", "when ", "where ", "which ", "can ", "does ")):
                questions.append(text[:160])
        return list(dict.fromkeys(questions))

    def _page_entities(self, parser: PageSignalParser) -> list[str]:
        text = " ".join([parser.title, " ".join(heading["text"] for heading in parser.headings)])
        candidates = re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", text)
        return list(dict.fromkeys(candidates))[:30]

    def _word_count(self, parser: PageSignalParser) -> int:
        text = " ".join(parser.text_chunks)
        if not text:
            return 0
        return len(re.findall(r"\b\w+\b", text))

    def _has_faq_signal(self, parser: PageSignalParser, *, h1: list[str], h2: list[str], h3: list[str]) -> bool:
        if any("faq" in str(value).lower() for value in [*h1, *h2, *h3]):
            return True
        if any(str(schema).strip().lower() == "faqpage" for schema in parser.schema_types):
            return True
        if len(self._page_questions(parser)) >= 3:
            return True
        return False

    def _content_type(
        self,
        page_url: str,
        *,
        h1: list[str],
        h2: list[str],
        h3: list[str],
        faq_present: bool,
    ) -> str:
        if faq_present:
            return "faq"
        path = (urlparse(page_url).path or "").lower()
        combined = " ".join([path, *h1[:2], *h2[:4], *h3[:2]]).lower()
        if path in {"", "/"}:
            return "homepage"
        if any(token in combined for token in ("/category", "/collections", "/catalog")):
            return "category"
        if any(token in combined for token in ("/product", "/products", "/shop")):
            return "product"
        if any(token in combined for token in ("/service", "/services")):
            return "service"
        if any(token in combined for token in ("/blog", "/article", "/guides", "/learn")):
            return "blog"
        if any(token in combined for token in ("/support", "/help")):
            return "support"
        return "page"

    def _url_depth(self, value: str) -> int:
        path = (urlparse(value).path or "/").strip("/")
        return 0 if not path else len([segment for segment in path.split("/") if segment])

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc or parsed.path
        path = parsed.path if parsed.netloc else ""
        normalized = parsed._replace(
            scheme=scheme,
            netloc=netloc.lower(),
            path=path or "/",
            params="",
            query="",
            fragment="",
        )
        return urlunparse(normalized)

    def _same_domain(self, first_url: str, second_url: str) -> bool:
        return urlparse(first_url).netloc == urlparse(second_url).netloc
