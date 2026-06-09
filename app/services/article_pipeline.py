"""Simplified article generation pipeline helpers."""

from __future__ import annotations

from typing import Any

from app.article_schema import ArticleSchema
from app.config import Settings
from app.review.editorial_rewriter import EditorialRewriteResult
from app.review.narrative_editor import NarrativeEditorResult
from app.review.sanity_checker import ArticleSanityChecker, SanityCheckReport
from app.review.section_expander import SectionExpansionResult


def effective_max_repair_passes(settings: Settings) -> int:
    if settings.simplified_article_pipeline:
        return min(max(0, settings.max_repair_passes), 1)
    return max(0, settings.max_repair_passes)


def should_run_section_expansion(settings: Settings, *, publishable_word_count: int) -> bool:
    if settings.simplified_article_pipeline:
        return settings.enable_section_expansion and publishable_word_count < settings.target_min_word_count
    return True


def should_run_humanization(settings: Settings) -> bool:
    if not settings.simplified_article_pipeline:
        return True
    return settings.enable_article_humanization


def should_run_narrative_editor(settings: Settings) -> bool:
    if not settings.simplified_article_pipeline:
        return True
    return settings.enable_narrative_editor


def should_run_semantic_sanity(settings: Settings) -> bool:
    if not settings.simplified_article_pipeline:
        return True
    return settings.enable_semantic_sanity_review


def should_run_youtube_ai_evaluation(settings: Settings) -> bool:
    if not settings.simplified_article_pipeline:
        return True
    return settings.enable_youtube_ai_evaluation


def run_deterministic_sanity_review(
    *,
    article: ArticleSchema,
    checker: ArticleSanityChecker,
    request_data: dict[str, Any],
    defaults: dict[str, str],
) -> tuple[ArticleSchema, SanityCheckReport, dict[str, Any]]:
    """Validator-first sanity: deterministic guardrails only unless semantic is enabled elsewhere."""
    reviewed = article.model_copy(deep=True)
    report = checker.check(reviewed, product_data=request_data)
    summary: dict[str, Any] = {
        "attempted": True,
        "mode": "deterministic",
        "changed_locations": [],
        "notes": "Deterministic sanity guardrails only.",
    }
    if report.passed:
        return reviewed, report, summary

    reviewed, guardrail_summary = checker.rewrite_blocking_claims(
        article=reviewed,
        report=report,
        defaults=defaults,
    )
    summary["deterministic_guardrail"] = guardrail_summary
    summary["changed_locations"] = list(guardrail_summary.get("changed_locations") or [])

    report = checker.check(reviewed, product_data=request_data)
    if report.passed:
        return reviewed, report, summary

    reviewed, removal_summary = checker.remove_blocking_claims(
        article=reviewed,
        report=report,
        defaults=defaults,
    )
    summary["deterministic_removal"] = removal_summary
    report = checker.check(reviewed, product_data=request_data)
    return reviewed, report, summary


def skipped_stage_summary(stage: str, *, reason: str) -> dict[str, Any]:
    return {
        "attempted": False,
        "skipped": True,
        "stage": stage,
        "reason": reason,
    }


def skipped_section_expansion_result(
    article: ArticleSchema,
    *,
    reason: str,
    word_count: int,
) -> SectionExpansionResult:
    summary = {
        **skipped_stage_summary("section_expansion", reason=reason),
        "word_count_before": word_count,
        "word_count_after": word_count,
        "pass_count": 0,
        "expanded_sections": [],
    }
    return SectionExpansionResult(article=article, summary=summary, prompt_records=[])


def skipped_editorial_rewrite_result(article: ArticleSchema, *, reason: str) -> EditorialRewriteResult:
    summary = skipped_stage_summary("humanization", reason=reason)
    return EditorialRewriteResult(
        article=article,
        prompt="",
        summary=summary,
        ai_pattern_report={"skipped": True, "reason": reason},
        rewritten_sections=[],
        reverted_sections=[],
        rewrite_attempts=[],
        humanization_quality_report={"skipped": True},
    )


def skipped_narrative_editor_result(article: ArticleSchema, *, reason: str) -> NarrativeEditorResult:
    return NarrativeEditorResult(
        article=article,
        pattern_report={"skipped": True, "reason": reason},
        summary=skipped_stage_summary("narrative_editor", reason=reason),
    )
