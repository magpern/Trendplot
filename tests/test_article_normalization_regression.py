"""Regression tests for article normalization, rendering, and product URL preservation."""

from app.article_schema import normalize_article
from app.catalog.products import resolve_product_page_url
from app.internal_links import InternalLinkResult, InternalLinkService
from app.rendering.article_renderer import render_article
from app.rendering.render_surface import ArticleRenderSurface


def test_object_shaped_research_context_renders_as_markdown() -> None:
    article = normalize_article(
        {
            "title": "Lab handling guide",
            "sections": [{"heading": "Intro", "content_markdown": "Body text."}],
            "research_context": {
                "overview": "Peptide catalog language can be ambiguous.",
                "workflow_relevance": "Naming precision affects receiving and documentation.",
                "evidence_limits": "Confirm IPA meaning from supplier paperwork.",
            },
        },
        defaults={"title": "Lab handling guide", "target_keyword": "lab handling", "product_name": "SKU", "product_url": "https://example.com/product/sku/"},
    )
    assert "**Overview**" in article.research_context
    assert "Peptide catalog language can be ambiguous." in article.research_context
    assert "{" not in article.research_context


def test_stringified_research_context_object_is_normalized() -> None:
    raw = (
        "{'overview': 'Peptide catalog language often combines shorthand.', "
        "'workflow_relevance': 'Naming precision affects receiving.', "
        "'evidence_limits': 'Confirm IPA meaning from supplier paperwork.'}"
    )
    article = normalize_article(
        {"title": "Guide", "sections": [], "research_context": raw},
        defaults={"title": "Guide", "target_keyword": "kw", "product_name": "SKU", "product_url": "https://example.com/"},
    )
    assert article.research_context.startswith("**Overview**")
    assert "Peptide catalog language often combines shorthand." in article.research_context


def test_heading_object_does_not_leak_internal_label() -> None:
    article = normalize_article(
        {
            "title": "CJC-1295 No DAC + IPA overview",
            "sections": [{"heading": "Intro", "content_markdown": "Body text."}],
            "research_context": {
                "heading": "Context for biomedical researchers",
                "content_markdown": (
                    "CJC-1295 No DAC and IPA are discussed in growth-hormone secretagogue literature."
                ),
            },
            "limitations_and_safety": {
                "heading": "Limitations and safety",
                "content_markdown": (
                    "For research use only. Not intended for human consumption, therapeutic, or diagnostic use."
                ),
            },
        },
        defaults={
            "title": "CJC-1295 No DAC + IPA overview",
            "target_keyword": "cjc-1295 no dac ipa",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        },
    )
    assert "**Heading**" not in article.research_context
    assert "**Heading**" not in article.limitations_and_safety
    assert "Context for biomedical researchers" not in article.research_context
    assert "Limitations and safety" not in article.limitations_and_safety
    assert "growth-hormone secretagogue literature" in article.research_context
    rendered = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE)
    assert "**Heading**" not in rendered.html
    assert "Research Context" in rendered.html
    assert "Limitations and Safety Notes" in rendered.html


def test_content_markdown_object_does_not_leak_schema_label() -> None:
    article = normalize_article(
        {
            "title": "BPC-157 research overview",
            "sections": [{"heading": "Intro", "content_markdown": "Body text."}],
            "research_context": {
                "content_markdown": "BPC-157 is discussed in preclinical repair and signaling literature.",
                "evidence_limits": "Human translation remains limited.",
            },
            "limitations_and_safety": {
                "content_markdown": "For research use only. Not intended for human consumption, therapeutic, or diagnostic use.",
                "scope": "This article summarizes literature themes only.",
            },
        },
        defaults={
            "title": "BPC-157 research overview",
            "target_keyword": "bpc-157",
            "product_name": "BPC-157",
            "product_url": "https://example.com/product/bpc-157/",
        },
    )
    assert "Content Markdown" not in article.research_context
    assert "BPC-157 is discussed in preclinical repair and signaling literature." in article.research_context
    assert "Content Markdown" not in article.limitations_and_safety
    rendered = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE)
    assert "Content Markdown" not in rendered.html
    assert "Research Context" in rendered.html


def test_object_shaped_limitations_and_safety_renders_in_html() -> None:
    article = normalize_article(
        {
            "title": "Safety guide",
            "sections": [{"heading": "Intro", "content_markdown": "Body text."}],
            "limitations_and_safety": {
                "disclaimer": "For research use only. Not intended for human consumption, therapeutic, or diagnostic use.",
                "scope": "This article explains labeling context only.",
                "interpretation_limit": "Supplier naming conventions can vary by catalog and batch.",
            },
        },
        defaults={"title": "Safety guide", "target_keyword": "kw", "product_name": "SKU", "product_url": "https://example.com/"},
    )
    rendered = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE)
    assert "For research use only." in rendered.html
    assert "Limitations and Safety Notes" in rendered.html
    assert "{'disclaimer'" not in rendered.html


def test_internal_links_upgrade_homepage_to_product_page() -> None:
    product_page = "https://www.example.com/product/cjc-1295-no-dac-ipa/"
    article = normalize_article(
        {
            "title": "CJC guide",
            "sections": [{"heading": "Intro", "content_markdown": "See the product page for specs."}],
            "internal_links": [
                {
                    "anchor_text": "CJC-1295 No DAC + IPA product page",
                    "url": "https://www.example.com/",
                    "reason": "",
                }
            ],
        },
        defaults={
            "title": "CJC guide",
            "target_keyword": "cjc handling",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": product_page,
        },
    )
    assert article.internal_links[0].url == product_page

    rendered = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE)
    assert product_page in rendered.html
    assert 'href="https://www.example.com/"' not in rendered.html


def test_product_cta_url_preserved_in_rendered_html() -> None:
    product_page = "https://www.example.com/product/cjc-1295-no-dac-ipa/"
    article = normalize_article(
        {
            "title": "CJC guide",
            "sections": [{"heading": "Intro", "content_markdown": "Workflow overview."}],
            "internal_links": [
                {
                    "anchor_text": "CJC-1295 No DAC + IPA product page",
                    "url": product_page,
                    "reason": "Primary product page.",
                }
            ],
        },
        defaults={
            "title": "CJC guide",
            "target_keyword": "cjc handling",
            "product_name": "CJC-1295 No DAC + IPA",
            "product_url": product_page,
        },
    )
    rendered = render_article(article, surface=ArticleRenderSurface.PUBLISHABLE)
    assert 'href="https://www.example.com/product/cjc-1295-no-dac-ipa/"' in rendered.html
    assert "Researchers interested in CJC-1295 No DAC + IPA materials" in rendered.html
    assert "Product reference" not in rendered.html


def test_resolve_product_page_url_matches_inventory_catalog() -> None:
    resolved = resolve_product_page_url(
        product_name="CJC-1295 No DAC + IPA",
        product_url="https://www.example.com/",
        catalog_urls=[
            "https://www.example.com/",
            "https://www.example.com/product/cjc-1295-no-dac-ipa/",
        ],
    )
    assert resolved == "https://www.example.com/product/cjc-1295-no-dac-ipa/"


def test_internal_link_service_upgrades_stale_homepage_markdown_links() -> None:
    service = InternalLinkService()
    product_page = "https://www.example.com/product/cjc-1295-no-dac-ipa/"
    markdown = "Review the [CJC-1295 No DAC + IPA product page](https://www.example.com/) for specs."
    result = service._upgrade_product_link_targets(
        InternalLinkResult(markdown=markdown, links=[]),
        product_url=product_page,
        suggested_links=[
            {
                "anchor_text": "CJC-1295 No DAC + IPA product page",
                "url": "https://www.example.com/",
            }
        ],
    )
    assert f"]({product_page})" in result.markdown
    assert "https://www.example.com/)" not in result.markdown
