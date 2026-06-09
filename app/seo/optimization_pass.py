from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from app.seo.article_linker import ArticleLinkCandidate, ArticleLinkReport, link_articles_in_structured
from app.seo.focus_keywords import (
    normalize_seo_focus_keywords,
    parse_focus_keywords,
    primary_focus_keyword,
    secondary_focus_keywords,
)
from app.seo.text_utils import (
    collect_body_markdown,
    count_keyword_occurrences,
    improve_meta_description,
    improve_seo_title,
    insert_keyword_in_text,
    keyword_in_text,
    normalize_keyword,
    recommend_canonical_url,
    recommend_slug,
    split_long_paragraphs,
    suggest_image_alts,
    target_keyword_range,
    word_count,
)


@dataclass(slots=True)
class OptimizationReport:
    changes: list[str] = field(default_factory=list)
    focus_keyword_intro: bool = False
    focus_keyword_heading: bool = False
    seo_title_improved: bool = False
    meta_description_improved: bool = False
    canonical_url_improved: bool = False
    slug_recommended: str | None = None
    canonical_url_recommended: str | None = None
    internal_links_added: int = 0
    paragraphs_split: int = 0
    image_alt_suggestions: bool = False
    keyword_occurrences: int = 0
    keyword_target_min: int = 0
    keyword_target_max: int = 0
    focus_keywords: str | None = None
    secondary_keyword_added: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "changes": list(self.changes),
            "focus_keyword_intro": self.focus_keyword_intro,
            "focus_keyword_heading": self.focus_keyword_heading,
            "seo_title_improved": self.seo_title_improved,
            "meta_description_improved": self.meta_description_improved,
            "canonical_url_improved": self.canonical_url_improved,
            "slug_recommended": self.slug_recommended,
            "canonical_url_recommended": self.canonical_url_recommended,
            "internal_links_added": self.internal_links_added,
            "paragraphs_split": self.paragraphs_split,
            "image_alt_suggestions": self.image_alt_suggestions,
            "keyword_occurrences": self.keyword_occurrences,
            "keyword_target_min": self.keyword_target_min,
            "keyword_target_max": self.keyword_target_max,
            "focus_keywords": self.focus_keywords,
            "secondary_keyword_added": self.secondary_keyword_added,
        }


def run_seo_optimization_pass(
    article_json: dict[str, Any],
    seo_fields: dict[str, Any],
    *,
    article_link_candidates: list[ArticleLinkCandidate] | None = None,
    respect_manual_seo: bool = True,
    seo_manually_edited: bool = False,
    wordpress_public_url: str = "",
    site_base_url: str = "",
    product_name: str = "",
    related_products: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], OptimizationReport]:
    article = copy.deepcopy(article_json or {})
    seo = copy.deepcopy(seo_fields or {})
    report = OptimizationReport()

    primary_fallback = _resolve_primary_fallback(article, seo)
    normalized_focus = normalize_seo_focus_keywords(
        str(seo.get("seo_focus_keyword") or primary_fallback),
        primary_fallback=primary_fallback,
        product_name=product_name,
        related_products=related_products,
    )
    if not normalized_focus:
        report.changes.append("Skipped: focus keyword is missing.")
        return article, seo, report

    primary_keyword = primary_focus_keyword(normalized_focus)
    secondary_keywords = secondary_focus_keywords(normalized_focus)
    report.focus_keywords = normalized_focus
    article_title = str(article.get("title") or seo.get("seo_title") or "").strip()

    seo_allowed = not (respect_manual_seo and seo_manually_edited)
    if seo_allowed:
        _optimize_seo_fields(seo, article, primary_keyword, article_title, report)
    else:
        report.changes.append("Preserved manually edited SEO fields.")

    slug = recommend_slug(primary_keyword, article_title)
    if slug:
        seo["recommended_slug"] = slug
        article["recommended_slug"] = slug
        report.slug_recommended = slug
        report.changes.append(f"Recommended slug: {slug}")

    if slug and seo_allowed:
        canonical = recommend_canonical_url(
            slug,
            existing_canonical=str(seo.get("seo_canonical_url") or ""),
            wordpress_public_url=wordpress_public_url,
            site_base_url=site_base_url,
        )
        if canonical:
            seo["seo_canonical_url"] = canonical
            report.canonical_url_recommended = canonical
            report.canonical_url_improved = True
            report.changes.append("Canonical URL shortened to match recommended slug.")

    body_before = collect_body_markdown(article)
    body_words = word_count(body_before)
    min_target, max_target = target_keyword_range(body_words)
    report.keyword_target_min = min_target
    report.keyword_target_max = max_target
    current_count = count_keyword_occurrences(body_before, primary_keyword)

    if current_count < max_target:
        report.focus_keyword_intro = _ensure_keyword_in_intro(article, primary_keyword, report)
        current_count = count_keyword_occurrences(collect_body_markdown(article), primary_keyword)
    if current_count < max_target:
        report.focus_keyword_heading = _ensure_keyword_in_heading(article, primary_keyword, report)
        current_count = count_keyword_occurrences(collect_body_markdown(article), primary_keyword)
    if current_count < min_target:
        _ensure_keyword_density(article, primary_keyword, min_target, max_target, report)

    for secondary in secondary_keywords:
        if _ensure_secondary_keyword_light(article, secondary, primary_keyword, report):
            report.secondary_keyword_added = True
            break

    body_after = collect_body_markdown(article)
    report.keyword_occurrences = count_keyword_occurrences(body_after, primary_keyword)

    linked_article, link_report = link_articles_in_structured(
        article,
        article_link_candidates or [],
        focus_keyword=primary_keyword,
        article_title=article_title,
    )
    article = linked_article
    report.internal_links_added = link_report.total_links
    if link_report.total_links:
        report.changes.append(f"Added {link_report.total_links} internal article link(s).")
        _merge_internal_links(article, link_report)

    split_total = _split_long_paragraphs_in_article(article)
    report.paragraphs_split = split_total
    if split_total:
        report.changes.append(f"Split {split_total} long paragraph(s).")

    alt_suggestions = suggest_image_alts(primary_keyword, article_title)
    seo.update(alt_suggestions)
    article.update(alt_suggestions)
    report.image_alt_suggestions = True
    report.changes.append("Created image alt suggestions.")

    if seo_allowed:
        seo["seo_focus_keyword"] = normalized_focus

    return article, seo, report


def _resolve_primary_fallback(article: dict[str, Any], seo: dict[str, Any]) -> str:
    for value in (
        primary_focus_keyword(str(seo.get("seo_focus_keyword") or "")),
        article.get("primary_keyword"),
        article.get("target_keyword"),
        article.get("focus_keyword"),
    ):
        text = normalize_keyword(str(value or ""))
        if text:
            return text
    return ""


def _ensure_secondary_keyword_light(
    article: dict[str, Any],
    secondary: str,
    primary: str,
    report: OptimizationReport,
) -> bool:
    secondary = normalize_keyword(secondary)
    primary = normalize_keyword(primary)
    if not secondary or secondary.lower() == primary.lower():
        return False
    body = collect_body_markdown(article)
    if keyword_in_text(body, secondary):
        return False
    sections = article.get("sections")
    if not isinstance(sections, list):
        return False
    for index, section in enumerate(sections):
        if index == 0:
            continue
        if not isinstance(section, dict):
            continue
        content = str(section.get("content_markdown") or "")
        if not content.strip() or keyword_in_text(content, secondary):
            continue
        updated, added = insert_keyword_in_text(content, secondary, max_additions=1)
        if added:
            section["content_markdown"] = updated
            report.changes.append(f"Secondary focus keyword added: {secondary}")
            return True
    return False


def _optimize_seo_fields(
    seo: dict[str, Any],
    article: dict[str, Any],
    focus_keyword: str,
    article_title: str,
    report: OptimizationReport,
) -> None:
    title = str(seo.get("seo_title") or article_title or "").strip()
    improved_title, title_changed = improve_seo_title(title, focus_keyword)
    if title_changed:
        seo["seo_title"] = improved_title
        report.seo_title_improved = True
        report.changes.append("SEO title improved.")

    description = str(seo.get("seo_description") or article.get("meta_description") or "").strip()
    improved_description, description_changed = improve_meta_description(description, focus_keyword)
    if description_changed:
        seo["seo_description"] = improved_description
        report.meta_description_improved = True
        report.changes.append("Meta description improved.")


def _ensure_keyword_in_intro(article: dict[str, Any], keyword: str, report: OptimizationReport) -> bool:
    sections = article.get("sections")
    if not isinstance(sections, list) or not sections:
        return False
    first = sections[0]
    if not isinstance(first, dict):
        return False
    content = str(first.get("content_markdown") or "")
    intro_slice = content[: max(200, len(content) // 10 or 200)]
    if keyword_in_text(intro_slice, keyword):
        return False
    updated, added = insert_keyword_in_text(content, keyword, max_additions=1)
    if added:
        first["content_markdown"] = updated
        report.changes.append("Focus keyword added to intro.")
        return True
    return False


def _ensure_keyword_in_heading(article: dict[str, Any], keyword: str, report: OptimizationReport) -> bool:
    sections = article.get("sections")
    if not isinstance(sections, list):
        return False
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        if heading and not keyword_in_text(heading, keyword):
            if len(heading) <= 48:
                section["heading"] = f"{keyword}: {heading}"
            else:
                section["heading"] = f"{heading} — {keyword}"
            report.changes.append("Focus keyword added to heading.")
            return True
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sub_heading = str(subsection.get("heading") or "").strip()
            if not sub_heading or keyword_in_text(sub_heading, keyword):
                continue
            subsection["heading"] = f"{sub_heading} — {keyword}"
            report.changes.append("Focus keyword added to heading.")
            return True
    return False



def _ensure_keyword_density(
    article: dict[str, Any],
    keyword: str,
    min_target: int,
    max_target: int,
    report: OptimizationReport,
) -> None:
    body = collect_body_markdown(article)
    current = count_keyword_occurrences(body, keyword)
    if current >= min_target or current >= max_target:
        return
    needed = min_target - current
    sections = article.get("sections")
    if not isinstance(sections, list):
        return
    added = 0
    for section in sections:
        if added >= needed or current + added >= max_target:
            break
        if not isinstance(section, dict):
            continue
        content = str(section.get("content_markdown") or "")
        if keyword_in_text(content, keyword):
            continue
        updated, count = insert_keyword_in_text(content, keyword, max_additions=1)
        if count:
            section["content_markdown"] = updated
            added += count
            report.changes.append("Focus keyword added to body section.")
    if added:
        return
    for section in sections:
        if added >= needed or current + added >= max_target:
            break
        content = str(section.get("content_markdown") or "")
        updated, count = insert_keyword_in_text(content, keyword, max_additions=1)
        if count:
            section["content_markdown"] = updated
            added += count
            report.changes.append("Focus keyword density adjusted.")


def _split_long_paragraphs_in_article(article: dict[str, Any]) -> int:
    total = 0
    sections = article.get("sections")
    if not isinstance(sections, list):
        return 0
    for section in sections:
        if not isinstance(section, dict):
            continue
        content = str(section.get("content_markdown") or "")
        updated, splits = split_long_paragraphs(content)
        if splits:
            section["content_markdown"] = updated
            total += splits
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sub_content = str(subsection.get("content_markdown") or "")
            updated_sub, sub_splits = split_long_paragraphs(sub_content)
            if sub_splits:
                subsection["content_markdown"] = updated_sub
                total += sub_splits
    excerpt = str(article.get("excerpt") or "")
    if excerpt:
        updated_excerpt, excerpt_splits = split_long_paragraphs(excerpt)
        if excerpt_splits:
            article["excerpt"] = updated_excerpt
            total += excerpt_splits
    return total


def _merge_internal_links(article: dict[str, Any], link_report: ArticleLinkReport) -> None:
    existing = article.get("internal_links")
    merged: list[dict[str, str]] = []
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict):
                merged.append(
                    {
                        "anchor_text": str(item.get("anchor_text") or ""),
                        "url": str(item.get("url") or ""),
                        "type": str(item.get("type") or "article"),
                    }
                )
    seen = {(item["url"], item["anchor_text"]) for item in merged if item.get("url")}
    for placement in link_report.placements:
        key = (placement.url, placement.anchor_text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "anchor_text": placement.anchor_text,
                "url": placement.url,
                "type": "article",
                "title": placement.title,
            }
        )
    article["internal_links"] = merged
