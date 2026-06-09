from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.catalog.products import is_product_page_url
from app.internal_links.product_linker import _collect_targets, link_first_unlinked_mention
from app.seo.text_utils import keyword_in_text, tokenize_phrase

MAX_ARTICLE_LINKS = 3
_HEADING_LINE = re.compile(r"^\s*#+\s")


@dataclass(slots=True)
class ArticleLinkCandidate:
    job_id: str
    title: str
    url: str
    focus_keyword: str = ""


@dataclass(slots=True)
class ArticleLinkPlacement:
    job_id: str
    title: str
    url: str
    anchor_text: str
    field: str
    section_key: str


@dataclass(slots=True)
class ArticleLinkReport:
    total_links: int = 0
    placements: list[ArticleLinkPlacement] = field(default_factory=list)
    skipped_product_urls: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_links": self.total_links,
            "placements": [
                {
                    "job_id": placement.job_id,
                    "title": placement.title,
                    "url": placement.url,
                    "anchor_text": placement.anchor_text,
                    "field": placement.field,
                    "section_key": placement.section_key,
                }
                for placement in self.placements
            ],
            "skipped_product_urls": self.skipped_product_urls,
            "rules": {
                "max_links": MAX_ARTICLE_LINKS,
                "max_links_per_section": 1,
                "article_urls_only": True,
            },
        }


def build_article_link_candidates(
    jobs: list[dict[str, Any]],
    *,
    current_job_id: str,
    inventory_rows: list[dict[str, Any]] | None = None,
) -> list[ArticleLinkCandidate]:
    candidates: list[ArticleLinkCandidate] = []
    seen_urls: set[str] = set()

    def _add_candidate(*, job_id: str, title: str, url: str, focus_keyword: str) -> None:
        normalized_url = str(url or "").strip()
        if not normalized_url.startswith(("http://", "https://")):
            return
        if job_id == current_job_id:
            return
        if is_product_page_url(normalized_url):
            return
        key = normalized_url.rstrip("/").lower()
        if key in seen_urls:
            return
        seen_urls.add(key)
        candidates.append(
            ArticleLinkCandidate(
                job_id=job_id,
                title=str(title or "").strip(),
                url=normalized_url,
                focus_keyword=str(focus_keyword or "").strip(),
            )
        )

    for job in jobs:
        if not isinstance(job, dict):
            continue
        request_input = job.get("request_input") or {}
        _add_candidate(
            job_id=str(job.get("id") or ""),
            title=str(request_input.get("title") or job.get("seo_title") or ""),
            url=str(job.get("wordpress_public_url") or ""),
            focus_keyword=str(job.get("seo_focus_keyword") or request_input.get("target_keyword") or ""),
        )

    for row in inventory_rows or []:
        if not isinstance(row, dict):
            continue
        content_type = str(row.get("content_type") or row.get("content_type_hint") or "").lower()
        if content_type in {"product", "woocommerce_product"}:
            continue
        url = str(row.get("url") or row.get("canonical_url") or "").strip()
        _add_candidate(
            job_id=str(row.get("generated_job_id") or row.get("id") or ""),
            title=str(row.get("title") or row.get("headline") or ""),
            url=url,
            focus_keyword=str(row.get("focus_keyword") or row.get("target_keyword") or ""),
        )

    return candidates


def score_article_relevance(
    candidate: ArticleLinkCandidate,
    *,
    focus_keyword: str,
    article_title: str,
) -> float:
    focus_tokens = set(tokenize_phrase(focus_keyword) + tokenize_phrase(article_title))
    candidate_tokens = set(tokenize_phrase(candidate.focus_keyword) + tokenize_phrase(candidate.title))
    overlap = focus_tokens & candidate_tokens
    if not overlap:
        return 0.0
    score = float(len(overlap))
    focus_lower = focus_keyword.lower()
    candidate_lower = candidate.focus_keyword.lower()
    if focus_lower and candidate_lower and (focus_lower in candidate_lower or candidate_lower in focus_lower):
        score += 2.0
    path = urlparse(candidate.url).path.lower()
    for token in overlap:
        if len(token) >= 3 and token in path:
            score += 1.0
    return score


def count_article_internal_links(article_json: dict[str, Any], article_urls: set[str]) -> int:
    if not article_urls:
        return 0
    body = _flatten_markdown(article_json)
    count = 0
    for url in article_urls:
        pattern = re.compile(rf"\[[^\]]+\]\({re.escape(url.rstrip('/'))}/?\)", re.IGNORECASE)
        count += len(pattern.findall(body))
    return count


def link_articles_in_structured(
    article_json: dict[str, Any],
    candidates: list[ArticleLinkCandidate],
    *,
    focus_keyword: str,
    article_title: str,
    max_links: int = MAX_ARTICLE_LINKS,
) -> tuple[dict[str, Any], ArticleLinkReport]:
    data = copy.deepcopy(article_json or {})
    report = ArticleLinkReport()
    ranked = sorted(
        [
            (score_article_relevance(candidate, focus_keyword=focus_keyword, article_title=article_title), candidate)
            for candidate in candidates
        ],
        key=lambda item: item[0],
        reverse=True,
    )
    eligible = [candidate for score, candidate in ranked if score > 0]
    if not eligible:
        return data, report

    linked_sections: set[str] = set()
    article_urls = {candidate.url.rstrip("/").lower() for candidate in eligible}

    for candidate in eligible:
        if report.total_links >= max_links:
            break
        if is_product_page_url(candidate.url):
            report.skipped_product_urls.append(candidate.url)
            continue
        anchor_phrase = _select_anchor_phrase(data, candidate)
        if not anchor_phrase:
            continue
        for target in _article_link_targets(data):
            if report.total_links >= max_links:
                break
            if target.section_key in linked_sections:
                continue
            current = target.getter()
            if _HEADING_LINE.match(current.strip()):
                continue
            updated, linked = link_first_unlinked_mention(current, anchor_phrase, candidate.url)
            if not linked:
                continue
            target.setter(updated)
            linked_sections.add(target.section_key)
            report.total_links += 1
            report.placements.append(
                ArticleLinkPlacement(
                    job_id=candidate.job_id,
                    title=candidate.title,
                    url=candidate.url,
                    anchor_text=anchor_phrase,
                    field=target.field_type,
                    section_key=target.section_key,
                )
            )

    _ = article_urls
    return data, report


def _article_link_targets(data: dict[str, Any]):
    return [
        target
        for target in _collect_targets(data)
        if target.field_type in {"section", "subsection", "excerpt"}
    ]


def _select_anchor_phrase(article_json: dict[str, Any], candidate: ArticleLinkCandidate) -> str | None:
    body = _flatten_markdown(article_json)
    phrases: list[str] = []
    if candidate.focus_keyword:
        phrases.append(candidate.focus_keyword)
    if candidate.title:
        phrases.append(candidate.title)
    for token in tokenize_phrase(candidate.title) + tokenize_phrase(candidate.focus_keyword):
        if len(token) >= 4 or any(char.isdigit() for char in token):
            phrases.append(token)
    seen: set[str] = set()
    ordered: list[str] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(phrase)
    for phrase in ordered:
        if keyword_in_text(body, phrase):
            return phrase
    return None


def _flatten_markdown(article_json: dict[str, Any]) -> str:
    parts: list[str] = []
    for section in article_json.get("sections") or []:
        if not isinstance(section, dict):
            continue
        parts.append(str(section.get("heading") or ""))
        parts.append(str(section.get("content_markdown") or ""))
        for subsection in section.get("subsections") or []:
            if isinstance(subsection, dict):
                parts.append(str(subsection.get("heading") or ""))
                parts.append(str(subsection.get("content_markdown") or ""))
    parts.append(str(article_json.get("excerpt") or ""))
    return "\n".join(parts)
