from __future__ import annotations

from app.catalog.products import is_product_page_url
from app.internal_links.product_linker import link_products_in_article
from app.seo.article_linker import ArticleLinkCandidate, build_article_link_candidates, link_articles_in_structured
from app.seo.optimization_pass import run_seo_optimization_pass
from app.seo.text_utils import (
    collect_body_markdown,
    count_keyword_occurrences,
    recommend_canonical_url,
    recommend_slug,
    split_long_paragraphs,
)


def _sample_article(*, with_keyword_in_intro: bool = False) -> dict:
    intro = (
        "TB-500 and BPC-157 are often discussed together in laboratory research."
        if with_keyword_in_intro
        else "Peptide research often compares related compounds in laboratory settings."
    )
    return {
        "title": "TB-500 vs BPC-157",
        "primary_keyword": "TB-500 vs BPC-157",
        "sections": [
            {
                "heading": "Background",
                "content_markdown": intro,
            },
            {
                "heading": "Mechanism differences",
                "content_markdown": (
                    "Researchers compare signaling pathways and experimental use cases. "
                    "These discussions remain limited to research use only (RUO) contexts."
                ),
            },
        ],
        "faq": [{"question": "Is this for human use?", "answer": "No. Research use only."}],
    }


def _run(article: dict, seo: dict | None = None, **kwargs):
    return run_seo_optimization_pass(
        article,
        seo or {"seo_focus_keyword": "TB-500 vs BPC-157"},
        article_link_candidates=kwargs.get("article_link_candidates", []),
        respect_manual_seo=kwargs.get("respect_manual_seo", True),
        seo_manually_edited=kwargs.get("seo_manually_edited", False),
        wordpress_public_url=str(kwargs.get("wordpress_public_url") or ""),
        site_base_url=str(kwargs.get("site_base_url") or ""),
    )


def test_focus_keyword_inserted_into_seo_title() -> None:
    article, seo, report = _run(_sample_article(), {"seo_title": "TB-500 vs BPC-157", "seo_focus_keyword": "TB-500 vs BPC-157"})
    assert "TB-500 vs BPC-157" in seo["seo_title"]
    assert report.seo_title_improved or "Key" in seo["seo_title"]


def test_focus_keyword_inserted_into_meta_description() -> None:
    article, seo, report = _run(
        _sample_article(),
        {"seo_description": "A research overview for laboratory contexts.", "seo_focus_keyword": "TB-500 vs BPC-157"},
    )
    assert "TB-500 vs BPC-157" in seo["seo_description"]
    assert report.meta_description_improved


def test_short_slug_generated() -> None:
    slug = recommend_slug("TB-500 vs BPC-157", "TB-500 vs BPC-157")
    assert slug
    assert len(slug) <= 60
    assert "tb-500" in slug
    assert "bpc-157" in slug


def test_long_canonical_url_shortened_to_recommended_slug() -> None:
    slug = recommend_slug("TB-500 vs BPC-157", "TB-500 vs BPC-157")
    long_canonical = (
        "https://staging.example.com/tb-500-vs-bpc-157-relationship-article-on-why-these-peptides-appear-toge/"
    )
    shortened = recommend_canonical_url(
        slug,
        existing_canonical=long_canonical,
        site_base_url="https://staging.example.com",
    )
    assert shortened == f"https://staging.example.com/{slug}/"

    article, seo, report = _run(
        _sample_article(),
        {
            "seo_focus_keyword": "TB-500 vs BPC-157",
            "seo_canonical_url": long_canonical,
        },
        respect_manual_seo=False,
        wordpress_public_url="https://staging.example.com/tb-500-vs-bpc-157-relationship-article-on-why-these-peptides-appear-toge/",
    )
    assert seo["seo_canonical_url"] == f"https://staging.example.com/{slug}/"
    assert report.canonical_url_improved


def test_focus_keyword_added_to_one_heading() -> None:
    article, _, report = _run(_sample_article())
    headings = [section["heading"] for section in article["sections"]]
    assert any("TB-500 vs BPC-157" in heading for heading in headings)
    assert report.focus_keyword_heading


def test_keyword_occurrence_target_respected() -> None:
    long_article = _sample_article()
    long_article["sections"].append(
        {
            "heading": "Extended discussion",
            "content_markdown": " ".join(["Laboratory peptide research context."] * 260),
        }
    )
    article, _, report = _run(long_article)
    body = collect_body_markdown(article)
    count = count_keyword_occurrences(body, "TB-500 vs BPC-157")
    assert report.keyword_target_min >= 3
    assert count >= report.keyword_target_min
    assert count <= max(report.keyword_target_max, report.keyword_target_min)


def test_no_keyword_stuffing() -> None:
    stuffed = _sample_article()
    stuffed["sections"][0]["content_markdown"] = "TB-500 vs BPC-157 " * 20
    before = count_keyword_occurrences(collect_body_markdown(stuffed), "TB-500 vs BPC-157")
    article, _, report = _run(stuffed)
    after = count_keyword_occurrences(collect_body_markdown(article), "TB-500 vs BPC-157")
    assert after <= before
    assert "Focus keyword density adjusted." not in report.changes


def test_article_to_article_internal_link_added() -> None:
    article = _sample_article()
    article["sections"][1]["content_markdown"] = (
        "Researchers also review BPC-157 mechanisms in separate laboratory studies. "
        "These discussions remain limited to research use only (RUO) contexts."
    )
    candidates = [
        ArticleLinkCandidate(
            job_id="other-job",
            title="BPC-157 Overview",
            url="https://test.example.com/bpc-157-overview/",
            focus_keyword="BPC-157",
        )
    ]
    updated, report = link_articles_in_structured(
        article,
        candidates,
        focus_keyword="TB-500 vs BPC-157",
        article_title="TB-500 vs BPC-157",
    )
    body = collect_body_markdown(updated)
    assert "https://test.example.com/bpc-157-overview/" in body
    assert report.total_links == 1


def test_product_only_links_do_not_count_as_article_internal_links() -> None:
    article = _sample_article()
    article["sections"][1]["content_markdown"] = (
        "Researchers compare BPC-157 signaling in laboratory models. "
        "These discussions remain limited to research use only (RUO) contexts."
    )
    product_url = "https://test.example.com/product/bpc-157/"
    assert is_product_page_url(product_url)
    updated, product_report = link_products_in_article(
        article,
        {"BPC-157": product_url},
    )
    candidates = build_article_link_candidates(
        [
            {
                "id": "product-job",
                "wordpress_public_url": product_url,
                "request_input": {"title": "BPC-157 Product"},
                "seo_focus_keyword": "BPC-157",
            }
        ],
        current_job_id="current",
    )
    assert candidates == []
    article_updated, article_report = link_articles_in_structured(
        updated,
        candidates,
        focus_keyword="TB-500 vs BPC-157",
        article_title="TB-500 vs BPC-157",
    )
    assert product_report.total_links >= 1
    assert article_report.total_links == 0


def test_existing_markdown_links_are_not_double_wrapped() -> None:
    article = _sample_article()
    url = "https://test.example.com/bpc-157-overview/"
    article["sections"][1]["content_markdown"] = f"Read the [BPC-157 overview]({url}) for context."
    updated, report = link_articles_in_structured(
        article,
        [
            ArticleLinkCandidate(
                job_id="other-job",
                title="BPC-157 Overview",
                url=url,
                focus_keyword="BPC-157",
            )
        ],
        focus_keyword="TB-500 vs BPC-157",
        article_title="TB-500 vs BPC-157",
    )
    body = collect_body_markdown(updated)
    assert body.count(f"]({url})") == 1
    assert report.total_links == 0


def test_self_link_is_skipped() -> None:
    article = _sample_article()
    self_url = "https://test.example.com/tb-500-vs-bpc-157/"
    candidates = build_article_link_candidates(
        [
            {
                "id": "current",
                "wordpress_public_url": self_url,
                "request_input": {"title": "TB-500 vs BPC-157"},
                "seo_focus_keyword": "TB-500 vs BPC-157",
            }
        ],
        current_job_id="current",
    )
    assert candidates == []


def test_long_paragraph_split() -> None:
    long_text = " ".join(["This sentence explains laboratory research context."] * 20)
    updated, splits = split_long_paragraphs(long_text, max_words=80)
    assert splits >= 1
    assert "\n\n" in updated


def test_manual_seo_edits_are_not_overwritten_unless_explicit_optimization_is_run() -> None:
    manual_title = "Custom SEO title for TB-500 vs BPC-157"
    article, seo, _ = _run(
        _sample_article(),
        {"seo_title": manual_title, "seo_description": "Custom description.", "seo_focus_keyword": "TB-500 vs BPC-157"},
        respect_manual_seo=True,
        seo_manually_edited=True,
    )
    assert seo["seo_title"] == manual_title

    article, seo, report = _run(
        _sample_article(),
        {"seo_title": manual_title, "seo_description": "Custom description.", "seo_focus_keyword": "TB-500 vs BPC-157"},
        respect_manual_seo=False,
        seo_manually_edited=True,
    )
    assert seo["seo_title"] != manual_title or report.seo_title_improved
