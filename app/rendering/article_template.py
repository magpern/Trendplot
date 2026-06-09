from html import escape, unescape
from typing import Any

from app.wordpress import markdown_to_sanitized_html
from app.rendering.youtube_embed import render_wordpress_youtube_embed


def render_article_html(
    article: dict[str, Any],
    markdown: str,
    youtube_video: dict[str, Any] | None = None,
) -> str:
    title = article.get("title") or ""
    excerpt = article.get("excerpt") or ""
    faq = article.get("faq") if isinstance(article.get("faq"), list) else []
    references = (
        article.get("suggested_external_references")
        if isinstance(article.get("suggested_external_references"), list)
        else []
    )

    sections = [
        '<article class="bp-ai-article">',
        _intro(title, excerpt),
        _key_takeaways(markdown),
        _toc(markdown),
        f'<section class="bp-ai-section bp-ai-main-content">{markdown_to_sanitized_html(markdown)}</section>',
        _product_cta(article),
        _faq(faq),
        _references(references),
        _related_video(youtube_video),
        "</article>",
    ]
    return "\n".join(section for section in sections if section)


def _intro(title: str, excerpt: str) -> str:
    if not title and not excerpt:
        return ""
    return (
        '<section class="bp-ai-intro">'
        f"<h1>{escape(title)}</h1>"
        f"<p>{escape(excerpt)}</p>"
        "</section>"
    )


def _key_takeaways(markdown: str) -> str:
    if "key takeaways" in markdown.lower():
        return ""
    return (
        '<section class="bp-ai-key-takeaways">'
        "<h2>Key Takeaways</h2>"
        "<p>Review the article sections below for the main research context, limitations, and practical considerations.</p>"
        "</section>"
    )


def _toc(markdown: str) -> str:
    headings = []
    for line in markdown.splitlines():
        if line.startswith("## ") and line.strip("# ").lower() != "key takeaways":
            heading = line.strip("# ").strip()
            anchor = _slugify(heading)
            headings.append((heading, anchor))

    if not headings:
        return ""

    links = "".join(
        f'<li><a href="#{escape(anchor)}">{escape(heading)}</a></li>'
        for heading, anchor in headings[:10]
    )
    return f'<nav class="bp-ai-toc"><h2>Table of Contents</h2><ul>{links}</ul></nav>'


def _product_cta(article: dict[str, Any]) -> str:
    links = article.get("internal_links") if isinstance(article.get("internal_links"), list) else []
    product_link = next((link for link in links if link.get("url")), None)
    if not product_link:
        return ""

    return (
        '<section class="bp-ai-cta">'
        "<h2>Research Material Reference</h2>"
        "<p>Review the relevant product or category page for specifications, handling notes, and availability.</p>"
        f'<p><a href="{escape(product_link["url"])}">{escape(product_link.get("anchor_text") or "View research material")}</a></p>'
        "</section>"
    )


def _faq(faq: list[dict[str, Any]]) -> str:
    if not faq:
        return ""
    items = []
    for item in faq:
        question = item.get("question")
        answer = item.get("answer")
        if not question or not answer:
            continue
        items.append(
            "<details>"
            f"<summary>{escape(str(question))}</summary>"
            f"<p>{escape(str(answer))}</p>"
            "</details>"
        )
    if not items:
        return ""
    return f'<section class="bp-ai-faq"><h2>FAQ</h2>{"".join(items)}</section>'


def _references(references: list[dict[str, Any]]) -> str:
    if not references:
        return ""
    items = []
    for reference in references:
        title = reference.get("title") or "Reference to verify"
        query = reference.get("search_query") or title
        reason = reference.get("reason") or ""
        items.append(
            "<li>"
            f"<strong>{escape(str(title))}</strong><br>"
            f"<span>Search query: {escape(str(query))}</span><br>"
            f"<span>{escape(str(reason))}</span>"
            "</li>"
        )
    return f'<section class="bp-ai-references"><h2>References to verify</h2><ul>{"".join(items)}</ul></section>'


def _related_video(youtube_video: dict[str, Any] | None) -> str:
    if not youtube_video:
        return ""
    embed_html = render_wordpress_youtube_embed(youtube_video)
    if not embed_html:
        return ""
    title = unescape(str(youtube_video.get("title") or "Related video"))
    channel_title = unescape(str(youtube_video.get("channel_title") or ""))
    meta = f'<p class="bp-ai-video-meta">{escape(channel_title)}</p>' if channel_title else ""
    return (
        '<section class="bp-ai-related-video">'
        "<h2>Related Video</h2>"
        f"<h3>{escape(title)}</h3>"
        f"{meta}"
        f"{embed_html}"
        "</section>"
    )


def _slugify(value: str) -> str:
    return "-".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )

