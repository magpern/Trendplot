from html import escape
from typing import Iterable

from app.wordpress import markdown_to_sanitized_html


def section(tag_class: str, heading: str, body_html: str) -> str:
    if not body_html.strip():
        return ""
    heading_html = f"<h2>{escape(heading)}</h2>" if heading else ""
    return f'<section class="{escape(tag_class)}">{heading_html}{body_html}</section>'


def paragraph(text: str) -> str:
    return f"<p>{escape(text)}</p>" if text else ""


def unordered_list(items: Iterable[str]) -> str:
    safe_items = [f"<li>{escape(item)}</li>" for item in items if item]
    if not safe_items:
        return ""
    return f"<ul>{''.join(safe_items)}</ul>"


def markdown_block(markdown: str) -> str:
    if not markdown.strip():
        return ""
    return markdown_to_sanitized_html(markdown)


def details_list(items: Iterable[tuple[str, str]]) -> str:
    details = []
    for summary, content in items:
        if not summary or not content:
            continue
        details.append(
            "<details>"
            f"<summary>{escape(summary)}</summary>"
            f"<p>{escape(content)}</p>"
            "</details>"
        )
    return "".join(details)
