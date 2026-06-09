from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.article_schema import (
    ArticleSchema,
    ArticleSection,
    CalloutBox,
    CautionBox,
    FAQItem,
    InternalLinkSuggestion,
    ReferenceToVerify,
    ResearchInsight,
    ResearchMetadataPanel,
    StudyCard,
    article_to_markdown,
    normalize_article,
)
from app.quality_checks import run_article_quality_checks
from app.rendering.article_renderer import render_article
from app.rendering.render_surface import ArticleRenderSurface
from app.services.jobs import JobService, _html_contains_editorial_verification_blocks


def _sample_article() -> ArticleSchema:
    return ArticleSchema(
        title="Best Practices for Storing Bacteriostatic Water",
        excerpt="Storage overview for laboratory settings.",
        research_context="Researchers often discuss labeled storage guidance.",
        limitations_and_safety="For research use only. Not intended for human consumption, therapeutic, or diagnostic use.",
        key_takeaways=["Verify supplier documentation before use."],
        sections=[
            ArticleSection(
                heading="Storage fundamentals",
                content_markdown=" ".join(["word"] * 200),
            )
        ],
        faq=[FAQItem(question="Why document storage?", answer="Documentation supports traceability.")],
        internal_links=[
            InternalLinkSuggestion(
                anchor_text="Bacteriostatic Water",
                url="https://shop.example/product/bacteriostatic-water/",
                reason="Primary product",
            )
        ],
        callout_boxes=[CalloutBox(title="Daily checklist", message="Label opened vials with date and initials.")],
        caution_boxes=[CautionBox(title="Handling", message="Follow institutional SOPs.")],
        references_to_verify=[
            ReferenceToVerify(title="USP chapter", search_query="bacteriostatic water USP", reason="Verify label claims")
        ],
        study_cards=[
            StudyCard(
                title="Evidence gap: opened-vial stability",
                observed_finding="Handling varies by workflow.",
                verification_needed="Check supplier documentation.",
            )
        ],
        research_insights=[
            ResearchInsight(title="Practice note", insight="Documentation gaps drive most issues.", limitation="Local SOPs vary.")
        ],
        research_metadata_panel=ResearchMetadataPanel(
            research_status="reviewed",
            confidence_notes="Editorial confidence is moderate.",
        ),
    )


_PUBLISHABLE_FORBIDDEN = (
    "Research Metadata",
    "Research Insights",
    "Research Notes To Verify",
    "References to verify",
    "Evidence gap",
)


def test_publishable_html_excludes_verification_blocks() -> None:
    article = _sample_article()
    html = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE).html
    for phrase in _PUBLISHABLE_FORBIDDEN:
        assert phrase not in html


def test_editorial_full_html_includes_verification_blocks() -> None:
    article = _sample_article()
    html = render_article(article, surface=ArticleRenderSurface.EDITORIAL_FULL).html
    assert "Research Metadata" in html
    assert "Research Insights" in html
    assert "Research Notes To Verify" in html
    assert "References to verify" in html
    assert "Evidence gap" in html


def test_publishable_markdown_omits_verification_sections() -> None:
    article = _sample_article()
    md = article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE)
    assert "Research Notes To Verify" not in md
    assert "References to verify" not in md
    assert "Limitations and Safety Notes" in md


def test_publishable_keeps_compliance_and_faq_and_cta() -> None:
    article = _sample_article()
    html = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE).html
    assert "Limitations and Safety Notes" in html
    assert "FAQ" in html
    assert "Researchers interested in Bacteriostatic Water materials" in html
    assert "Product reference" not in html
    assert "research use only" in html.lower()


def test_quality_checks_flag_verification_in_publishable_html() -> None:
    article = _sample_article()
    editorial_html = render_article(article, surface=ArticleRenderSurface.EDITORIAL_FULL).html
    publishable_md = article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE)
    result = run_article_quality_checks(
        article=article.model_dump(),
        markdown=publishable_md,
        product_url="https://shop.example/product/bacteriostatic-water/",
        youtube_video=None,
        rendered_html=editorial_html,
        publishable_html=editorial_html,
        min_word_count=50,
        required_disclaimer="For research use only. Not intended for human consumption, therapeutic, or diagnostic use.",
    )
    assert not result.passed
    assert any("Publishable HTML must not contain" in error for error in result.errors)


def test_canonical_json_preserves_verification_artifacts() -> None:
    article = _sample_article()
    normalized = normalize_article(article.model_dump(), defaults={})
    payload = normalized.model_dump()
    assert payload["references_to_verify"]
    assert payload["study_cards"]
    assert payload["editorial_artifacts"] is not None
    assert payload["editorial_artifacts"]["study_cards"]


def test_html_contains_editorial_verification_blocks_detector() -> None:
    editorial = render_article(_sample_article(), surface=ArticleRenderSurface.EDITORIAL_FULL).html
    publishable = render_article(_sample_article(), surface=ArticleRenderSurface.PUBLISHABLE).html
    assert _html_contains_editorial_verification_blocks(editorial)
    assert not _html_contains_editorial_verification_blocks(publishable)


def test_resolve_publishable_html_rerenders_legacy_editorial_html() -> None:
    article = _sample_article()
    legacy_html = render_article(article, surface=ArticleRenderSurface.EDITORIAL_FULL).html
    service = JobService(
        repositories=MagicMock(),
        registry=MagicMock(),
        settings=MagicMock(target_min_word_count=1800, biomedical_ruo_disclaimer="RUO"),
    )
    service._latest_artifact_text = AsyncMock(side_effect=lambda _job_id, artifact_type: legacy_html if artifact_type == "article_html" else "")
    service._latest_artifact_json = AsyncMock(
        side_effect=lambda _job_id, artifact_type: (
            article.model_dump()
            if artifact_type in {"structured_article_json", "structured_article", "youtube_video", "image_generation_result"}
            else None
        )
    )
    service.repositories.jobs.get_job = AsyncMock(return_value={"request_input": {}})
    service._save_rendered_article_artifacts = AsyncMock(
        return_value=(
            render_article(article, surface=ArticleRenderSurface.PUBLISHABLE).html,
            legacy_html,
            [],
        )
    )

    html = asyncio.run(service._resolve_publishable_html("job-1"))
    assert html
    assert not _html_contains_editorial_verification_blocks(html)
    service._save_rendered_article_artifacts.assert_awaited_once()


def test_publish_job_uses_publishable_html() -> None:
    article = _sample_article()
    publishable_html = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE).html
    service = JobService(
        repositories=MagicMock(),
        registry=MagicMock(),
        settings=MagicMock(
            target_min_word_count=1800,
            biomedical_ruo_disclaimer="RUO",
            allow_live_publish=True,
            wordpress_default_template="",
        ),
    )
    service._latest_artifact_json = AsyncMock(
        side_effect=lambda _job_id, artifact_type: {"passed": True} if "quality" in artifact_type or "sanity" in artifact_type else article.model_dump()
    )
    service._resolve_publishable_html = AsyncMock(return_value=publishable_html)
    service._mark_progress = AsyncMock()
    service.repositories.jobs.get_job = AsyncMock(return_value={"request_input": {"title": article.title}})
    service.repositories.jobs.mark_status = AsyncMock()
    service.repositories.logs.add_log = AsyncMock()
    service.repositories.artifacts.create_artifact = AsyncMock()

    with patch.object(service, "_publish_to_wordpress", AsyncMock(return_value=MagicMock(content_json={"id": 1}))) as publish_mock:
        asyncio.run(service.publish_existing_job(job_id="job-1", status="draft", confirm_live_publish=False))
        publish_mock.assert_awaited_once()
        assert publish_mock.await_args.kwargs["status"] == "draft"
