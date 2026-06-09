import asyncio
import json
import logging
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from app.article_schema import ArticleSchema, article_outline, article_to_markdown, normalize_article
from app.catalog.products import product_name_from_url, resolve_product_page_url
from app.config import Settings
from app.enrichment import EnrichmentService
from app.internal_links import InternalLinkService
from app.internal_links.product_linker import (
    LinkReport,
    build_article_product_url_map,
    link_products_in_article,
)
from app.repositories import utc_now
from app.seo.article_linker import ArticleLinkCandidate, build_article_link_candidates
from app.seo.optimization_pass import OptimizationReport, run_seo_optimization_pass
from app.wordpress_connector.seo import job_seo_snapshot
from app.media.image_generation import ArticleImageGenerationService
from app.opportunities.verticals import detect_vertical
from app.prompts import (
    ArticlePromptInput,
    build_article_prompt,
    build_youtube_evaluation_prompt,
)
from app.providers.base import GeneratedContent, PublishPolicy
from app.providers.model_router import ModelTask
from app.quality_checks import requires_ruo_disclaimer, run_article_quality_checks
from app.rules.compliance_rules import build_compliance_rules, default_publisher_name
from app.rendering.article_renderer import render_article
from app.rendering.dual_render import render_dual_surfaces
from app.rendering.render_surface import ArticleRenderSurface
from app.rendering.schema_jsonld import build_schema_jsonld
from app.providers.registry import ProviderRegistry
from app.product_data import NullProductDataProvider
from app.repositories import Repositories
from app.services.publish_decisions import PublishDecisionService
from app.services.run_metrics import JobRunMetrics
from app.review.article_repair import (
    ArticleRepairRequest,
    ArticleRepairService,
    apply_deterministic_quality_fixes,
    has_fixable_quality_issues,
    sanitize_article_safety,
)
from app.services.article_pipeline import (
    effective_max_repair_passes,
    run_deterministic_sanity_review,
    should_run_humanization,
    should_run_narrative_editor,
    should_run_section_expansion,
    should_run_semantic_sanity,
    should_run_youtube_ai_evaluation,
    skipped_editorial_rewrite_result,
    skipped_narrative_editor_result,
    skipped_section_expansion_result,
)
from app.review.editorial_rewriter import EditorialRewriter
from app.review.narrative_editor import NarrativeEditor
from app.review.redundancy_checker import RedundancyChecker
from app.review.sanity_checker import ArticleSanityChecker
from app.review.semantic_sanity import SemanticSanityReviewer
from app.review.section_expander import SectionExpansionRequest, SectionExpansionResult, SectionExpansionService

logger = logging.getLogger(__name__)

GENERATION_ACTIVE_STATUSES = frozenset(
    {
        "queued",
        "running_generation",
        "running_repair",
        "running_expansion",
        "running_review",
        "running_rendering",
        "running_publish",
    }
)


class GenerationCancelledError(Exception):
    """Raised when article generation is stopped by the operator."""


def _opportunity_context_json(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    from app.ai_opportunity_ideation.article_brief import enrich_article_opportunity_context

    enriched = enrich_article_opportunity_context(context)
    try:
        return json.dumps(enriched, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(enriched)


def _related_products_from_context(context: dict[str, Any] | None) -> list[str]:
    if not isinstance(context, dict):
        return []
    products = context.get("related_products")
    if not isinstance(products, list):
        return []
    return [str(item).strip() for item in products if str(item).strip()]


@dataclass(slots=True)
class GenerateArticleCommand:
    title: str
    target_keyword: str
    product_name: str
    product_url: str
    publish_policy: str | None = None
    category_id: int | None = None
    category_slug: str | None = None
    category_name: str | None = None
    wordpress_template: str | None = None
    wordpress_category_id: int | None = None
    wordpress_category_slug: str | None = None
    wordpress_category_name: str | None = None
    wordpress_tags: list[str] | None = None
    featured_image_id: int | None = None
    featured_image_url: str | None = None
    featured_image_alt: str | None = None
    unattended_mode: bool = False
    workspace_id: str | None = None
    content_plan_item_id: str | None = None
    origin_type: str | None = None
    opportunity_context: dict[str, Any] | None = None


class JobService:
    def __init__(
        self,
        settings: Settings,
        registry: ProviderRegistry,
        repositories: Repositories,
        wordpress_connector_service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.repositories = repositories
        self.wordpress_connector_service = wordpress_connector_service
        self.internal_links = InternalLinkService()
        self.article_repair = ArticleRepairService()
        self.section_expander = SectionExpansionService()
        self.humanizer = EditorialRewriter()
        self.narrative_editor = NarrativeEditor()
        self.sanity_checker = ArticleSanityChecker()
        self.semantic_sanity = SemanticSanityReviewer()
        self.publish_decisions = PublishDecisionService(settings)
        self.redundancy_checker = RedundancyChecker()
        self.image_generation = ArticleImageGenerationService(settings)
        self.product_data = NullProductDataProvider()
        self._cancel_requested: set[str] = set()

    def request_cancel(self, job_id: str) -> None:
        self._cancel_requested.add(job_id)

    def clear_cancel(self, job_id: str) -> None:
        self._cancel_requested.discard(job_id)

    def _ensure_not_cancelled(self, job_id: str) -> None:
        if job_id in self._cancel_requested:
            raise GenerationCancelledError("Article generation cancelled by user.")

    async def cancel_generation_job(self, job_id: str) -> dict[str, Any]:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        status = str(job.get("status") or "")
        if status == "cancelled":
            return {"job_id": job_id, "status": "cancelled", "already_cancelled": True}
        self.request_cancel(job_id)
        if status in GENERATION_ACTIVE_STATUSES:
            await self.repositories.jobs.mark_status(job_id, "cancelled", "Cancelled by user.")
            await self.repositories.logs.add_log(
                job_id,
                "warning",
                "job",
                "Article generation cancelled by user.",
            )
        else:
            await self.repositories.logs.add_log(
                job_id,
                "info",
                "job",
                f"Cancel requested for job in status {status}.",
            )
        return {"job_id": job_id, "status": "cancelled"}

    async def delete_generation_job(self, job_id: str) -> None:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        status = str(job.get("status") or "")
        if status in GENERATION_ACTIVE_STATUSES:
            await self.cancel_generation_job(job_id)
        await self._cleanup_job_files(job_id)
        await self.repositories.jobs.clear_generated_job_references(job_id)
        deleted = await self.repositories.jobs.delete_job(job_id)
        if not deleted:
            raise ValueError("Job not found.")
        self.clear_cancel(job_id)

    async def _cleanup_job_files(self, job_id: str) -> None:
        image_generation = await self._latest_artifact_json(job_id, "image_generation_result") or {}
        images = image_generation.get("images")
        if not isinstance(images, list):
            return
        output_dir = Path(self.settings.ai_image_output_dir).resolve()
        for image in images:
            if not isinstance(image, dict):
                continue
            local_path = str(image.get("local_path") or "").strip()
            if not local_path:
                continue
            path = Path(local_path).resolve()
            if path.parent != output_dir or not path.is_file():
                continue
            try:
                path.unlink()
            except OSError:
                logger.warning("Failed to delete generated image file.", extra={"path": str(path)})

    def _publish_policy_for_command(self, command: GenerateArticleCommand) -> PublishPolicy:
        if command.unattended_mode and not self.settings.unattended_mode_enabled:
            raise ValueError("unattended_mode=true requires UNATTENDED_MODE_ENABLED=true.")
        publish_policy = command.publish_policy or (
            self.settings.unattended_default_publish_policy if command.unattended_mode else self.settings.default_publish_policy
        )
        if publish_policy not in {
            "manual_review",
            "draft_after_review",
            "live_after_review",
            "auto_draft",
            "auto_live",
        }:
            raise ValueError("Unsupported publish_policy.")
        return PublishPolicy(
            mode=publish_policy,
            wordpress_status="draft",
            human_review_required=self.settings.human_review_required,
        )

    async def prepare_generation_job(self, command: GenerateArticleCommand) -> tuple[str, PublishPolicy]:
        policy = self._publish_policy_for_command(command)
        job_id = await self.repositories.jobs.create_job(
            request_input=asdict(command),
            human_review_required=policy.human_review_required,
            workspace_id=command.workspace_id,
            content_plan_item_id=command.content_plan_item_id,
            origin_type=command.origin_type,
        )
        await self.repositories.jobs.mark_status(job_id, "queued")
        await self.repositories.logs.add_log(
            job_id,
            "info",
            "job",
            "Article generation queued.",
        )
        return job_id, policy

    async def run_generation_job_task(
        self,
        job_id: str,
        command: GenerateArticleCommand,
        policy: PublishPolicy,
    ) -> None:
        await self._mark_progress(job_id, "running_generation", "job", "Job started.")
        try:
            result = await self._run_generation_job(job_id, command, policy)
            final_status = result.get("status", "completed")
            await self.repositories.jobs.mark_status(job_id, final_status)
            await self.repositories.logs.add_log(
                job_id,
                "info",
                "job",
                f"Job finished with status {final_status}.",
            )
        except GenerationCancelledError:
            await self.repositories.jobs.mark_status(job_id, "cancelled", "Cancelled by user.")
            await self.repositories.logs.add_log(
                job_id,
                "warning",
                "job",
                "Article generation cancelled by user.",
            )
        except asyncio.CancelledError:
            await self.repositories.jobs.mark_status(job_id, "cancelled", "Cancelled by user.")
            await self.repositories.logs.add_log(
                job_id,
                "warning",
                "job",
                "Article generation task interrupted.",
            )
            raise
        except Exception as exc:
            logger.exception("Job failed.", extra={"job_id": job_id})
            await self.repositories.jobs.mark_status(job_id, "failed_generation", str(exc))
            await self.repositories.logs.add_log(
                job_id,
                "error",
                "job",
                "Job failed.",
                {"error": str(exc)},
            )
        finally:
            self.clear_cancel(job_id)

    async def generate_article(self, command: GenerateArticleCommand) -> dict[str, Any]:
        job_id, policy = await self.prepare_generation_job(command)
        await self._mark_progress(job_id, "running_generation", "job", "Job started.")
        try:
            result = await self._run_generation_job(job_id, command, policy)
            final_status = result.get("status", "completed")
            await self.repositories.jobs.mark_status(job_id, final_status)
            await self.repositories.logs.add_log(
                job_id,
                "info",
                "job",
                f"Job finished with status {final_status}.",
            )
            return result
        except Exception as exc:
            logger.exception("Job failed.", extra={"job_id": job_id})
            await self.repositories.jobs.mark_status(job_id, "failed_generation", str(exc))
            await self.repositories.logs.add_log(
                job_id,
                "error",
                "job",
                "Job failed.",
                {"error": str(exc)},
            )
            raise

    async def get_generation_result(self, job_id: str) -> dict[str, Any] | None:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            return None
        status = str(job.get("status") or "")
        if status in GENERATION_ACTIVE_STATUSES:
            return None
        request_input = job.get("request_input") or {}
        quality = await self._latest_artifact_json(job_id, "final_quality_check_results")
        if not quality:
            quality = await self._latest_artifact_json(job_id, "quality_check_results")
        return {
            "job_id": job_id,
            "status": status,
            "human_review_required": bool(job.get("human_review_required")),
            "publish_policy": request_input.get("publish_policy"),
            "quality_check": quality,
            "final_quality_check": await self._latest_artifact_json(job_id, "final_quality_check_results") or quality,
            "sanity_check": await self._latest_artifact_json(job_id, "sanity_check_results"),
            "structured_article": await self._latest_artifact_json(job_id, "structured_article_json"),
            "wordpress_presentation_metadata": await self._latest_artifact_json(job_id, "wordpress_presentation_metadata") or {},
            "rendered_html": await self._latest_artifact_text(job_id, "rendered_html"),
            "publishable_html_available": bool(await self._latest_artifact_text(job_id, "publishable_html")),
            "wordpress_post_id": job.get("wordpress_post_id"),
            "wordpress_edit_url": job.get("wordpress_edit_url"),
            "wordpress_public_url": job.get("wordpress_public_url"),
            "wordpress_status": job.get("wordpress_status"),
            "wordpress_draft_created_at": job.get("wordpress_draft_created_at"),
            "wordpress_draft_updated_at": job.get("wordpress_draft_updated_at"),
            "last_wordpress_sync_at": job.get("last_wordpress_sync_at"),
            "wordpress_publish_error": job.get("wordpress_publish_error"),
            "seo_title": job.get("seo_title"),
            "seo_description": job.get("seo_description"),
            "seo_focus_keyword": job.get("seo_focus_keyword"),
            "seo_canonical_url": job.get("seo_canonical_url"),
            "seo_robots": job.get("seo_robots"),
            "seo_schema_type": job.get("seo_schema_type"),
            "seo_generated_at": job.get("seo_generated_at"),
            "seo_synced_at": job.get("seo_synced_at"),
            "seo_last_error": job.get("seo_last_error"),
            "rank_math_score": job.get("rank_math_score"),
            "recommended_slug": job.get("recommended_slug"),
            "seo_manually_edited": job.get("seo_manually_edited"),
            "suggested_featured_image_alt": job.get("suggested_featured_image_alt"),
            "suggested_inline_image_alt": job.get("suggested_inline_image_alt"),
            "seo_optimized_at": job.get("seo_optimized_at"),
            "seo_optimization_report": await self._latest_artifact_json(job_id, "seo_optimization_report"),
        }

    async def rerun_job(self, job_id: str) -> dict[str, Any]:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        request_input = job.get("request_input") or {}
        command = self._command_from_request_input(request_input)
        result = await self.generate_article(command)
        await self.repositories.logs.add_log(
            result["job_id"],
            "info",
            "job",
            f"Job rerun created from {job_id}.",
            {"source_job_id": job_id},
        )
        return {
            "source_job_id": job_id,
            "article_job": result,
        }

    def _command_from_request_input(self, request_input: dict[str, Any]) -> GenerateArticleCommand:
        missing = [
            field
            for field in ("title", "target_keyword", "product_name", "product_url")
            if not str(request_input.get(field) or "").strip()
        ]
        if missing:
            raise ValueError(f"Cannot rerun job because request input is missing: {', '.join(missing)}.")
        publish_policy = request_input.get("publish_policy")
        if not publish_policy and request_input.get("publish_mode"):
            publish_policy = "manual_review"
        return GenerateArticleCommand(
            title=str(request_input["title"]),
            target_keyword=str(request_input["target_keyword"]),
            product_name=str(request_input["product_name"]),
            product_url=str(request_input["product_url"]),
            publish_policy=str(publish_policy or self.settings.default_publish_policy),
            category_id=request_input.get("category_id"),
            category_slug=request_input.get("category_slug"),
            category_name=request_input.get("category_name"),
            wordpress_template=request_input.get("wordpress_template"),
            wordpress_category_id=request_input.get("wordpress_category_id"),
            wordpress_category_slug=request_input.get("wordpress_category_slug"),
            wordpress_category_name=request_input.get("wordpress_category_name"),
            wordpress_tags=_string_list_from_value(request_input.get("wordpress_tags")),
            featured_image_id=request_input.get("featured_image_id"),
            featured_image_url=request_input.get("featured_image_url"),
            featured_image_alt=request_input.get("featured_image_alt"),
            unattended_mode=bool(request_input.get("unattended_mode")),
        )

    async def _run_generation_job(
        self,
        job_id: str,
        command: GenerateArticleCommand,
        policy: PublishPolicy,
    ) -> dict[str, Any]:
        self._ensure_not_cancelled(job_id)
        command = await self._resolve_generation_command(command)
        content_provider = self.registry.content_generation
        enrichment = EnrichmentService(self.registry.image, self.registry.video)
        metrics = JobRunMetrics()
        renderer_publishable_logs: list[str] = []

        metrics.start_stage("article_generation")
        article_prompt = build_article_prompt(
            ArticlePromptInput(
                title=command.title,
                target_keyword=command.target_keyword,
                product_name=command.product_name,
                product_url=command.product_url,
                min_word_count=self.settings.target_min_word_count,
                max_word_count=max(
                    self.settings.target_article_min_words,
                    self.settings.target_min_word_count + 600,
                ),
                opportunity_context_json=_opportunity_context_json(command.opportunity_context),
            )
        )
        await self._save_prompt(job_id, "structured_article", article_prompt, ModelTask.ARTICLE_GENERATION)

        article = await content_provider.generate_article(article_prompt, task_type=ModelTask.ARTICLE_GENERATION)
        initial_article_generation = article
        metrics.record_model_call("article_generation", initial_article_generation)
        await self._save_raw_llm_response(job_id, "structured_article_initial", initial_article_generation)
        article_model = self._normalize_structured_article(article, command)
        compliance_ctx = await self._generation_compliance_context(command, article_model)
        self.sanity_checker.rules = compliance_ctx["compliance_rules"]
        article_defaults = {
            "title": command.title,
            "target_keyword": command.target_keyword,
            "product_name": command.product_name,
            "product_url": command.product_url,
        }
        article_model = apply_deterministic_quality_fixes(
            article_model,
            request_data=asdict(command),
            is_biomedical=compliance_ctx["is_biomedical"],
            required_disclaimer=compliance_ctx["required_disclaimer"],
            defaults=article_defaults,
            target_min_word_count=self.settings.target_min_word_count,
        )
        from app.review.compliance_redundancy import apply_editorial_post_processing

        article_model = apply_editorial_post_processing(
            article_model,
            defaults=article_defaults,
            opportunity_context=command.opportunity_context,
        )
        article_model, product_link_report = await self._apply_editorial_product_links(article_model, command)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "product_link_report",
            GeneratedContent(content_json=product_link_report.as_dict(), provider="product-linker"),
        )
        initial_quality_result = run_article_quality_checks(
            article=article_model,
            markdown=article_to_markdown(article_model, surface=ArticleRenderSurface.PUBLISHABLE),
            product_url=command.product_url,
            youtube_video=None,
            min_word_count=self.settings.target_min_word_count,
            required_disclaimer=self.settings.biomedical_ruo_disclaimer,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "initial_quality_check_results",
            GeneratedContent(
                content_json={
                    **initial_quality_result.as_dict(),
                    "task_type": ModelTask.QUALITY_REVIEW.value,
                },
                provider="quality-checker",
            ),
        )
        metrics.finish_stage("article_generation")
        self._ensure_not_cancelled(job_id)

        repair_summary: dict[str, Any] = {
            "attempted": False,
            "pass_count": 0,
            "reason": "Initial quality passed or failures were not fixable.",
            "remaining_errors": initial_quality_result.errors,
            "remaining_warnings": initial_quality_result.warnings,
        }
        repair_pass_count = 0
        repair_generations: list[GeneratedContent] = []
        current_quality_result = initial_quality_result
        if not initial_quality_result.passed and has_fixable_quality_issues(
            initial_quality_result.errors,
            initial_quality_result.warnings,
        ):
            await self._mark_progress(job_id, "running_repair", "article_repair", "Repairing fixable quality issues.")
            metrics.start_stage("article_repair")
            for pass_number in range(1, effective_max_repair_passes(self.settings) + 1):
                repair_pass_count = pass_number
                repair_result = await self.article_repair.repair(
                    content_provider=content_provider,
                    request=ArticleRepairRequest(
                        article=article_model,
                        request_data=asdict(command),
                        quality_errors=current_quality_result.errors,
                        quality_warnings=current_quality_result.warnings,
                        target_min_word_count=self.settings.target_min_word_count,
                        is_biomedical=compliance_ctx["is_biomedical"],
                        required_disclaimer=self.settings.biomedical_ruo_disclaimer,
                        pass_number=pass_number,
                    ),
                )
                if repair_result.generated is not None:
                    repair_generations.append(repair_result.generated)
                    metrics.record_model_call("article_repair", repair_result.generated)
                await self.repositories.artifacts.create_artifact(
                    job_id,
                    "article_repair_prompt",
                    GeneratedContent(
                        content_text=repair_result.prompt,
                        content_json={
                            "pass_number": pass_number,
                            "task_type": ModelTask.ARTICLE_REPAIR.value,
                            **self._prompt_metadata(repair_result.prompt),
                        },
                        provider="prompt-builder",
                    ),
                )
                await self.repositories.artifacts.create_artifact(
                    job_id,
                    "article_repair_raw_response",
                    GeneratedContent(
                        content_json={
                            "pass_number": pass_number,
                            "task_type": repair_result.generated.task_type if repair_result.generated else ModelTask.ARTICLE_REPAIR.value,
                            "model": repair_result.generated.model if repair_result.generated else None,
                            "usage": self._usage_dict(repair_result.generated),
                        "reasoning": self._reasoning_dict(repair_result.generated),
                            "response": repair_result.generated.raw_response if repair_result.generated else None,
                        },
                        provider=repair_result.generated.provider if repair_result.generated else "article-repair",
                        model=repair_result.generated.model if repair_result.generated else None,
                    task_type=repair_result.generated.task_type if repair_result.generated else ModelTask.ARTICLE_REPAIR.value,
                        usage=repair_result.generated.usage if repair_result.generated else None,
                    ),
                )

                repaired_article_model = normalize_article(
                    repair_result.repaired_article_json,
                    defaults={
                        "title": command.title,
                        "target_keyword": command.target_keyword,
                        "product_name": command.product_name,
                        "product_url": command.product_url,
                    },
                )
                repaired_quality_result = run_article_quality_checks(
                    article=repaired_article_model,
                    markdown=article_to_markdown(repaired_article_model, surface=ArticleRenderSurface.PUBLISHABLE),
                    product_url=command.product_url,
                    youtube_video=None,
                    min_word_count=self.settings.target_min_word_count,
                    required_disclaimer=self.settings.biomedical_ruo_disclaimer,
                )
                repair_summary = {
                    **repair_result.repair_summary,
                    "attempted": True,
                    "pass_count": pass_number,
                    "repaired_fields": repair_result.repaired_fields,
                    "repaired_sections": repair_result.repaired_sections,
                    "previous_errors": current_quality_result.errors,
                    "previous_warnings": current_quality_result.warnings,
                    "remaining_errors": repaired_quality_result.errors,
                    "remaining_warnings": repaired_quality_result.warnings,
                    "word_count_before": current_quality_result.word_count,
                    "word_count_after": repaired_quality_result.word_count,
                    "accepted": repaired_quality_result.word_count >= current_quality_result.word_count,
                }
                if repaired_quality_result.word_count >= current_quality_result.word_count:
                    article_model = repaired_article_model
                    article = repair_result.generated or article
                    current_quality_result = repaired_quality_result
                if current_quality_result.passed:
                    break
            metrics.finish_stage("article_repair")

        await self.repositories.artifacts.create_artifact(
            job_id,
            "article_repair_summary",
            GeneratedContent(
                content_json=repair_summary,
                provider="article-repair",
            ),
        )

        await self._mark_progress(job_id, "running_expansion", "section_expansion", "Expanding thin article sections.")
        metrics.start_stage("section_expansion")
        if should_run_section_expansion(
            self.settings,
            publishable_word_count=current_quality_result.word_count,
        ):
            expansion_result = await self.section_expander.expand(
                content_provider=content_provider,
                request=SectionExpansionRequest(
                    article=article_model,
                    request_data=asdict(command),
                    quality_result=current_quality_result.as_dict(),
                    target_article_word_count=max(
                        self.settings.target_article_min_words,
                        self.settings.target_min_word_count,
                    ),
                    target_section_min_words=self.settings.target_section_min_words,
                    max_passes=self.settings.max_section_expansion_passes,
                    max_sections_per_pass=self.settings.max_sections_expanded_per_pass,
                    is_biomedical=compliance_ctx["is_biomedical"],
                    required_disclaimer=compliance_ctx["required_disclaimer"],
                ),
            )
            article_model = expansion_result.article
            for record in expansion_result.prompt_records:
                metrics.record_model_call("section_expansion", record.generated)
            article_model = normalize_article(
                sanitize_article_safety(article_model.model_dump()),
                defaults=article_defaults,
            )
        else:
            expansion_result = skipped_section_expansion_result(
                article_model,
                reason=(
                    "Simplified pipeline: section expansion disabled or article already meets "
                    f"{self.settings.target_min_word_count} words."
                ),
                word_count=current_quality_result.word_count,
            )
        for record in expansion_result.prompt_records:
            await self.repositories.artifacts.create_artifact(
                job_id,
                "section_expansion_prompt",
                GeneratedContent(
                    content_text=record.prompt,
                    content_json={
                        "pass_number": record.pass_number,
                        "task_type": ModelTask.SECTION_EXPANSION.value,
                        "target_type": record.target_type,
                        "target_index": record.target_index,
                        "heading": record.heading,
                            **self._prompt_metadata(record.prompt),
                    },
                    provider="prompt-builder",
                ),
            )
            await self.repositories.artifacts.create_artifact(
                job_id,
                "section_expansion_raw_response",
                GeneratedContent(
                    content_json={
                        "pass_number": record.pass_number,
                        "task_type": record.generated.task_type if record.generated else ModelTask.SECTION_EXPANSION.value,
                        "model": record.generated.model if record.generated else None,
                        "usage": self._usage_dict(record.generated),
                        "reasoning": self._reasoning_dict(record.generated),
                        "target_type": record.target_type,
                        "target_index": record.target_index,
                        "heading": record.heading,
                        "response": record.generated.raw_response if record.generated else None,
                    },
                    provider=record.generated.provider if record.generated else "section-expander",
                    model=record.generated.model if record.generated else None,
                    task_type=record.generated.task_type if record.generated else ModelTask.SECTION_EXPANSION.value,
                    usage=record.generated.usage if record.generated else None,
                ),
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "section_expansion_summary",
            GeneratedContent(
                content_json=expansion_result.summary,
                provider="section-expander",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "section_expansion_word_count_before",
            GeneratedContent(
                content_text=str(expansion_result.summary.get("word_count_before", "")),
                content_json={"word_count": expansion_result.summary.get("word_count_before")},
                provider="section-expander",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "section_expansion_word_count_after",
            GeneratedContent(
                content_text=str(expansion_result.summary.get("word_count_after", "")),
                content_json={"word_count": expansion_result.summary.get("word_count_after")},
                provider="section-expander",
            ),
        )
        metrics.finish_stage("section_expansion")
        self._ensure_not_cancelled(job_id)

        await self._mark_progress(job_id, "running_review", "redundancy_review", "Reviewing article redundancy.")
        metrics.start_stage("redundancy_review")
        redundancy_report = self.redundancy_checker.review(article_model)
        article_model, redundancy_cleanup_summary = self.redundancy_checker.cleanup(
            article_model,
            defaults={
                "title": command.title,
                "target_keyword": command.target_keyword,
                "product_name": command.product_name,
                "product_url": command.product_url,
            },
            required_disclaimer=compliance_ctx["required_disclaimer"],
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "redundancy_review_results",
            GeneratedContent(content_json=redundancy_report.as_dict(), provider="redundancy-checker"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "redundancy_cleanup_summary",
            GeneratedContent(content_json=redundancy_cleanup_summary, provider="redundancy-checker"),
        )
        metrics.finish_stage("redundancy_review")
        self._ensure_not_cancelled(job_id)

        metrics.start_stage("humanization")
        await self.repositories.artifacts.create_artifact(
            job_id,
            "pre_humanized_article_json",
            GeneratedContent(content_json=article_model.model_dump(), provider="humanizer"),
        )
        if should_run_humanization(self.settings):
            humanization_profile, humanization_vertical_report = _detect_article_vertical(
                article=article_model,
                command=command,
                configured_vertical=self.settings.opportunity_vertical,
            )
            humanization_result = await self.humanizer.humanize(
                content_provider=content_provider,
                article=article_model,
                request_data=asdict(command),
                required_disclaimer=self.settings.biomedical_ruo_disclaimer,
                target_min_word_count=self.settings.target_min_word_count,
                vertical_profile={
                    "detected_vertical": humanization_vertical_report.get(
                        "detected_vertical", humanization_profile.id
                    ),
                    "active_vertical": humanization_profile.id,
                    "confidence": humanization_vertical_report.get("confidence"),
                    "profile_summary": humanization_profile.summary(),
                },
                rewrite_strength=self.settings.humanization_rewrite_strength,
                redundancy_report=redundancy_report.as_dict(),
            )
        else:
            humanization_result = skipped_editorial_rewrite_result(
                article_model,
                reason="Simplified pipeline: editorial humanization disabled.",
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "humanization_prompt",
            GeneratedContent(
                content_text=humanization_result.prompt,
                content_json={
                    "task_type": ModelTask.HUMANIZATION.value,
                    **self._prompt_metadata(humanization_result.prompt),
                },
                provider="prompt-builder",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "humanization_section_prompts",
            GeneratedContent(
                content_json={
                    "prompts": [record.as_dict(include_prompt=True) for record in humanization_result.prompt_records],
                },
                provider="prompt-builder",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "ai_pattern_report",
            GeneratedContent(content_json=humanization_result.ai_pattern_report, provider="ai-pattern-detector"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "rewritten_sections",
            GeneratedContent(content_json={"sections": humanization_result.rewritten_sections}, provider="humanizer"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "reverted_sections",
            GeneratedContent(content_json={"sections": humanization_result.reverted_sections}, provider="humanizer"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "rewrite_attempts",
            GeneratedContent(content_json={"attempts": humanization_result.rewrite_attempts}, provider="humanizer"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "rewrite_strength_used",
            GeneratedContent(
                content_json={"value": humanization_result.summary.get("rewrite_strength_used")},
                provider="humanizer",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "humanization_quality_report",
            GeneratedContent(content_json=humanization_result.humanization_quality_report, provider="humanizer"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "repeated_phrases_removed",
            GeneratedContent(
                content_json={"phrases": humanization_result.summary.get("repeated_phrases_removed", [])},
                provider="humanizer",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "sections_rewritten",
            GeneratedContent(
                content_json={"count": humanization_result.summary.get("sections_rewritten", 0)},
                provider="humanizer",
            ),
        )
        if humanization_result.generations:
            await self.repositories.artifacts.create_artifact(
                job_id,
                "humanization_raw_response",
                GeneratedContent(
                    content_json={
                        "responses": [
                            {
                                "task_type": generated.task_type,
                                "model": generated.model,
                                "usage": self._usage_dict(generated),
                                "reasoning": self._reasoning_dict(generated),
                                "response": generated.raw_response,
                            }
                            for generated in humanization_result.generations
                        ],
                    },
                    provider=humanization_result.generated.provider if humanization_result.generated else "humanizer",
                    model=humanization_result.generated.model if humanization_result.generated else None,
                    task_type=humanization_result.generated.task_type if humanization_result.generated else ModelTask.HUMANIZATION.value,
                    usage=humanization_result.generated.usage if humanization_result.generated else None,
                ),
            )
        if should_run_humanization(self.settings):
            article_model = humanization_result.article
            article_model = normalize_article(
                article_model.model_dump(),
                defaults=article_defaults,
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "humanization_summary",
            GeneratedContent(content_json=humanization_result.summary, provider="humanizer"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "post_humanized_article_json",
            GeneratedContent(content_json=article_model.model_dump(), provider="humanizer"),
        )
        post_humanization_redundancy_report = self.redundancy_checker.review(article_model)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "post_humanization_redundancy_review",
            GeneratedContent(content_json=post_humanization_redundancy_report.as_dict(), provider="redundancy-checker"),
        )
        for generated in humanization_result.generations:
            metrics.record_model_call("humanization", generated)
        if humanization_result.generated is not None:
            article = humanization_result.generated
        metrics.finish_stage("humanization")
        self._ensure_not_cancelled(job_id)

        await self._mark_progress(job_id, "running_review", "narrative_editor", "Running final narrative editor pass.")
        metrics.start_stage("narrative_editor")
        if should_run_narrative_editor(self.settings):
            narrative_result = await self.narrative_editor.edit(
                content_provider=content_provider,
                article=article_model,
                request_data=asdict(command),
                required_disclaimer=self.settings.biomedical_ruo_disclaimer,
                target_min_word_count=self.settings.target_min_word_count,
                deterministic_checker=self.sanity_checker,
            )
        else:
            narrative_result = skipped_narrative_editor_result(
                article_model,
                reason="Simplified pipeline: narrative editor disabled.",
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "narrative_editor_prompt",
            GeneratedContent(
                content_text=narrative_result.prompt,
                content_json={
                    "task_type": ModelTask.HUMANIZATION.value,
                    **self._prompt_metadata(narrative_result.prompt),
                },
                provider="prompt-builder",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "narrative_pattern_report",
            GeneratedContent(content_json=narrative_result.pattern_report, provider="narrative-editor"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "narrative_editor_summary",
            GeneratedContent(content_json=narrative_result.summary, provider="narrative-editor"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "narrative_editor_edits",
            GeneratedContent(
                content_json={
                    "applied": narrative_result.edits_applied,
                    "skipped": narrative_result.edits_skipped,
                },
                provider="narrative-editor",
            ),
        )
        if narrative_result.generated is not None:
            await self._save_raw_llm_response(job_id, "narrative_editor", narrative_result.generated)
            metrics.record_model_call("narrative_editor", narrative_result.generated)
            article = narrative_result.generated
        if should_run_narrative_editor(self.settings):
            article_model = normalize_article(
                narrative_result.article.model_dump(),
                defaults=article_defaults,
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "post_narrative_editor_article_json",
            GeneratedContent(content_json=article_model.model_dump(), provider="narrative-editor"),
        )
        post_narrative_redundancy_report = self.redundancy_checker.review(article_model)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "post_narrative_redundancy_review",
            GeneratedContent(content_json=post_narrative_redundancy_report.as_dict(), provider="redundancy-checker"),
        )
        metrics.finish_stage("narrative_editor")
        self._ensure_not_cancelled(job_id)

        structured_article = article_model.model_dump()
        article_markdown = article_to_markdown(article_model)
        structured_artifact = GeneratedContent(
            content_json=structured_article,
            provider=article.provider,
            model=article.model,
            usage=article.usage,
            raw_response=article.raw_response,
        )
        await self.repositories.artifacts.create_artifact(job_id, "structured_article_json", structured_artifact)
        await self.repositories.artifacts.create_artifact(job_id, "structured_article", structured_artifact)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "article_markdown",
            GeneratedContent(
                content_text=article_markdown,
                content_json={"source": "structured_article"},
                provider=article.provider,
                model=article.model,
                usage=article.usage,
            ),
        )
        await self._save_raw_llm_response(job_id, "structured_article", article)
        await self.repositories.logs.add_log(
            job_id,
            "info",
            "content_generation",
            "Generated structured article.",
        )
        await self.repositories.jobs.mark_status(job_id, "generated")

        internal_links = await self.internal_links.enrich_markdown(
            markdown=article_markdown,
            product_name=command.product_name,
            product_url=command.product_url,
            target_keyword=command.target_keyword,
            suggested_links=structured_article.get("internal_links", []),
            disclaimer_url=self.settings.research_use_disclaimer_url or None,
            required_disclaimer=compliance_ctx["required_disclaimer"],
        )
        enriched_markdown = internal_links.content_text or article_markdown
        await self.repositories.artifacts.create_artifact(
            job_id,
            "internal_links",
            internal_links,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "internal_link_plan",
            GeneratedContent(content_json=internal_links.content_json or {}, provider="internal-linker"),
        )

        await self.repositories.artifacts.create_artifact(
            job_id,
            "product_data_grounding_plan",
            GeneratedContent(
                content_json={
                    "provider": self.product_data.provider_name,
                    "product_url": command.product_url,
                    "status": "not_implemented",
                    "planned_methods": [
                        "get_product_by_url",
                        "get_product_storage_guidance",
                        "get_product_category",
                        "get_related_products",
                    ],
                    "purpose": "Future grounding for product facts, storage guidance, category choice, and related links.",
                },
                provider=self.product_data.provider_name,
            ),
        )

        metrics.start_stage("image_generation")
        active_image_profile, image_vertical_report = _detect_article_vertical(
            article=article_model,
            command=command,
            configured_vertical=self.settings.opportunity_vertical,
        )
        image_workflow = await self.image_generation.run(
            content_provider=content_provider,
            article=article_model,
            request_data=asdict(command),
            active_vertical_profile=active_image_profile,
            detected_vertical=image_vertical_report.get("detected_vertical", active_image_profile.id),
            safety_context={
                "sanity_checker_rules": self.sanity_checker.rules,
                "biomedical": compliance_ctx["is_biomedical"],
            },
        )
        metrics.record_model_call("image_generation", image_workflow.image_prompt)
        metrics.finish_stage("image_generation")
        for artifact_type, content in {
            "image_placement_plan": image_workflow.image_placement_plan,
            "image_prompt": image_workflow.image_prompt,
            "image_generation_prompt": image_workflow.image_prompt,
            "image_generation_result": image_workflow.image_generation_result,
            "generated_images": image_workflow.generated_images,
            "approved_images": image_workflow.approved_images,
            "rejected_images": image_workflow.rejected_images,
            "image_alt_text": image_workflow.image_alt_text,
            "image_caption": image_workflow.image_caption,
            "image_safety_notes": image_workflow.image_safety_notes,
        }.items():
            await self.repositories.artifacts.create_artifact(job_id, artifact_type, content)

        featured_image = await enrichment.fetch_featured_image(command.target_keyword)
        generated_featured_image = _generated_featured_image(image_workflow.image_generation_result.content_json or {})
        if generated_featured_image:
            featured_image = GeneratedContent(
                content_json=generated_featured_image,
                provider="ai-image-generation",
                model=self.settings.ai_image_model,
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "featured_image",
            featured_image,
        )

        metrics.start_stage("youtube_enrichment")
        youtube_candidates = await enrichment.fetch_youtube_candidates(command.target_keyword, max_results=8)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "youtube_candidates",
            youtube_candidates,
        )
        youtube_evaluation, youtube_video = await self._evaluate_youtube_candidates(
            job_id=job_id,
            command=command,
            structured_article=structured_article,
            candidates=youtube_candidates.content_json.get("candidates", [])
            if youtube_candidates.content_json
            else [],
            content_provider=content_provider,
        )
        metrics.record_model_call("youtube_enrichment", youtube_evaluation)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "youtube_ai_evaluation",
            youtube_evaluation,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "youtube_video",
            youtube_video,
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "youtube_relevance_summary",
            GeneratedContent(
                content_json={
                    "status": (youtube_video.content_json or {}).get("status"),
                    "title": (youtube_video.content_json or {}).get("title"),
                    "channel_title": (youtube_video.content_json or {}).get("channel_title"),
                    "score": (youtube_video.content_json or {}).get("score"),
                    "reason": (youtube_video.content_json or {}).get("selection_reason")
                    or (youtube_video.content_json or {}).get("reason"),
                    "note": "Related media only; does not support article facts unless transcript grounding is added.",
                },
                provider="youtube",
            ),
        )
        metrics.finish_stage("youtube_enrichment")

        await self._mark_progress(job_id, "running_rendering", "rendering", "Rendering article preview.")
        metrics.start_stage("rendering")
        article_html, _editorial_html, renderer_publishable_logs = await self._save_rendered_article_artifacts(
            job_id,
            article=article_model,
            youtube_video=youtube_video.content_json,
            generated_images=image_workflow.image_generation_result.content_json,
        )
        metrics.finish_stage("rendering")
        self._ensure_not_cancelled(job_id)

        metrics.start_stage("quality_review")
        publishable_markdown = article_to_markdown(article_model, surface=ArticleRenderSurface.PUBLISHABLE)
        final_quality_result = run_article_quality_checks(
            article=structured_article,
            markdown=publishable_markdown,
            product_url=command.product_url,
            youtube_video=youtube_video.content_json,
            rendered_html=article_html,
            publishable_html=article_html,
            min_word_count=self.settings.target_min_word_count,
            required_disclaimer=self.settings.biomedical_ruo_disclaimer,
        )
        quality_artifact = GeneratedContent(
            content_json={
                **final_quality_result.as_dict(),
                "task_type": ModelTask.QUALITY_REVIEW.value,
            },
            provider="quality-checker",
        )
        await self.repositories.artifacts.create_artifact(job_id, "final_quality_check_results", quality_artifact)
        await self.repositories.artifacts.create_artifact(job_id, "quality_check_results", quality_artifact)
        await self.repositories.artifacts.create_artifact(job_id, "quality_check", quality_artifact)
        metrics.finish_stage("quality_review")
        self._ensure_not_cancelled(job_id)

        sanity_progress = (
            "Running semantic and deterministic sanity review."
            if should_run_semantic_sanity(self.settings)
            else "Running deterministic sanity guardrails."
        )
        await self._mark_progress(job_id, "running_review", "sanity_review", sanity_progress)
        metrics.start_stage("sanity_review")
        compliance_ctx = await self._generation_compliance_context(command, article_model)
        self.sanity_checker.rules = compliance_ctx["compliance_rules"]
        if should_run_semantic_sanity(self.settings):
            sanity_result = await self.semantic_sanity.review(
                content_provider=content_provider,
                article=article_model,
                request_data=asdict(command),
                rules=self.sanity_checker.rules,
                deterministic_checker=self.sanity_checker,
            )
            await self._save_prompt(job_id, "sanity_check_results", sanity_result.prompt, ModelTask.SANITY_REVIEW)
            if sanity_result.generated is not None:
                await self._save_raw_llm_response(job_id, "sanity_check_results", sanity_result.generated)
                metrics.record_model_call("sanity_review", sanity_result.generated)
            article_model = sanity_result.article
            sanity_report = sanity_result.report
            sanity_rewrite_summary = sanity_result.summary
            sanity_source = "semantic_sanity_review"
            sanity_provider = (
                sanity_result.generated.provider if sanity_result.generated else "semantic-sanity-reviewer"
            )
        else:
            article_model, sanity_report, sanity_rewrite_summary = run_deterministic_sanity_review(
                article=article_model,
                checker=self.sanity_checker,
                request_data=asdict(command),
                defaults=article_defaults,
            )
            sanity_source = "deterministic_sanity_review"
            sanity_provider = "sanity-checker"
        article_model, product_link_report = await self._apply_editorial_product_links(article_model, command)
        structured_article = article_model.model_dump()
        structured_article, _seo_updates, _optimization_report = await self._apply_seo_optimization_to_article(
            job_id,
            structured_article,
            respect_manual_seo=True,
        )
        if _seo_updates:
            await self.repositories.jobs.update_job_seo(job_id, **_seo_updates)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "seo_optimization_report",
            GeneratedContent(content_json=_optimization_report.as_dict(), provider="seo-optimization-pass"),
        )
        article_model = normalize_article(structured_article, defaults=article_defaults)
        article_markdown = article_to_markdown(article_model, surface=ArticleRenderSurface.PUBLISHABLE)
        enriched_markdown = article_markdown
        structured_artifact = GeneratedContent(
            content_json=structured_article,
            provider=sanity_provider,
        )
        await self.repositories.artifacts.create_artifact(job_id, "structured_article_json", structured_artifact)
        await self.repositories.artifacts.create_artifact(job_id, "structured_article", structured_artifact)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "product_link_report",
            GeneratedContent(content_json=product_link_report.as_dict(), provider="product-linker"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "article_markdown",
            GeneratedContent(
                content_text=article_markdown,
                content_json={"source": sanity_source},
                provider=sanity_provider,
            ),
        )
        article_html, _editorial_html, renderer_publishable_logs = await self._save_rendered_article_artifacts(
            job_id,
            article=article_model,
            youtube_video=youtube_video.content_json,
            generated_images=image_workflow.image_generation_result.content_json,
        )
        final_quality_result = run_article_quality_checks(
            article=structured_article,
            markdown=enriched_markdown,
            product_url=command.product_url,
            youtube_video=youtube_video.content_json,
            rendered_html=article_html,
            publishable_html=article_html,
            min_word_count=self.settings.target_min_word_count,
            required_disclaimer=self.settings.biomedical_ruo_disclaimer,
        )
        quality_artifact = GeneratedContent(
            content_json={
                **final_quality_result.as_dict(),
                "task_type": ModelTask.QUALITY_REVIEW.value,
            },
            provider="quality-checker",
        )
        await self.repositories.artifacts.create_artifact(job_id, "final_quality_check_results", quality_artifact)
        await self.repositories.artifacts.create_artifact(job_id, "quality_check_results", quality_artifact)
        await self.repositories.artifacts.create_artifact(job_id, "quality_check", quality_artifact)
        metrics.finish_stage("sanity_review")

        if self.settings.enable_jsonld_schema:
            request_payload = asdict(command)
            request_payload["workspace_name"] = compliance_ctx.get("workspace_name", "")
            request_payload["site_name"] = compliance_ctx.get("site_name", "")
            schema_jsonld = build_schema_jsonld(
                article=article_model,
                request_data=request_payload,
                youtube_video=youtube_video.content_json,
                category={
                    "id": command.wordpress_category_id or command.category_id,
                    "name": command.wordpress_category_name or command.category_name,
                    "slug": command.wordpress_category_slug or command.category_slug,
                },
                organization_name=compliance_ctx["publisher_name"],
            )
            await self.repositories.artifacts.create_artifact(
                job_id,
                "schema_jsonld",
                GeneratedContent(content_json={"schemas": schema_jsonld}, provider="schema-jsonld"),
            )

        await self.repositories.artifacts.create_artifact(
            job_id,
            "sanity_check_results",
            GeneratedContent(content_json=sanity_report.as_dict(), provider="sanity-checker"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "sanity_rewrite_summary",
            GeneratedContent(content_json=sanity_rewrite_summary, provider="sanity-checker"),
        )

        seo_metadata = {
            "meta_title": structured_article.get("meta_title"),
            "meta_description": structured_article.get("meta_description"),
            "slug": structured_article.get("slug"),
            "excerpt": structured_article.get("excerpt"),
            "primary_keyword": structured_article.get("primary_keyword"),
            "secondary_keywords": structured_article.get("secondary_keywords", []),
            "markdown_source": "publishable",
            "publishable_markdown_excerpt": article_markdown[:4000],
        }
        await self.repositories.artifacts.create_artifact(
            job_id,
            "seo_metadata",
            GeneratedContent(content_json=seo_metadata, provider=article.provider, model=article.model),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "meta_title",
            GeneratedContent(content_text=str(structured_article.get("meta_title") or ""), provider=article.provider),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "meta_description",
            GeneratedContent(content_text=str(structured_article.get("meta_description") or ""), provider=article.provider),
        )

        social_posts = structured_article.get("social_posts", {}) or {}
        x_post = GeneratedContent(content_text=social_posts.get("x", ""), provider=article.provider, model=article.model)
        threads_post = GeneratedContent(content_text=social_posts.get("threads", ""), provider=article.provider, model=article.model)
        await self.repositories.artifacts.create_artifact(job_id, "x_post", x_post)
        await self.repositories.artifacts.create_artifact(job_id, "threads_post", threads_post)
        await self.repositories.artifacts.create_artifact(
            job_id,
            "suggested_external_references",
            GeneratedContent(
                content_json={"references": structured_article.get("references_to_verify", [])},
                provider=article.provider,
                model=article.model,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "references_to_verify",
            GeneratedContent(
                content_json={"references": structured_article.get("references_to_verify", [])},
                provider=article.provider,
                model=article.model,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "backlink_plan",
            GeneratedContent(
                content_json={
                    "requires_human_approval": True,
                    "plan": structured_article.get("backlink_plan", []),
                },
                provider=article.provider,
                model=article.model,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "social_posts",
            GeneratedContent(
                content_json=structured_article.get("social_posts", {}),
                provider=article.provider,
                model=article.model,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "study_cards",
            GeneratedContent(content_json={"study_cards": structured_article.get("study_cards", [])}, provider=article.provider),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "research_metadata_panel",
            GeneratedContent(
                content_json=structured_article.get("research_metadata_panel") or {},
                provider=article.provider,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "rich_components_json",
            GeneratedContent(
                content_json={
                    "callout_boxes": structured_article.get("callout_boxes", []),
                    "research_insights": structured_article.get("research_insights", []),
                    "study_cards": structured_article.get("study_cards", []),
                    "definition_boxes": structured_article.get("definition_boxes", []),
                    "caution_boxes": structured_article.get("caution_boxes", []),
                    "comparison_tables": structured_article.get("comparison_tables", []),
                    "related_topics": structured_article.get("related_topics", []),
                },
                provider=article.provider,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "category_selection",
            GeneratedContent(
                content_json={
                    "category_id": command.wordpress_category_id or command.category_id,
                    "category_slug": command.wordpress_category_slug or command.category_slug,
                    "category_name": command.wordpress_category_name or command.category_name,
                },
                provider="job-input",
            ),
        )
        tag_suggestions = self._tag_suggestions(command, structured_article)
        presentation_metadata = self._presentation_metadata_from_command(
            command=command,
            structured_article=structured_article,
            featured_image=featured_image.content_json,
            tag_suggestions=tag_suggestions,
        )
        available_templates = await self._safe_wordpress_templates()
        available_categories = await self._safe_wordpress_categories()
        metrics.start_stage("publish_decision")
        decision_result = await self.publish_decisions.decide(
            content_provider=content_provider,
            request_input=asdict(command),
            structured_article=structured_article,
            initial_metadata=presentation_metadata,
            featured_image=featured_image.content_json,
            available_templates=available_templates,
            available_categories=available_categories,
            publish_policy=policy.mode,
            quality_passed=final_quality_result.passed,
            sanity_passed=sanity_report.passed,
            unattended_mode=command.unattended_mode,
        )
        metrics.record_model_call("publish_decision", decision_result.generated if hasattr(decision_result, "generated") else None)
        metrics.finish_stage("publish_decision")
        presentation_metadata = decision_result.metadata
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_tag_suggestions",
            GeneratedContent(content_json={"tags": tag_suggestions}, provider="job-input"),
        )
        for artifact_type, payload in {
            "publish_decision_report": decision_result.report,
            **decision_result.artifacts,
        }.items():
            await self.repositories.artifacts.create_artifact(
                job_id,
                artifact_type,
                GeneratedContent(content_json=payload, provider="publish-decision-service"),
            )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_presentation_metadata",
            GeneratedContent(content_json=presentation_metadata, provider="job-input"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_template_selection",
            GeneratedContent(
                content_json={"template": presentation_metadata.get("wordpress_template")},
                provider="job-input",
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "wordpress_category_selection",
            GeneratedContent(
                content_json={
                    "category_id": presentation_metadata.get("wordpress_category_id"),
                    "category_slug": presentation_metadata.get("wordpress_category_slug"),
                    "category_name": presentation_metadata.get("wordpress_category_name"),
                },
                provider="job-input",
            ),
        )

        wordpress_post = GeneratedContent(content_json=None, provider="wordpress")
        final_status = "failed_quality"
        if final_quality_result.passed and sanity_report.passed:
            final_status = "ready_for_review"
            auto_publish_status = str(presentation_metadata.get("publish_status") or "none")
            if auto_publish_status == "draft":
                try:
                    await self._mark_progress(job_id, "running_publish", "wordpress_publish", "Publishing automatic WordPress draft.")
                    metrics.start_stage("wordpress_publish")
                    wordpress_post = await self._publish_to_wordpress(
                        job_id=job_id,
                        title=structured_article.get("title") or command.title,
                        article_html=article_html,
                        status="draft",
                        excerpt=structured_article.get("excerpt"),
                        categories=await self._resolve_category_ids(presentation_metadata),
                        presentation_metadata=presentation_metadata,
                    )
                    metrics.finish_stage("wordpress_publish")
                    final_status = "published_draft"
                except Exception as exc:
                    metrics.fail_stage("wordpress_publish", str(exc))
                    await self.repositories.logs.add_log(
                        job_id,
                        "error",
                        "wordpress_publish",
                        "Automatic draft publishing failed.",
                        {"error": str(exc)},
                    )
                    final_status = "failed_publish"
            elif auto_publish_status == "publish":
                await self.repositories.logs.add_log(
                    job_id,
                    "warning",
                    "wordpress_publish",
                    "Automatic live publishing is not supported. Connector Phase 1 supports drafts only.",
                    {"requested_status": "publish"},
                )
            elif policy.mode == "auto_live":
                await self.repositories.logs.add_log(
                    job_id,
                    "warning",
                    "publish_policy",
                    "auto_live requested but unattended live publishing is not fully enabled; article is ready for review.",
                    decision_result.report.get("publish", {}),
                )
        else:
            failed_step = "sanity_check" if final_quality_result.passed and not sanity_report.passed else "quality_check"
            final_status = "failed_sanity" if failed_step == "sanity_check" else "failed_quality"
            await self.repositories.logs.add_log(
                job_id,
                "warning",
                failed_step,
                "Article is not ready for publishing.",
                {
                    "quality_check": final_quality_result.as_dict(),
                    "sanity_check": sanity_report.as_dict(),
                },
            )

        run_metric_artifacts = metrics.artifacts(
            repair_pass_count=repair_pass_count if repair_summary.get("attempted") else 0,
            expansion_pass_count=int(expansion_result.summary.get("pass_count") or 0),
            final_word_count=final_quality_result.word_count,
            final_quality_status=final_quality_result.status,
            final_sanity_status=str(sanity_report.status),
        )
        for artifact_type, payload in run_metric_artifacts.items():
            await self.repositories.artifacts.create_artifact(
                job_id,
                artifact_type,
                GeneratedContent(content_json=payload, provider="run-metrics"),
            )

        return {
            "job_id": job_id,
            "status": final_status,
            "human_review_required": policy.human_review_required,
            "publish_policy": policy.mode,
            "wordpress_post": wordpress_post.content_json,
            "featured_image": featured_image.content_json,
            "youtube_video": youtube_video.content_json,
            "x_post": x_post.content_text,
            "threads_post": threads_post.content_text,
            "quality_check": final_quality_result.as_dict(),
            "initial_quality_check": initial_quality_result.as_dict(),
            "final_quality_check": final_quality_result.as_dict(),
            "sanity_check": sanity_report.as_dict(),
            "sanity_rewrite_summary": sanity_rewrite_summary,
            "repair_attempted": bool(repair_summary.get("attempted")),
            "repair_pass_count": repair_pass_count if repair_summary.get("attempted") else 0,
            "repair_summary": repair_summary,
            "section_expansion_attempted": bool(expansion_result.summary.get("attempted")),
            "section_expansion_summary": expansion_result.summary,
            "redundancy_review": redundancy_report.as_dict(),
            "redundancy_cleanup_summary": redundancy_cleanup_summary,
            "post_humanization_redundancy_review": post_humanization_redundancy_report.as_dict(),
            "ai_pattern_report": humanization_result.ai_pattern_report,
            "humanization_summary": humanization_result.summary,
            "rewritten_sections": {"sections": humanization_result.rewritten_sections},
            "rewrite_attempts": {"attempts": humanization_result.rewrite_attempts},
            "rewrite_strength_used": {"value": humanization_result.summary.get("rewrite_strength_used")},
            "humanization_quality_report": humanization_result.humanization_quality_report,
            "repeated_phrases_removed": {"phrases": humanization_result.summary.get("repeated_phrases_removed", [])},
            "sections_rewritten": {"count": humanization_result.summary.get("sections_rewritten", 0)},
            "reverted_sections": {"sections": humanization_result.reverted_sections},
            "narrative_pattern_report": narrative_result.pattern_report,
            "narrative_editor_summary": narrative_result.summary,
            "narrative_editor_edits": {
                "applied": narrative_result.edits_applied,
                "skipped": narrative_result.edits_skipped,
            },
            "post_narrative_redundancy_review": post_narrative_redundancy_report.as_dict(),
            "model_pipeline": self._model_pipeline(
                [
                    initial_article_generation,
                    *repair_generations,
                    *(record.generated for record in expansion_result.prompt_records if record.generated),
                    *humanization_result.generations,
                    narrative_result.generated,
                    youtube_evaluation,
                ]
            ),
            "backlink_plan": structured_article.get("backlink_plan", []),
            "suggested_external_references": structured_article.get("references_to_verify", []),
            "wordpress_presentation_metadata": presentation_metadata,
            "wordpress_tag_suggestions": tag_suggestions,
            "publish_decision_report": decision_result.report,
            "structured_article": structured_article,
            "rendered_html": article_html,
            "renderer_logs": renderer_publishable_logs,
            "job_run_metrics": run_metric_artifacts["job_run_metrics"],
            "stage_timing_summary": run_metric_artifacts["stage_timing_summary"],
            "model_cost_summary": run_metric_artifacts["model_cost_summary"],
            "image_placement_plan": image_workflow.image_placement_plan.content_json,
            "image_generation_result": image_workflow.image_generation_result.content_json,
            "generated_images": image_workflow.generated_images.content_json,
            "approved_images": image_workflow.approved_images.content_json,
            "rejected_images": image_workflow.rejected_images.content_json,
            "image_rendering_summary": _image_rendering_summary(
                image_workflow.image_generation_result.content_json or {},
                renderer_publishable_logs,
            ),
        }

    async def publish_existing_job(
        self,
        job_id: str,
        status: str,
        confirm_live_publish: bool = False,
        category_id: int | None = None,
        wordpress_template: str | None = None,
        wordpress_category_id: int | None = None,
        wordpress_category_slug: str | None = None,
        wordpress_category_name: str | None = None,
        wordpress_tags: list[str] | None = None,
        featured_image_id: int | None = None,
        featured_image_url: str | None = None,
        featured_image_alt: str | None = None,
    ) -> dict[str, Any]:
        del confirm_live_publish, category_id, wordpress_template, wordpress_category_id
        del wordpress_category_slug, wordpress_category_name, wordpress_tags
        del featured_image_id, featured_image_url, featured_image_alt
        if status != "draft":
            raise ValueError("Live publishing is not supported. Connector Phase 1 supports drafts only.")

        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")

        quality = await self._latest_artifact_json(job_id, "final_quality_check_results")
        if not quality:
            quality = await self._latest_artifact_json(job_id, "quality_check_results")
        if not quality or not quality.get("passed"):
            raise ValueError("Publishing is blocked because final quality did not pass.")

        sanity = await self._latest_artifact_json(job_id, "sanity_check_results")
        if not sanity or not sanity.get("passed"):
            raise ValueError("Publishing is blocked because the domain sanity check did not pass.")

        article_html = await self._resolve_publishable_html(job_id)
        if not article_html:
            raise ValueError("Publishable HTML artifact is missing.")

        try:
            await self._mark_progress(job_id, "running_publish", "wordpress_publish", "Creating WordPress draft via connector.")
            wordpress_post = await self._publish_to_wordpress(
                job_id=job_id,
                title="",
                article_html=article_html,
                status="draft",
            )
        except Exception as exc:
            await self.repositories.jobs.mark_status(job_id, "failed_publish", str(exc))
            await self.repositories.logs.add_log(
                job_id,
                "error",
                "wordpress_publish",
                "WordPress draft creation failed.",
                {"error": str(exc)},
            )
            raise
        await self.repositories.jobs.mark_status(job_id, "published_draft")
        return {
            "job_id": job_id,
            "status": "published_draft",
            "wordpress_post": wordpress_post.content_json,
        }

    async def run_sanity_check_for_job(
        self,
        job_id: str,
        apply_rewrite: bool = True,
    ) -> dict[str, Any]:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")

        structured_article = await self._latest_artifact_json(job_id, "structured_article_json")
        if not structured_article:
            structured_article = await self._latest_artifact_json(job_id, "structured_article")
        if not structured_article:
            raise ValueError("Structured article artifact is missing.")

        request_input = job.get("request_input", {})
        article_model = normalize_article(
            structured_article,
            defaults={
                "title": str(request_input.get("title") or ""),
                "target_keyword": str(request_input.get("target_keyword") or ""),
                "product_name": str(request_input.get("product_name") or ""),
                "product_url": str(request_input.get("product_url") or ""),
            },
        )
        rendered_html = await self._latest_artifact_text(job_id, "rendered_html") or ""
        youtube_video = await self._latest_artifact_json(job_id, "youtube_video")

        if not rendered_html:
            rendered_html, _editorial_html, _ = await self._save_rendered_article_artifacts(
                job_id,
                article=article_model,
                youtube_video=youtube_video,
            )

        if apply_rewrite:
            sanity_result = await self.semantic_sanity.review(
                content_provider=self.registry.content_generation,
                article=article_model,
                request_data=request_input,
                rules=self.sanity_checker.rules,
                deterministic_checker=self.sanity_checker,
            )
            await self._save_prompt(job_id, "sanity_check_results", sanity_result.prompt, ModelTask.SANITY_REVIEW)
            if sanity_result.generated is not None:
                await self._save_raw_llm_response(job_id, "sanity_check_results", sanity_result.generated)
            article_model = sanity_result.article
            sanity_report = sanity_result.report
            sanity_rewrite_summary = sanity_result.summary
            structured_article = article_model.model_dump()
            article_markdown = article_to_markdown(article_model, surface=ArticleRenderSurface.PUBLISHABLE)
            await self.repositories.artifacts.create_artifact(
                job_id,
                "structured_article_json",
                GeneratedContent(content_json=structured_article, provider="semantic-sanity-reviewer"),
            )
            await self.repositories.artifacts.create_artifact(
                job_id,
                "structured_article",
                GeneratedContent(content_json=structured_article, provider="semantic-sanity-reviewer"),
            )
            await self.repositories.artifacts.create_artifact(
                job_id,
                "article_markdown",
                GeneratedContent(
                    content_text=article_markdown,
                    content_json={"source": "manual_semantic_sanity_review", "surface": "publishable"},
                    provider="semantic-sanity-reviewer",
                ),
            )
            rendered_html, _editorial_html, _ = await self._save_rendered_article_artifacts(
                job_id,
                article=article_model,
                youtube_video=youtube_video,
            )
            final_quality_result = run_article_quality_checks(
                article=structured_article,
                markdown=article_markdown,
                product_url=str(request_input.get("product_url") or ""),
                youtube_video=youtube_video,
                rendered_html=rendered_html,
                publishable_html=rendered_html,
                min_word_count=self.settings.target_min_word_count,
                required_disclaimer=self.settings.biomedical_ruo_disclaimer,
            )
            quality_artifact = GeneratedContent(
                content_json={
                    **final_quality_result.as_dict(),
                    "task_type": ModelTask.QUALITY_REVIEW.value,
                },
                provider="quality-checker",
            )
            await self.repositories.artifacts.create_artifact(job_id, "final_quality_check_results", quality_artifact)
            await self.repositories.artifacts.create_artifact(job_id, "quality_check_results", quality_artifact)
            await self.repositories.artifacts.create_artifact(job_id, "quality_check", quality_artifact)
        else:
            sanity_report = self.sanity_checker.check(
                article=article_model,
                rendered_html=rendered_html,
                product_data=request_input,
            )
            sanity_rewrite_summary = {
                "attempted": False,
                "changed_locations": [],
                "reason": "Manual sanity check ran deterministic guardrails without rewrite.",
            }

        await self.repositories.artifacts.create_artifact(
            job_id,
            "sanity_check_results",
            GeneratedContent(content_json=sanity_report.as_dict(), provider="sanity-checker"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "sanity_rewrite_summary",
            GeneratedContent(content_json=sanity_rewrite_summary, provider="sanity-checker"),
        )

        quality = await self._latest_artifact_json(job_id, "final_quality_check_results")
        if quality and quality.get("passed") and sanity_report.passed:
            final_status = "ready_for_review"
        elif not sanity_report.passed:
            final_status = "failed_sanity"
        else:
            final_status = job.get("status") or "generated"
        await self.repositories.jobs.mark_status(job_id, final_status)
        await self.repositories.logs.add_log(
            job_id,
            "info",
            "sanity_check",
            f"Manual sanity check finished with status {sanity_report.status}.",
            sanity_report.as_dict(),
        )
        return {
            "job_id": job_id,
            "status": final_status,
            "sanity_check": sanity_report.as_dict(),
            "sanity_rewrite_summary": sanity_rewrite_summary,
        }

    async def _publish_to_wordpress(
        self,
        job_id: str,
        title: str,
        article_html: str,
        status: str,
        excerpt: str | None = None,
        categories: list[int] | None = None,
        presentation_metadata: dict[str, Any] | None = None,
    ) -> GeneratedContent:
        del title, excerpt, categories, presentation_metadata
        if status != "draft":
            raise ValueError("Live publishing is not supported. Connector Phase 1 supports drafts only.")
        if self.wordpress_connector_service is None:
            raise ValueError("WordPress connector service is not configured.")
        if not article_html:
            raise ValueError("Publishable HTML artifact is missing.")

        result = await self.wordpress_connector_service.create_wordpress_draft(job_id)
        structured_article = await self._latest_artifact_json(job_id, "structured_article_json") or {}
        job = await self.repositories.jobs.get_job(job_id) or {}
        resolved_title = str(
            structured_article.get("title")
            or (job.get("request_input") or {}).get("title")
            or "Untitled"
        )
        content_json = {
            "id": result.get("wordpress_post_id"),
            "link": result.get("wordpress_public_url"),
            "edit_url": result.get("wordpress_edit_url"),
            "status": result.get("wordpress_status") or "draft",
            "connector_status": result.get("status"),
            "message": result.get("message"),
            "provider": "trendplot-connector-phase1",
        }
        wordpress_post = GeneratedContent(content_json=content_json, provider="trendplot-connector-phase1")
        await self.repositories.artifacts.create_artifact(job_id, "wordpress_post", wordpress_post)
        await self.repositories.artifacts.create_artifact(job_id, "wordpress_publish_response", wordpress_post)
        await self._record_trendplot_publish_inventory(
            job_id,
            title=resolved_title,
            wordpress_post=wordpress_post,
            publish_status="draft",
        )
        return wordpress_post

    async def _record_trendplot_publish_inventory(
        self,
        job_id: str,
        *,
        title: str,
        wordpress_post: GeneratedContent | dict[str, Any],
        publish_status: str,
    ) -> None:
        job = await self.repositories.jobs.get_job(job_id)
        workspace_id = str((job or {}).get("workspace_id") or "")
        if not workspace_id:
            return
        payload = wordpress_post.content_json if isinstance(wordpress_post, GeneratedContent) else wordpress_post
        if not isinstance(payload, dict):
            payload = {}
        url = str(payload.get("link") or payload.get("url") or "")
        post_id = str(payload.get("id") or "")
        from app.content_inventory import inventory_item_from_trendplot_publish

        item = inventory_item_from_trendplot_publish(
            workspace_id=workspace_id,
            job_id=job_id,
            title=title,
            url=url,
            wordpress_post_id=post_id or None,
            published_at=payload.get("date") or payload.get("published_at"),
        )
        try:
            await self.repositories.workspace_content_inventory.upsert_page(workspace_id, item)
            await self.repositories.published_content.create(
                workspace_id,
                {
                    "job_id": job_id,
                    "external_id": post_id,
                    "url": url,
                    "title": title,
                    "status": publish_status,
                    "channel": "wordpress",
                    "metrics": {"created_by_trendplot": True, "trendplot_job_id": job_id},
                },
            )
        except Exception:
            logger.exception("Failed to record Trendplot content inventory for job %s", job_id)

    async def _safe_wordpress_templates(self) -> list[dict[str, Any]]:
        try:
            return await self.registry.wordpress.list_templates()
        except Exception:
            return [
                {"key": "elementor_header_footer", "label": "Elementor Full Width", "default": True},
                {"key": "", "label": "Default theme template"},
            ]

    async def _safe_wordpress_categories(self) -> list[dict[str, Any]]:
        try:
            return await self.registry.wordpress.list_categories()
        except Exception:
            return []

    async def _resolve_category_ids(self, presentation_metadata: dict[str, Any]) -> list[int]:
        category_id = presentation_metadata.get("wordpress_category_id")
        if category_id:
            return [int(category_id)]

        slug = str(presentation_metadata.get("wordpress_category_slug") or "").strip().lower()
        name = str(presentation_metadata.get("wordpress_category_name") or "").strip().lower()
        if not slug and not name:
            return []

        categories = await self.registry.wordpress.list_categories()
        for category in categories:
            if slug and str(category.get("slug") or "").strip().lower() == slug:
                return [int(category["id"])]
            if name and str(category.get("name") or "").strip().lower() == name:
                return [int(category["id"])]
        return []

    async def _resolve_featured_image(self, presentation_metadata: dict[str, Any]) -> dict[str, Any]:
        featured_image_id = presentation_metadata.get("featured_image_id")
        if featured_image_id:
            return {"id": int(featured_image_id), "source": "provided_media_id", "status": "selected"}

        featured_image_path = str(presentation_metadata.get("featured_image_local_path") or "").strip()
        if featured_image_path:
            return await self.registry.wordpress.upload_featured_image_from_path(
                image_path=featured_image_path,
                alt_text=str(presentation_metadata.get("featured_image_alt") or ""),
            )

        featured_image_url = str(presentation_metadata.get("featured_image_url") or "").strip()
        if not featured_image_url:
            return {"id": None, "status": "missing", "reason": "No featured image selected."}
        if "placehold.co" in featured_image_url.lower():
            return {"id": None, "status": "skipped", "reason": "Placeholder featured images are not uploaded."}

        return await self.registry.wordpress.upload_featured_image_from_url(
            image_url=featured_image_url,
            alt_text=str(presentation_metadata.get("featured_image_alt") or ""),
        )

    def _presentation_metadata_from_command(
        self,
        command: GenerateArticleCommand,
        structured_article: dict[str, Any],
        featured_image: dict[str, Any] | None,
        tag_suggestions: list[str],
    ) -> dict[str, Any]:
        image = featured_image or {}
        return {
            "wordpress_template": command.wordpress_template,
            "wordpress_category_id": command.wordpress_category_id or command.category_id,
            "wordpress_category_slug": command.wordpress_category_slug or command.category_slug,
            "wordpress_category_name": command.wordpress_category_name or command.category_name,
            "wordpress_tags": _clean_publish_tags(command.wordpress_tags, self.settings.wordpress_max_tags),
            "featured_image_id": command.featured_image_id,
            "featured_image_url": command.featured_image_url or image.get("url"),
            "featured_image_local_path": image.get("local_path"),
            "featured_image_alt": command.featured_image_alt or image.get("alt_text") or structured_article.get("title") or "",
        }

    def _presentation_metadata_from_publish_request(
        self,
        request_input: dict[str, Any],
        structured_article: dict[str, Any],
        existing_metadata: dict[str, Any],
        category_id: int | None = None,
        wordpress_template: str | None = None,
        wordpress_category_id: int | None = None,
        wordpress_category_slug: str | None = None,
        wordpress_category_name: str | None = None,
        wordpress_tags: list[str] | None = None,
        featured_image_id: int | None = None,
        featured_image_url: str | None = None,
        featured_image_alt: str | None = None,
    ) -> dict[str, Any]:
        fallback_tags = _clean_publish_tags(
            existing_metadata.get("wordpress_tags")
            or request_input.get("wordpress_tags")
            or self._tag_suggestions_from_request(request_input, structured_article),
            self.settings.wordpress_max_tags,
        )
        return {
            "wordpress_template": wordpress_template
            or existing_metadata.get("wordpress_template")
            or request_input.get("wordpress_template")
            or self.settings.wordpress_default_template,
            "wordpress_category_id": wordpress_category_id
            or category_id
            or existing_metadata.get("wordpress_category_id")
            or request_input.get("wordpress_category_id")
            or request_input.get("category_id"),
            "wordpress_category_slug": wordpress_category_slug
            or existing_metadata.get("wordpress_category_slug")
            or request_input.get("wordpress_category_slug")
            or request_input.get("category_slug"),
            "wordpress_category_name": wordpress_category_name
            or existing_metadata.get("wordpress_category_name")
            or request_input.get("wordpress_category_name")
            or request_input.get("category_name"),
            "wordpress_tags": _clean_publish_tags(wordpress_tags or fallback_tags, self.settings.wordpress_max_tags),
            "featured_image_id": featured_image_id
            or existing_metadata.get("featured_image_id")
            or request_input.get("featured_image_id"),
            "featured_image_url": featured_image_url
            or existing_metadata.get("featured_image_url")
            or request_input.get("featured_image_url"),
            "featured_image_local_path": existing_metadata.get("featured_image_local_path"),
            "featured_image_alt": featured_image_alt
            or existing_metadata.get("featured_image_alt")
            or request_input.get("featured_image_alt")
            or structured_article.get("title")
            or "",
        }

    def _tag_suggestions(self, command: GenerateArticleCommand, structured_article: dict[str, Any]) -> list[str]:
        tags = [
            structured_article.get("primary_keyword"),
            command.target_keyword,
            command.product_name,
            *(structured_article.get("secondary_keywords") or []),
        ]
        return _clean_publish_tags(tags, self.settings.wordpress_max_tags)

    def _tag_suggestions_from_request(
        self,
        request_input: dict[str, Any],
        structured_article: dict[str, Any],
    ) -> list[str]:
        tags = [
            structured_article.get("primary_keyword"),
            request_input.get("target_keyword"),
            request_input.get("product_name"),
            *(structured_article.get("secondary_keywords") or []),
        ]
        return _clean_publish_tags(tags, self.settings.wordpress_max_tags)

    async def _latest_artifact_json(self, job_id: str, artifact_type: str) -> dict[str, Any] | None:
        artifact = await self.repositories.artifacts.get_latest_artifact(job_id, artifact_type)
        if artifact is None or not artifact.get("content_json"):
            return None
        return json.loads(artifact["content_json"])

    async def _latest_artifact_text(self, job_id: str, artifact_type: str) -> str | None:
        artifact = await self.repositories.artifacts.get_latest_artifact(job_id, artifact_type)
        if artifact is None:
            return None
        return artifact.get("content_text")

    async def _mark_progress(
        self,
        job_id: str,
        status: str,
        step: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self.repositories.jobs.mark_status(job_id, status)
        await self.repositories.logs.add_log(job_id, "info", step, message, context)

    def _category_ids(self, command: GenerateArticleCommand) -> list[int]:
        category_id = command.wordpress_category_id or command.category_id
        return [int(category_id)] if category_id else []

    def _category_ids_from_input(self, request_input: dict[str, Any]) -> list[int]:
        category_id = request_input.get("wordpress_category_id") or request_input.get("category_id")
        return [int(category_id)] if category_id else []

    def _normalize_structured_article(
        self,
        generated: GeneratedContent,
        command: GenerateArticleCommand,
    ) -> ArticleSchema:
        content = generated.content_json or {"article_markdown": generated.content_text or ""}
        return normalize_article(
            content,
            defaults={
                "title": command.title,
                "target_keyword": command.target_keyword,
                "product_name": command.product_name,
                "product_url": command.product_url,
            },
        )

    async def _evaluate_youtube_candidates(
        self,
        job_id: str,
        command: GenerateArticleCommand,
        structured_article: dict[str, Any],
        candidates: list[dict[str, Any]],
        content_provider: Any,
    ) -> tuple[GeneratedContent, GeneratedContent]:
        if not candidates:
            evaluation = GeneratedContent(
                content_json={
                    "selected_video_id": "",
                    "score": 0,
                    "reason": "",
                    "reject_reason": "No YouTube candidates were returned.",
                },
                provider="youtube-ai-evaluator",
            )
            video = GeneratedContent(
                content_json={
                    "query": command.target_keyword,
                    "video": None,
                    "status": "not_selected",
                    "reason": "No candidates available.",
                },
                provider="youtube",
            )
            return evaluation, video

        if not should_run_youtube_ai_evaluation(self.settings):
            selected = max(
                candidates,
                key=lambda candidate: int(candidate.get("view_count") or 0),
            )
            video_id = str(selected.get("video_id") or "")
            evaluation = GeneratedContent(
                content_json={
                    "selected_video_id": video_id,
                    "score": 75,
                    "reason": "Heuristic selection: highest view count (AI evaluation disabled).",
                    "reject_reason": "",
                    "selection_mode": "heuristic",
                },
                provider="youtube-heuristic",
            )
            video = GeneratedContent(
                content_json={
                    **selected,
                    "query": command.target_keyword,
                    "embed_url": f"https://www.youtube.com/embed/{video_id}" if video_id else "",
                    "status": "selected",
                    "score": 75,
                    "selection_reason": evaluation.content_json["reason"],
                },
                provider="youtube",
            )
            return evaluation, video

        outline = self._article_outline(structured_article)
        prompt = build_youtube_evaluation_prompt(
            article_title=structured_article.get("title") or command.title,
            target_keyword=command.target_keyword,
            product_name=command.product_name,
            article_outline=outline,
            candidates=candidates,
        )
        await self._save_prompt(job_id, "youtube_ai_evaluation", prompt, ModelTask.YOUTUBE_EVALUATION)

        try:
            evaluation = await content_provider.evaluate_youtube_candidates(prompt)
            payload = evaluation.content_json or {}
            selected_video_id = str(payload.get("selected_video_id") or "")
            score = int(payload.get("score") or 0)
            selected = next(
                (candidate for candidate in candidates if candidate.get("video_id") == selected_video_id),
                None,
            )

            if selected and score >= 70:
                video = GeneratedContent(
                    content_json={
                        **selected,
                        "query": command.target_keyword,
                        "embed_url": f"https://www.youtube.com/embed/{selected['video_id']}",
                        "status": "selected",
                        "score": score,
                        "selection_reason": payload.get("reason", ""),
                    },
                    provider="youtube",
                )
            else:
                video = GeneratedContent(
                    content_json={
                        "query": command.target_keyword,
                        "video": None,
                        "status": "not_selected",
                        "score": score,
                        "reason": payload.get("reject_reason")
                        or "No candidate reached the relevance threshold.",
                    },
                    provider="youtube",
                )

            await self._save_raw_llm_response(job_id, "youtube_ai_evaluation", evaluation)
            return evaluation, video
        except Exception as exc:
            await self.repositories.logs.add_log(
                job_id,
                "warning",
                "youtube_ai_evaluation",
                "YouTube candidate evaluation failed; article generation will continue without a video.",
                {"error": str(exc)},
            )
            evaluation = GeneratedContent(
                content_json={
                    "selected_video_id": "",
                    "score": 0,
                    "reason": "",
                    "reject_reason": f"AI evaluation failed: {exc}",
                },
                provider="youtube-ai-evaluator",
            )
            video = GeneratedContent(
                content_json={
                    "query": command.target_keyword,
                    "video": None,
                    "status": "evaluation_failed",
                    "reason": str(exc),
                },
                provider="youtube",
            )
            return evaluation, video

    def _article_outline(self, structured_article: dict[str, Any]) -> str:
        article = ArticleSchema.model_validate(structured_article)
        outline = article_outline(article)
        if outline:
            return outline
        return article_to_markdown(article)[:1500]

    async def _save_prompt(
        self,
        job_id: str,
        target_artifact_type: str,
        prompt: str,
        task_type: ModelTask | str | None = None,
    ) -> None:
        await self.repositories.artifacts.create_artifact(
            job_id,
            "prompt",
            GeneratedContent(
                content_text=prompt,
                content_json={
                    "target_artifact_type": target_artifact_type,
                    "task_type": str(task_type.value if isinstance(task_type, ModelTask) else task_type or ""),
                    **self._prompt_metadata(prompt),
                },
                provider="prompt-builder",
            ),
        )

    def _prompt_metadata(self, prompt: str) -> dict[str, Any]:
        metadata = getattr(prompt, "prompt_metadata", None)
        return dict(metadata) if isinstance(metadata, dict) else {}

    async def _save_raw_llm_response(
        self,
        job_id: str,
        target_artifact_type: str,
        generated: GeneratedContent,
    ) -> None:
        if generated.raw_response is None:
            return
        await self.repositories.artifacts.create_artifact(
            job_id,
            "raw_llm_response",
            GeneratedContent(
                content_json={
                    "target_artifact_type": target_artifact_type,
                    "task_type": generated.task_type,
                    "model": generated.model,
                    "usage": self._usage_dict(generated),
                    "reasoning": self._reasoning_dict(generated),
                    "response": generated.raw_response,
                },
                provider=generated.provider,
                model=generated.model,
                task_type=generated.task_type,
                usage=generated.usage,
            ),
        )

    def _usage_dict(self, generated: GeneratedContent | None) -> dict[str, Any] | None:
        if generated is None or generated.usage is None:
            return None
        return {
            "token_input": generated.usage.token_input,
            "token_output": generated.usage.token_output,
            "estimated_cost": generated.usage.estimated_cost,
        }

    def _model_pipeline(self, generated_items: list[GeneratedContent]) -> list[dict[str, Any]]:
        steps = []
        for generated in generated_items:
            if generated is None:
                continue
            usage = self._usage_dict(generated)
            steps.append(
                {
                    "task_type": generated.task_type,
                    "provider": generated.provider,
                    "model": generated.model,
                    "token_input": usage.get("token_input") if usage else None,
                    "token_output": usage.get("token_output") if usage else None,
                    "estimated_cost": usage.get("estimated_cost") if usage else None,
                    "reasoning_enabled": generated.reasoning_enabled,
                    "reasoning_supported": generated.reasoning_supported,
                    "reasoning_effort": generated.reasoning_effort,
                }
            )
        return steps

    def _reasoning_dict(self, generated: GeneratedContent | None) -> dict[str, Any] | None:
        if generated is None:
            return None
        return {
            "enabled": generated.reasoning_enabled,
            "supported": generated.reasoning_supported,
            "effort": generated.reasoning_effort,
            "source": generated.reasoning_source,
        }

    async def _save_rendered_article_artifacts(
        self,
        job_id: str,
        *,
        article: ArticleSchema,
        youtube_video: dict | None = None,
        generated_images: dict | None = None,
    ) -> tuple[str, str, list[str]]:
        article, _report = await self._apply_editorial_product_links_for_job(job_id, article)
        dual = render_dual_surfaces(
            article,
            youtube_video=youtube_video,
            generated_images=generated_images,
        )
        publishable_html = dual.publishable.html
        editorial_html = dual.editorial.html
        provider = "article-template-renderer"
        image_summary_payload = generated_images or {}
        await self.repositories.artifacts.create_artifact(
            job_id,
            "publishable_html",
            GeneratedContent(content_text=publishable_html, provider=provider),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "article_html_editorial",
            GeneratedContent(content_text=editorial_html, provider=provider),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "rendered_html",
            GeneratedContent(content_text=publishable_html, provider=provider),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "article_html",
            GeneratedContent(content_text=publishable_html, provider=provider),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "renderer_logs",
            GeneratedContent(
                content_json={
                    "publishable_logs": dual.publishable.logs,
                    "editorial_logs": dual.editorial.logs,
                },
                provider=provider,
            ),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "image_rendering_summary",
            GeneratedContent(
                content_json=_image_rendering_summary(image_summary_payload, dual.publishable.logs),
                provider=provider,
            ),
        )
        return publishable_html, editorial_html, list(dual.publishable.logs)

    async def _resolve_publishable_html(self, job_id: str) -> str:
        for artifact_type in ("publishable_html", "article_html", "rendered_html"):
            html = await self._latest_artifact_text(job_id, artifact_type)
            if html and not _html_contains_editorial_verification_blocks(html):
                return html
        structured_article = await self._latest_artifact_json(job_id, "structured_article_json")
        if not structured_article:
            structured_article = await self._latest_artifact_json(job_id, "structured_article")
        if not structured_article:
            return ""
        job = await self.repositories.jobs.get_job(job_id)
        request_input = (job or {}).get("request_input") or {}
        article_model = normalize_article(
            structured_article,
            defaults={
                "title": str(request_input.get("title") or ""),
                "target_keyword": str(request_input.get("target_keyword") or ""),
                "product_name": str(request_input.get("product_name") or ""),
                "product_url": str(request_input.get("product_url") or ""),
            },
        )
        publishable_html, _editorial_html, _ = await self._save_rendered_article_artifacts(
            job_id,
            article=article_model,
            youtube_video=await self._latest_artifact_json(job_id, "youtube_video"),
            generated_images=await self._latest_artifact_json(job_id, "image_generation_result"),
        )
        return publishable_html

    async def _resolve_generation_command(self, command: GenerateArticleCommand) -> GenerateArticleCommand:
        if not command.workspace_id:
            return command
        inventory = await self.repositories.workspace_content_inventory.list_for_workspace(
            command.workspace_id,
            limit=500,
        )
        catalog_urls: list[str] = []
        for row in inventory:
            url = str(row.get("url") or row.get("canonical_url") or "").strip()
            if not url:
                continue
            if str(row.get("content_type") or "").lower() == "product" or product_name_from_url(url):
                catalog_urls.append(url)
        resolved = resolve_product_page_url(
            product_name=command.product_name,
            product_url=command.product_url,
            catalog_urls=catalog_urls,
        )
        if resolved == command.product_url:
            return command
        return replace(command, product_url=resolved)

    async def _catalog_urls_for_workspace(self, workspace_id: str | None) -> list[str]:
        if not workspace_id:
            return []
        inventory = await self.repositories.workspace_content_inventory.list_for_workspace(
            workspace_id,
            limit=500,
        )
        catalog_urls: list[str] = []
        for row in inventory:
            url = str(row.get("url") or row.get("canonical_url") or "").strip()
            if not url:
                continue
            if str(row.get("content_type") or "").lower() == "product" or product_name_from_url(url):
                catalog_urls.append(url)
        return catalog_urls

    async def _apply_editorial_product_links(
        self,
        article: ArticleSchema,
        command: GenerateArticleCommand,
    ) -> tuple[ArticleSchema, LinkReport]:
        catalog_urls = await self._catalog_urls_for_workspace(command.workspace_id)
        related_products = _related_products_from_context(command.opportunity_context)
        url_map = build_article_product_url_map(
            product_name=command.product_name,
            product_url=command.product_url,
            related_products=related_products,
            catalog_urls=catalog_urls,
        )
        updated, report = link_products_in_article(article.model_dump(), url_map)
        defaults = {
            "title": command.title,
            "target_keyword": command.target_keyword,
            "product_name": command.product_name,
            "product_url": command.product_url,
        }
        return normalize_article(updated, defaults=defaults), report

    async def _apply_editorial_product_links_for_job(
        self,
        job_id: str,
        article: ArticleSchema,
    ) -> tuple[ArticleSchema, LinkReport]:
        job = await self.repositories.jobs.get_job(job_id)
        request_input = (job or {}).get("request_input") or {}
        command = GenerateArticleCommand(
            title=str(request_input.get("title") or ""),
            target_keyword=str(request_input.get("target_keyword") or ""),
            product_name=str(request_input.get("product_name") or ""),
            product_url=str(request_input.get("product_url") or ""),
            workspace_id=str((job or {}).get("workspace_id") or request_input.get("workspace_id") or "") or None,
            opportunity_context=request_input.get("opportunity_context")
            if isinstance(request_input.get("opportunity_context"), dict)
            else None,
        )
        if command.product_url and command.workspace_id:
            resolved_url = resolve_product_page_url(
                product_name=command.product_name,
                product_url=command.product_url,
                catalog_urls=await self._catalog_urls_for_workspace(command.workspace_id),
            )
            command = replace(command, product_url=resolved_url)
        return await self._apply_editorial_product_links(article, command)

    async def run_seo_optimization(self, job_id: str, *, respect_manual_seo: bool = False) -> dict[str, Any]:
        job = await self.repositories.jobs.get_job(job_id)
        if job is None:
            raise ValueError("Job not found.")
        structured_article = await self._latest_artifact_json(job_id, "structured_article_json")
        if not structured_article:
            structured_article = await self._latest_artifact_json(job_id, "structured_article")
        if not structured_article:
            raise ValueError("Structured article is not available for SEO optimization.")

        updated_article, seo_updates, report = await self._apply_seo_optimization_to_article(
            job_id,
            structured_article,
            respect_manual_seo=respect_manual_seo,
            job=job,
        )
        request_input = job.get("request_input") or {}
        article_model = normalize_article(
            updated_article,
            defaults={
                "title": str(request_input.get("title") or ""),
                "target_keyword": str(request_input.get("target_keyword") or ""),
                "product_name": str(request_input.get("product_name") or ""),
                "product_url": str(request_input.get("product_url") or ""),
            },
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "structured_article_json",
            GeneratedContent(content_json=updated_article, provider="seo-optimization-pass"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "structured_article",
            GeneratedContent(content_json=updated_article, provider="seo-optimization-pass"),
        )
        await self.repositories.artifacts.create_artifact(
            job_id,
            "seo_optimization_report",
            GeneratedContent(content_json=report.as_dict(), provider="seo-optimization-pass"),
        )
        await self._save_rendered_article_artifacts(
            job_id,
            article=article_model,
            youtube_video=await self._latest_artifact_json(job_id, "youtube_video"),
            generated_images=await self._latest_artifact_json(job_id, "image_generation_result"),
        )
        if seo_updates:
            await self.repositories.jobs.update_job_seo(job_id, **seo_updates)
        refreshed = await self.repositories.jobs.get_job(job_id) or job
        return {
            "job_id": job_id,
            "status": "optimized",
            "optimization_report": report.as_dict(),
            **job_seo_snapshot(refreshed),
        }

    async def _apply_seo_optimization_to_article(
        self,
        job_id: str,
        structured_article: dict[str, Any],
        *,
        respect_manual_seo: bool,
        job: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], OptimizationReport]:
        job = job or await self.repositories.jobs.get_job(job_id) or {}
        workspace_id = str(job.get("workspace_id") or "").strip()
        seo_fields = job_seo_snapshot(job)
        request_input = job.get("request_input") or {}
        if not seo_fields.get("seo_focus_keyword"):
            seo_fields["seo_focus_keyword"] = str(
                structured_article.get("primary_keyword")
                or request_input.get("target_keyword")
                or ""
            ).strip() or None
        if not seo_fields.get("seo_title"):
            seo_fields["seo_title"] = str(structured_article.get("meta_title") or request_input.get("title") or "").strip() or None
        if not seo_fields.get("seo_description"):
            seo_fields["seo_description"] = str(structured_article.get("meta_description") or "").strip() or None

        opportunity = request_input.get("opportunity_context") if isinstance(request_input.get("opportunity_context"), dict) else {}
        related_products = _related_products_from_context(opportunity)
        if not related_products:
            article_related = structured_article.get("related_products")
            if isinstance(article_related, list):
                related_products = [str(item).strip() for item in article_related if str(item).strip()]
        candidates = await self._article_link_candidates(workspace_id, exclude_job_id=job_id)
        updated_article, updated_seo, report = run_seo_optimization_pass(
            structured_article,
            seo_fields,
            article_link_candidates=candidates,
            respect_manual_seo=respect_manual_seo,
            seo_manually_edited=bool(job.get("seo_manually_edited")),
            wordpress_public_url=str(job.get("wordpress_public_url") or ""),
            site_base_url=str(job.get("wordpress_connector_site_url") or ""),
            product_name=str(request_input.get("product_name") or opportunity.get("product_name") or ""),
            related_products=related_products,
        )

        seo_updates: dict[str, Any] = {"seo_optimized_at": utc_now()}
        for field in (
            "seo_title",
            "seo_description",
            "seo_focus_keyword",
            "seo_canonical_url",
            "recommended_slug",
            "suggested_featured_image_alt",
            "suggested_inline_image_alt",
        ):
            value = updated_seo.get(field)
            if value is None:
                continue
            if str(job.get(field) or "") != str(value):
                seo_updates[field] = value
        return updated_article, seo_updates, report

    async def _article_link_candidates(self, workspace_id: str, *, exclude_job_id: str) -> list[ArticleLinkCandidate]:
        if not workspace_id:
            return []
        jobs = await self.repositories.jobs.list_recent(50, workspace_id=workspace_id)
        inventory = await self.repositories.workspace_content_inventory.list_for_workspace(workspace_id, limit=200)
        return build_article_link_candidates(
            jobs,
            current_job_id=exclude_job_id,
            inventory_rows=inventory,
        )

    async def _generation_compliance_context(
        self,
        command: GenerateArticleCommand,
        article: ArticleSchema,
    ) -> dict[str, Any]:
        workspace: dict[str, Any] = {}
        if command.workspace_id:
            row = await self.repositories.autopilot_workspaces.get(command.workspace_id)
            workspace = row if isinstance(row, dict) else {}

        profile, detection = _detect_article_vertical(
            article=article,
            command=command,
            configured_vertical=self.settings.opportunity_vertical,
        )
        ws_settings = workspace.get("settings") if isinstance(workspace.get("settings"), dict) else {}
        ws_compliance = ws_settings.get("compliance") if isinstance(ws_settings.get("compliance"), dict) else {}
        markdown = article_to_markdown(article)
        workspace_name = str(workspace.get("name") or "").strip()
        return {
            "vertical_profile": profile,
            "vertical_detection": detection,
            "vertical_id": profile.id,
            "workspace_name": workspace_name,
            "site_name": workspace_name,
            "publisher_name": default_publisher_name(
                product_name=command.product_name,
                product_url=command.product_url,
                workspace_name=workspace_name,
                site_name=workspace_name,
            ),
            "compliance_rules": build_compliance_rules(
                brand_name=workspace_name or command.product_name,
                vertical_compliance=profile.compliance_profile,
                workspace_compliance=ws_compliance,
            ),
            "required_disclaimer": self.settings.biomedical_ruo_disclaimer,
            "is_biomedical": requires_ruo_disclaimer(
                article.model_dump(),
                markdown,
                vertical_id=profile.id,
                vertical_compliance=profile.compliance_profile,
            ),
        }


def _string_list_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _generated_featured_image(payload: dict[str, Any]) -> dict[str, Any] | None:
    images = payload.get("images") if isinstance(payload.get("images"), list) else []
    for image in images:
        if not _is_renderable_generated_image(image) or image.get("type") != "featured":
            continue
        return {
            "url": image.get("url") or "",
            "local_path": image.get("local_path") or "",
            "alt_text": image.get("alt_text") or "",
            "caption": image.get("caption") or "",
            "source": "ai_image_generation",
        }
    return None


def _first_generated_image(payload: dict[str, Any]) -> dict[str, Any] | None:
    images = payload.get("images") if isinstance(payload.get("images"), list) else []
    for image in images:
        if _is_renderable_generated_image(image):
            return image
    return None


def _html_contains_editorial_verification_blocks(html: str) -> bool:
    lowered = html.lower()
    markers = (
        "research metadata",
        "research insights",
        "research notes to verify",
        "references to verify",
    )
    return any(marker in lowered for marker in markers)


def _detect_article_vertical(
    *,
    article: ArticleSchema,
    command: GenerateArticleCommand,
    configured_vertical: str,
) -> tuple[Any, dict[str, Any]]:
    text_sample = " ".join(
        [
            str(article.title or ""),
            str(article.primary_keyword or ""),
            str(command.product_name or ""),
            str(article.research_context or ""),
            str(article.limitations_and_safety or ""),
            " ".join(str(section.heading or "") for section in article.sections),
        ]
    )
    synthetic_site = {
        "url": command.product_url,
        "domain": "",
        "pages": [
            {
                "url": command.product_url,
                "title": article.title or command.title,
                "meta_description": article.excerpt,
                "headings": [{"level": "h2", "text": section.heading} for section in article.sections if section.heading],
                "commercial_links": [{"text": command.product_name, "url": command.product_url}],
                "text_sample": text_sample,
            }
        ],
    }
    return detect_vertical(
        website=synthetic_site,
        competitors=[],
        override=configured_vertical or "auto",
    )


def _image_rendering_summary(image_generation: dict[str, Any], logs: list[str]) -> dict[str, Any]:
    images = image_generation.get("images") if isinstance(image_generation.get("images"), list) else []
    renderable = [image for image in images if _is_renderable_generated_image(image)]
    return {
        "approved_for_publish": bool(renderable),
        "generated_image_count": len(images),
        "approved_image_count": len(renderable),
        "renderable_image_count": len(renderable),
        "inline_images_renderable": len([image for image in renderable if image.get("type") == "inline" and image.get("url")]),
        "featured_image_renderable": bool(
            next((image for image in renderable if image.get("type") == "featured" and image.get("url")), None)
        ),
        "logs": logs,
        "note": "Generated images render automatically when they pass image safety and have a URL.",
    }


def _renderable_generated_images(image_generation: dict[str, Any]) -> list[dict[str, Any]]:
    images = image_generation.get("images") if isinstance(image_generation.get("images"), list) else []
    return [image for image in images if _is_renderable_generated_image(image)]


def _is_renderable_generated_image(image: Any) -> bool:
    return (
        isinstance(image, dict)
        and image.get("status") == "generated"
        and bool(image.get("url") or image.get("local_path"))
    )


def _clean_publish_tags(value: Any, max_tags: int) -> list[str]:
    seen: set[str] = set()
    cleaned = []
    for item in _string_list_from_value(value):
        tag = " ".join(item.replace("#", "").split()).strip(" ,;")
        if not tag or len(tag) > 60:
            continue
        normalized = tag.lower()
        if normalized in seen:
            continue
        # Avoid obvious exact-match stuffing by keeping one very long keyword phrase at most.
        if len(tag.split()) > 5 and any(len(existing.split()) > 5 for existing in cleaned):
            continue
        seen.add(normalized)
        cleaned.append(tag)
        if len(cleaned) >= max(1, max_tags):
            break
    return cleaned

