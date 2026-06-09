from dataclasses import dataclass, field
from html import escape, unescape
import re
from typing import Any

import bleach

from app.article_schema import ArticleSchema
from app.review.article_composition import product_reference_integrated
from app.rendering.render_surface import ArticleRenderSurface
from app.rendering.templates.sections import details_list, markdown_block, paragraph, section, unordered_list
from app.rendering.youtube_embed import render_wordpress_youtube_embed

@dataclass(slots=True)
class RenderedArticle:
    html: str
    logs: list[str] = field(default_factory=list)


ALLOWED_RENDER_TAGS = [
    "a",
    "article",
    "br",
    "code",
    "details",
    "div",
    "em",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "iframe",
    "img",
    "li",
    "nav",
    "ol",
    "p",
    "section",
    "span",
    "strong",
    "summary",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
]


ALLOWED_RENDER_ATTRIBUTES = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel", "class", "id"],
    "img": ["alt", "class", "height", "id", "loading", "src", "title", "width"],
    "iframe": [
        "allow",
        "allowfullscreen",
        "class",
        "frameborder",
        "height",
        "id",
        "loading",
        "referrerpolicy",
        "src",
        "title",
        "width",
    ],
}


def render_article(
    article: ArticleSchema,
    youtube_video: dict | None = None,
    generated_images: dict | None = None,
    *,
    surface: ArticleRenderSurface | str = ArticleRenderSurface.EDITORIAL_FULL,
) -> RenderedArticle:
    resolved_surface = ArticleRenderSurface(str(surface))
    logs: list[str] = []
    publishable = resolved_surface == ArticleRenderSurface.PUBLISHABLE
    parts = [
        '<article class="bp-ai-article">',
        _hero(article, logs),
        _generated_featured_image(generated_images, logs),
        _key_takeaways(article, logs),
        _table_of_contents(article, logs),
        _comparison_tables(article, logs),
        "" if publishable else _research_metadata(article, logs),
        _definition_boxes(article, logs),
        _research_context(article, logs),
        _content_sections(article, logs, generated_images),
        "" if publishable else _research_insights(article, logs),
        "" if publishable else _study_cards(article, logs),
        _callout_boxes(article, logs, publishable=publishable),
        _caution_boxes(article, logs),
        _limitations_and_safety(article, logs),
        _research_use_cta(article, logs, publishable=publishable),
        _related_topics(article, logs),
        _faq(article, logs),
        "" if publishable else _references(article, logs),
        _related_video(youtube_video, logs),
        "</article>",
    ]
    raw_html = "\n".join(part for part in parts if part)
    sanitized = bleach.clean(
        raw_html,
        tags=ALLOWED_RENDER_TAGS,
        attributes=ALLOWED_RENDER_ATTRIBUTES,
        protocols=["http", "https"],
        strip=True,
        strip_comments=False,
    )
    sanitized = _restore_wordpress_block_comments(sanitized)
    if not sanitized.strip():
        logs.append("Renderer produced empty HTML.")
    return RenderedArticle(html=sanitized, logs=logs)


def _generated_featured_image(generated_images: dict | None, logs: list[str]) -> str:
    image = _first_image(generated_images, "featured")
    if not image:
        return ""
    source = str(image.get("url") or "")
    if not source:
        logs.append("Generated featured image omitted because no public URL is available.")
        return ""
    alt = str(image.get("alt_text") or "")
    caption = str(image.get("caption") or "")
    caption_html = f'<p class="bp-ai-image-caption">{escape(caption)}</p>' if caption else ""
    return (
        '<figure class="bp-ai-image-block bp-ai-image bp-ai-featured-image">'
        f'<img src="{escape(source)}" alt="{escape(alt)}" loading="lazy">'
        f"{caption_html}</figure>"
    )


def _generated_inline_images(generated_images: dict | None, logs: list[str], section_heading: str | None = None, placement: str | None = None) -> str:
    images = [
        image
        for image in (generated_images or {}).get("images", [])
        if _is_renderable_generated_image(image) and image.get("type") == "inline"
    ][:3]
    if section_heading:
        images = [
            image
            for image in images
            if str(image.get("section_heading") or "").lower() == section_heading.lower()
            and (not placement or str(image.get("placement") or "") == placement)
        ]
    if not images:
        return ""
    figures = []
    for image in images:
        caption = str(image.get("caption") or "")
        caption_html = f'<p class="bp-ai-image-caption">{escape(caption)}</p>' if caption else ""
        figures.append(
            '<figure class="bp-ai-image-block bp-ai-image bp-ai-inline-image">'
            f'<img src="{escape(str(image.get("url") or ""))}" alt="{escape(str(image.get("alt_text") or ""))}" loading="lazy">'
            f"{caption_html}</figure>"
        )
    return "".join(figures)


def _hero(article: ArticleSchema, logs: list[str]) -> str:
    if not article.title:
        logs.append("Missing article title.")
    body = f"<h1>{escape(article.title)}</h1>{paragraph(article.excerpt)}"
    return section("bp-ai-section bp-ai-intro", "", body)


def _key_takeaways(article: ArticleSchema, logs: list[str]) -> str:
    if not article.key_takeaways:
        logs.append("Missing key takeaways.")
        return ""
    return section(
        "bp-ai-key-takeaways",
        "Key Takeaways",
        unordered_list(article.key_takeaways),
    )


def _table_of_contents(article: ArticleSchema, logs: list[str]) -> str:
    headings = article.table_of_contents or [section_item.heading for section_item in article.sections]
    if not article.table_of_contents:
        headings.extend(
            f"{section_item.heading}: {subsection.heading}"
            for section_item in article.sections
            for subsection in section_item.subsections
            if subsection.heading
        )
    headings = [heading for heading in headings if heading]
    if not headings:
        logs.append("Table of contents omitted because no headings were available.")
        return ""
    links = "".join(
        f'<li><a href="#{escape(_slugify(heading))}">{escape(heading)}</a></li>'
        for heading in headings[:12]
    )
    return f'<nav class="bp-ai-section bp-ai-toc"><h2>Table of Contents</h2><ul>{links}</ul></nav>'


def _research_context(article: ArticleSchema, logs: list[str]) -> str:
    if not article.research_context:
        logs.append("Missing research context.")
        return ""
    return section("bp-ai-section", "Research Context", markdown_block(article.research_context))


def _content_sections(article: ArticleSchema, logs: list[str], generated_images: dict | None = None) -> str:
    rendered = []
    for item in article.sections:
        if not item.heading or not (item.content_markdown or item.subsections):
            logs.append(f"Omitted empty section: {item.heading or 'untitled'}.")
            continue
        before = _generated_inline_images(generated_images, logs, item.heading, "before_section")
        after_intro = _generated_inline_images(generated_images, logs, item.heading, "after_section_intro")
        after = _generated_inline_images(generated_images, logs, item.heading, "after_section")
        body = f'<div id="{escape(_slugify(item.heading))}">{markdown_block(item.content_markdown)}{after_intro}</div>'
        if item.subsections:
            body += "".join(
                (
                    f'<section class="bp-ai-subsection" id="{escape(_slugify(f"{item.heading}-{subsection.heading}"))}">'
                    f"<h3>{escape(subsection.heading)}</h3>"
                    f"{markdown_block(subsection.content_markdown)}"
                    "</section>"
                )
                for subsection in item.subsections
                if subsection.heading or subsection.content_markdown
            )
        rendered.append(
            before
            +
            section(
                "bp-ai-section",
                item.heading,
                body,
            )
            + after
        )
    return "\n".join(rendered)


def _research_metadata(article: ArticleSchema, logs: list[str]) -> str:
    panel = article.research_metadata_panel
    if not panel:
        return ""
    rows = [
        ("Research status", panel.research_status),
        ("Study types", ", ".join(panel.study_types)),
        ("Human-use status", panel.human_use_status),
        ("RUO status", panel.ruo_status),
        ("Confidence notes", panel.confidence_notes),
    ]
    body = "".join(f"<p><strong>{escape(label)}:</strong> {escape(value)}</p>" for label, value in rows if value)
    return section("bp-ai-research-metadata", "Research Metadata", body)


def _definition_boxes(article: ArticleSchema, logs: list[str]) -> str:
    if not article.definition_boxes:
        return ""
    body = "".join(
        f'<div class="bp-ai-definition"><h3>{escape(item.term)}</h3><p>{escape(item.definition)}</p></div>'
        for item in article.definition_boxes
        if item.term and item.definition
    )
    return section("bp-ai-section bp-ai-definitions", "Definitions", body)


def _research_insights(article: ArticleSchema, logs: list[str]) -> str:
    if not article.research_insights:
        return ""
    body = "".join(
        (
            f'<div class="bp-ai-callout"><h3>{escape(item.title)}</h3>'
            f"<p>{escape(item.insight)}</p>"
            f"{f'<p><strong>Limitation:</strong> {escape(item.limitation)}</p>' if item.limitation else ''}"
            "</div>"
        )
        for item in article.research_insights
        if item.title and item.insight
    )
    return section("bp-ai-section bp-ai-research-insights", "Research Insights", body)


def _study_cards(article: ArticleSchema, logs: list[str]) -> str:
    if not article.study_cards:
        return ""
    body = "".join(
        (
            f'<article class="bp-ai-study-card"><h3>{escape(card.title)}</h3>'
            f"<p><strong>Source:</strong> {escape(card.source_label or 'reference to verify')}</p>"
            f"<p><strong>Context:</strong> {escape(card.model_or_context)}</p>"
            f"<p><strong>Observed finding:</strong> {escape(card.observed_finding)}</p>"
            f"<p><strong>Limitation:</strong> {escape(card.limitation)}</p>"
            f"<p><strong>Verification needed:</strong> {escape(card.verification_needed or 'Verify source details before citing.')}</p>"
            "</article>"
        )
        for card in article.study_cards
        if card.title
    )
    return section("bp-ai-section bp-ai-study-cards", "Research Notes To Verify", body)


def _comparison_tables(article: ArticleSchema, logs: list[str]) -> str:
    if not article.comparison_tables:
        return ""
    blocks: list[str] = []
    titles: list[str] = []
    for table in article.comparison_tables:
        if not table.headers or not table.rows:
            continue
        titles.append(table.title or "At a Glance")
        header_html = "".join(f"<th>{escape(header)}</th>" for header in table.headers)
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
            for row in table.rows
        )
        title_html = "" if len(article.comparison_tables) == 1 else f"<h3>{escape(table.title)}</h3>"
        blocks.append(
            f'<div class="bp-ai-comparison-table">{title_html}'
            f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table></div>"
        )
    if not blocks:
        return ""
    section_heading = titles[0] if len(titles) == 1 else "At a Glance"
    return section("bp-ai-section bp-ai-comparison", section_heading, "".join(blocks))


def _callout_boxes(article: ArticleSchema, logs: list[str], *, publishable: bool = False) -> str:
    heading = "Practical Notes" if publishable else "Research Callouts"
    return _simple_box_section("bp-ai-callout", heading, article.callout_boxes)


def _caution_boxes(article: ArticleSchema, logs: list[str]) -> str:
    return _simple_box_section("bp-ai-caution", "Cautions", article.caution_boxes)


def _related_topics(article: ArticleSchema, logs: list[str]) -> str:
    if not article.related_topics:
        return ""
    items = "".join(
        "<li>"
        f"<strong>{escape(item.title)}</strong><br>"
        f"<span>{escape(item.angle)}</span>"
        f"{f'<br><a href=\"{escape(item.suggested_url)}\">Read more</a>' if item.suggested_url else ''}"
        "</li>"
        for item in article.related_topics
        if item.title
    )
    return section("bp-ai-section bp-ai-related-topics", "Related Research Topics", f"<ul>{items}</ul>")


def _simple_box_section(css_class: str, heading: str, items: list) -> str:
    if not items:
        return ""
    body = "".join(
        f'<div class="{css_class}"><h3>{escape(getattr(item, "title", ""))}</h3><p>{escape(getattr(item, "message", ""))}</p></div>'
        for item in items
        if getattr(item, "title", "") and getattr(item, "message", "")
    )
    return section("bp-ai-section", heading, body)


def _limitations_and_safety(article: ArticleSchema, logs: list[str]) -> str:
    if not article.limitations_and_safety:
        logs.append("Missing limitations and safety notes.")
        return ""
    return section(
        "bp-ai-section bp-ai-safety",
        "Limitations and Safety Notes",
        markdown_block(article.limitations_and_safety),
    )


def _research_use_cta(article: ArticleSchema, logs: list[str], *, publishable: bool = False) -> str:
    links = [link for link in article.internal_links if link.url]
    if not links:
        logs.append("CTA omitted because no internal links were provided.")
        return ""
    primary = links[0]
    if publishable:
        if product_reference_integrated(article.model_dump(), product_url=primary.url):
            logs.append("Product reference integrated in section body; standalone CTA omitted.")
            return ""
        body = _publishable_product_reference(article, primary)
        return section("bp-ai-cta bp-ai-product-reference", "", body)
    return section(
        "bp-ai-cta",
        "Research Material Reference",
        (
            "<p>Review the relevant product or category page for specifications, documentation, and research-use context.</p>"
            f'<p><a href="{escape(primary.url)}">{escape(primary.anchor_text or "View research material")}</a></p>'
        ),
    )


def _publishable_product_reference(article: ArticleSchema, link: Any) -> str:
    product_name = str(link.anchor_text or article.primary_keyword or article.title or "this research material").strip()
    product_name = re.sub(r"\s+product page$", "", product_name, flags=re.I).strip() or "this research material"
    prose = (
        f"Researchers interested in {product_name} materials can review the "
        f"{product_name} product page for specifications and supporting documentation."
    )
    anchor = product_name if product_name.lower() not in {"view product", "view research material"} else product_name
    return f'<p>{escape(prose)}</p><p><a href="{escape(link.url)}">{escape(anchor)}</a></p>'


def _faq(article: ArticleSchema, logs: list[str]) -> str:
    if not article.faq:
        logs.append("FAQ omitted because no FAQ items were provided.")
        return ""
    return section(
        "bp-ai-faq",
        "FAQ",
        details_list((item.question, item.answer) for item in article.faq),
    )


def _references(article: ArticleSchema, logs: list[str]) -> str:
    if not article.references_to_verify:
        logs.append("References omitted because no references_to_verify were provided.")
        return ""
    items = []
    for ref in article.references_to_verify:
        items.append(
            "<li>"
            f"<strong>{escape(ref.title)}</strong><br>"
            f"<span>Search query: {escape(ref.search_query)}</span><br>"
            f"<span>{escape(ref.reason)}</span>"
            "</li>"
        )
    return section("bp-ai-section bp-ai-references", "References to verify", f"<ul>{''.join(items)}</ul>")


def _related_video(youtube_video: dict | None, logs: list[str]) -> str:
    if not youtube_video:
        logs.append("Related video omitted because no selected video exists.")
        return ""
    embed_html = render_wordpress_youtube_embed(youtube_video)
    if not embed_html:
        logs.append("Related video omitted because no valid YouTube URL or video ID exists.")
        return ""
    title = unescape(str(youtube_video.get("title") or "Related video"))
    channel = unescape(str(youtube_video.get("channel_title") or ""))
    meta = f'<p class="bp-ai-video-meta">{escape(channel)}</p>' if channel else ""
    reason = str(youtube_video.get("selection_reason") or youtube_video.get("reason") or "")
    relevance = (
        f'<p class="bp-ai-video-relevance">{escape(reason)} This video is included as related media, not as factual support unless independently verified.</p>'
        if reason
        else '<p class="bp-ai-video-relevance">This video is included as related media, not as factual support unless independently verified.</p>'
    )
    return section(
        "bp-ai-video",
        "Related Video",
        (
            f"<h3>{escape(title)}</h3>"
            f"{meta}"
            f"{relevance}"
            f"{embed_html}"
        ),
    )


def _slugify(value: str) -> str:
    return "-".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )


def _first_image(generated_images: dict | None, image_type: str) -> dict | None:
    images = (generated_images or {}).get("images", [])
    if not isinstance(images, list):
        return None
    for image in images:
        if _is_renderable_generated_image(image) and image.get("type") == image_type:
            return image
    return None


def _is_renderable_generated_image(image: Any) -> bool:
    return isinstance(image, dict) and image.get("status") == "generated" and bool(image.get("url"))


def _restore_wordpress_block_comments(html: str) -> str:
    return re.sub(
        r"<!--\s+(/?wp:[^>]*)\s+-->",
        lambda match: f"<!-- {unescape(match.group(1))} -->",
        html,
    )

