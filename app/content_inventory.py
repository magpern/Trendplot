"""Workspace content inventory: crawled pages, Trendplot marks, duplicate-topic checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

from app.sitemap_discovery import normalize_url

_NON_EDITORIAL_CONTENT_TYPES = frozenset({"product", "category", "utility"})
_EDITORIAL_CONTENT_TYPES = frozenset({"article", "faq", "unknown"})


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1].lower()


def normalize_topic_text(value: str) -> str:
    text = re.sub(r"[^a-z0-9\s]+", " ", (value or "").lower())
    return " ".join(text.split())


def topic_fingerprint(*, title: str, url: str = "", headings: list[str] | None = None) -> str:
    parts = [normalize_topic_text(title)]
    if url:
        parts.append(slug_from_url(url))
    for heading in headings or []:
        if isinstance(heading, dict):
            parts.append(normalize_topic_text(str(heading.get("text") or "")))
        else:
            parts.append(normalize_topic_text(str(heading)))
    return "|".join(part for part in parts if part)


def coverage_topics_from_page(page: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    title = str(page.get("title") or page.get("h1") or "").strip()
    if title:
        topics.append(title)
    for entity in page.get("entities") or []:
        if isinstance(entity, dict):
            name = str(entity.get("name") or entity.get("text") or "").strip()
        else:
            name = str(entity).strip()
        if name:
            topics.append(name)
    return list(dict.fromkeys(topics))[:12]


def inventory_item_from_page(
    page: dict[str, Any],
    *,
    workspace_id: str,
    source: str = "existing_site",
    created_by_trendplot: bool = False,
    generated_job_id: str | None = None,
    wordpress_post_id: str | None = None,
) -> dict[str, Any]:
    url = str(page.get("url") or "")
    canonical = str(page.get("canonical_url") or url)
    title = str(page.get("title") or page.get("h1") or "").strip()
    content_type = str(page.get("content_type") or "unknown")
    return {
        "workspace_id": workspace_id,
        "url": url,
        "canonical_url": canonical,
        "title": title,
        "slug": slug_from_url(canonical or url),
        "content_type": content_type,
        "source": source,
        "wordpress_post_id": wordpress_post_id,
        "created_by_trendplot": created_by_trendplot,
        "generated_job_id": generated_job_id,
        "published_at": page.get("published_at"),
        "topic_fingerprint": topic_fingerprint(title=title, url=canonical or url, headings=page.get("headings")),
        "coverage_topics": coverage_topics_from_page(page),
        "metadata": {
            "word_count": page.get("word_count"),
            "discovery_reason": page.get("discovery_reason"),
        },
    }


def inventory_item_from_trendplot_publish(
    *,
    workspace_id: str,
    job_id: str,
    title: str,
    url: str,
    wordpress_post_id: str | None,
    published_at: str | None = None,
    topic: str = "",
) -> dict[str, Any]:
    display_title = title or topic
    return {
        "workspace_id": workspace_id,
        "url": url,
        "canonical_url": url,
        "title": display_title,
        "slug": slug_from_url(url),
        "content_type": "article",
        "source": "trendplot_generated",
        "wordpress_post_id": wordpress_post_id,
        "created_by_trendplot": True,
        "generated_job_id": job_id,
        "published_at": published_at,
        "topic_fingerprint": topic_fingerprint(title=display_title, url=url),
        "coverage_topics": [display_title] if display_title else [],
        "metadata": {"trendplot_job_id": job_id},
    }


def is_editorial_inventory_item(item: dict[str, Any]) -> bool:
    if item.get("created_by_trendplot"):
        return True
    content_type = str(item.get("content_type") or "unknown").lower()
    return content_type in _EDITORIAL_CONTENT_TYPES


@dataclass(slots=True)
class InventoryMatch:
    kind: str  # duplicate | related | none
    item: dict[str, Any] | None = None
    similarity: float = 0.0
    reasons: list[str] = field(default_factory=list)


def _title_similarity(left: str, right: str) -> float:
    a = normalize_topic_text(left)
    b = normalize_topic_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _entity_overlap(candidate_topics: list[str], item_topics: list[str]) -> float:
    cand = {normalize_topic_text(t) for t in candidate_topics if t}
    inv = {normalize_topic_text(t) for t in item_topics if t}
    if not cand or not inv:
        return 0.0
    overlap = cand & inv
    return len(overlap) / max(1, min(len(cand), len(inv)))


def find_inventory_match(
    *,
    topic: str,
    title: str,
    target_keyword: str,
    inventory: list[dict[str, Any]],
    candidate_entities: list[str] | None = None,
) -> InventoryMatch:
    fingerprint = topic_fingerprint(title=title or topic, url="")
    keyword_fp = topic_fingerprint(title=target_keyword or topic, url="")
    labels = [topic, title, target_keyword, *(candidate_entities or [])]

    best_duplicate: InventoryMatch | None = None
    best_related: InventoryMatch | None = None

    for item in inventory:
        if not is_editorial_inventory_item(item):
            continue
        item_fp = str(item.get("topic_fingerprint") or "")
        item_title = str(item.get("title") or "")
        item_url = str(item.get("canonical_url") or item.get("url") or "")
        slug = str(item.get("slug") or "")
        reasons: list[str] = []

        if fingerprint and item_fp and fingerprint == item_fp:
            reasons.append("topic_fingerprint match")
        elif keyword_fp and item_fp and keyword_fp == item_fp:
            reasons.append("target keyword fingerprint match")

        title_score = max(
            _title_similarity(title or topic, item_title),
            _title_similarity(target_keyword, item_title),
        )
        if title_score >= 0.88:
            reasons.append(f"title similarity {title_score:.2f}")

        if slug and slug_from_url(item_url) == slug and len(slug) > 3:
            reasons.append("slug match")

        entity_score = _entity_overlap(labels, list(item.get("coverage_topics") or []))
        if entity_score >= 0.6:
            reasons.append(f"entity/topic overlap {entity_score:.2f}")

        if not reasons:
            continue

        similarity = max(title_score, entity_score, 1.0 if "fingerprint" in " ".join(reasons) else 0.0)
        match = InventoryMatch(kind="duplicate", item=item, similarity=similarity, reasons=reasons)
        if title_score >= 0.88 or "fingerprint" in reasons[0]:
            if best_duplicate is None or similarity > best_duplicate.similarity:
                best_duplicate = match
        elif best_related is None or similarity > best_related.similarity:
            best_related = InventoryMatch(kind="related", item=item, similarity=similarity, reasons=reasons)

    if best_duplicate:
        return best_duplicate
    if best_related and best_related.similarity >= 0.72:
        return best_related
    return InventoryMatch(kind="none")


def apply_inventory_to_action(
    action: str,
    candidate: Any,
    match: InventoryMatch,
) -> tuple[str, list[str], str]:
    """Convert CREATE into refresh/expand when inventory already covers the topic."""
    if action != "create" or match.kind == "none" or not match.item:
        return action, [], ""

    item = match.item
    url = str(item.get("canonical_url") or item.get("url") or "")
    title = str(item.get("title") or candidate.topic)
    reason_text = "; ".join(match.reasons)
    meta = candidate.metadata if isinstance(getattr(candidate, "metadata", None), dict) else {}

    if match.kind == "related":
        explanation = (
            f"Related existing page may support a follow-up article instead of a duplicate CREATE: {url}"
        )
        new_meta = {**meta, "inventory_match": "related", "inventory_url": url, "expansion_kind": "follow_up"}
        candidate.metadata = new_meta  # type: ignore[attr-defined]
        if item.get("id"):
            candidate.related_content_id = str(item["id"])  # type: ignore[attr-defined]
        return (
            "expand",
            [
                f"Similar topic already exists ({title}).",
                f"Suggested follow-up rather than duplicate CREATE. ({reason_text})",
            ],
            explanation,
        )

    if item.get("id"):
        candidate.related_content_id = str(item["id"])  # type: ignore[attr-defined]

    if item.get("created_by_trendplot") or str(item.get("source") or "") == "trendplot_generated":
        explanation = (
            f"Not recommended as CREATE because an existing Trendplot article already covers this topic: {url}. "
            "Suggested action: Refresh existing article with competitor FAQ gaps."
        )
        return (
            "refresh",
            [
                f"Trendplot-generated content already covers this topic ({title}).",
                reason_text,
            ],
            explanation,
        )

    gaps = meta.get("competitor_gaps") or meta.get("coverage_gaps")
    if gaps:
        explanation = (
            f"Existing page found ({url}). Suggested action: Expand with competitor gaps (FAQ, schema, internal links)."
        )
        new_meta = {**meta, "inventory_match": "duplicate", "inventory_url": url, "expansion_kind": "content_gaps"}
        candidate.metadata = new_meta  # type: ignore[attr-defined]
        return (
            "expand",
            [
                f"Existing site page covers this topic ({title}).",
                "Expand existing article (FAQ, comparison, schema, internal links).",
                reason_text,
            ],
            explanation,
        )

    explanation = f"Existing page covers this topic ({url}). Suggested action: Refresh existing content."
    return (
        "refresh",
        [f"Duplicate topic vs existing page: {title}.", reason_text],
        explanation,
    )


def normalize_url_for_inventory(url: str) -> str:
    return normalize_url(url)
