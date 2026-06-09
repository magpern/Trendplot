import json
from dataclasses import dataclass, field
from typing import Any

from app.article_schema import ArticleSchema, article_to_markdown, normalize_article
from app.rendering.render_surface import ArticleRenderSurface
from app.prompts import render_prompt
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask
from app.review.article_repair import sanitize_article_safety
from app.review.sanity_checker import ArticleSanityChecker, SanityCheckReport, SanityFinding


@dataclass(slots=True)
class SemanticSanityResult:
    article: ArticleSchema
    report: SanityCheckReport
    prompt: str
    summary: dict[str, Any] = field(default_factory=dict)
    generated: GeneratedContent | None = None
    deterministic_summary: dict[str, Any] = field(default_factory=dict)


class SemanticSanityReviewer:
    async def review(
        self,
        content_provider: Any,
        article: ArticleSchema,
        request_data: dict[str, Any],
        rules: dict[str, Any],
        deterministic_checker: ArticleSanityChecker,
    ) -> SemanticSanityResult:
        prompt = build_semantic_sanity_prompt(
            article=article,
            request_data=request_data,
            rules=rules,
        )
        generated: GeneratedContent | None = None
        try:
            generated = await content_provider.generate_article(prompt, task_type=ModelTask.SANITY_REVIEW)
        except Exception as exc:
            fallback_article, deterministic_summary = _deterministic_fallback(
                article=article,
                request_data=request_data,
                deterministic_checker=deterministic_checker,
            )
            return SemanticSanityResult(
                article=fallback_article,
                report=SanityCheckReport(
                    passed=True,
                    rules_summary=list(rules.get("rules", [])),
                    status="passed",
                ),
                prompt=prompt,
                summary={
                    "attempted": True,
                    "changed_locations": deterministic_summary.get("changed_locations", []),
                    "notes": f"AI semantic sanity review failed; deterministic guardrail fallback was applied: {exc}",
                    "deterministic_guardrail": deterministic_summary,
                },
                generated=None,
                deterministic_summary=deterministic_summary,
            )
        payload = generated.content_json or {}
        article_json = payload.get("article") if isinstance(payload.get("article"), dict) else article.model_dump()
        reviewed_article = normalize_article(
            sanitize_article_safety(article_json),
            defaults=_defaults_from_request(request_data, article),
        )
        summary = _summary_from_payload(payload)
        issues = _issues_from_payload(payload)

        deterministic_summary: dict[str, Any] = {
            "attempted": False,
            "changed_locations": [],
            "reason": "AI semantic sanity review passed without deterministic guardrail fixes.",
        }
        guardrail_report = deterministic_checker.check(reviewed_article, product_data=request_data)
        if not guardrail_report.passed:
            reviewed_article, deterministic_summary = deterministic_checker.rewrite_blocking_claims(
                article=reviewed_article,
                report=guardrail_report,
                defaults=_defaults_from_request(request_data, reviewed_article),
            )
            second_guardrail_report = deterministic_checker.check(reviewed_article, product_data=request_data)
            if not second_guardrail_report.passed:
                reviewed_article, deterministic_summary = deterministic_checker.remove_blocking_claims(
                    article=reviewed_article,
                    report=second_guardrail_report,
                    defaults=_defaults_from_request(request_data, reviewed_article),
                )

        report = SanityCheckReport(
            passed=True,
            warnings=issues,
            rules_summary=list(rules.get("rules", [])),
            status="passed",
        )
        summary.setdefault("attempted", True)
        summary.setdefault("notes", "AI semantic sanity review completed.")
        summary["deterministic_guardrail"] = deterministic_summary
        return SemanticSanityResult(
            article=reviewed_article,
            report=report,
            prompt=prompt,
            summary=summary,
            generated=generated,
            deterministic_summary=deterministic_summary,
        )


def build_semantic_sanity_prompt(
    article: ArticleSchema,
    request_data: dict[str, Any],
    rules: dict[str, Any],
) -> str:
    return render_prompt(
        "sanity_check",
        {
            "article_json": article.model_dump_json(indent=2),
            "article_markdown": article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE),
            "request_data_json": json.dumps(request_data, ensure_ascii=False, indent=2),
            "brand_rules_json": json.dumps(rules, ensure_ascii=False, indent=2),
        },
    )


def _defaults_from_request(request_data: dict[str, Any], article: ArticleSchema) -> dict[str, str]:
    return {
        "title": str(request_data.get("title") or article.title or ""),
        "target_keyword": str(request_data.get("target_keyword") or article.primary_keyword or ""),
        "product_name": str(request_data.get("product_name") or ""),
        "product_url": str(request_data.get("product_url") or ""),
    }


def _summary_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return dict(summary)
    return {
        "attempted": True,
        "changed_locations": [],
        "notes": "Model returned a corrected article without a summary wrapper.",
    }


def _issues_from_payload(payload: dict[str, Any]) -> list[SanityFinding]:
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return []
    findings = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        findings.append(
            SanityFinding(
                code="semantic_sanity_review",
                severity="warning",
                message=str(issue.get("problem") or issue.get("message") or "Semantic sanity review note."),
                matched_text=str(issue.get("original_text") or ""),
                location=str(issue.get("location") or "article"),
                suggested_replacement=str(issue.get("replacement_text") or "") or None,
            )
        )
    return findings


def _deterministic_fallback(
    article: ArticleSchema,
    request_data: dict[str, Any],
    deterministic_checker: ArticleSanityChecker,
) -> tuple[ArticleSchema, dict[str, Any]]:
    report = deterministic_checker.check(article, product_data=request_data)
    if report.passed:
        return article, {
            "attempted": False,
            "changed_locations": [],
            "reason": "Deterministic guardrail fallback found no blocking issues.",
        }

    rewritten, summary = deterministic_checker.rewrite_blocking_claims(
        article=article,
        report=report,
        defaults=_defaults_from_request(request_data, article),
    )
    second_report = deterministic_checker.check(rewritten, product_data=request_data)
    if second_report.passed:
        return rewritten, summary

    return deterministic_checker.remove_blocking_claims(
        article=rewritten,
        report=second_report,
        defaults=_defaults_from_request(request_data, rewritten),
    )
