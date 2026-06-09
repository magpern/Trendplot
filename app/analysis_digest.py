from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse

_UTILITY_PATH = re.compile(
    r"/(cart|checkout|account|login|privacy|terms|cookie|refund|shipping-policy|my-account)(/|$)",
    re.I,
)
_PRODUCT_PATH = re.compile(r"/(product|products|shop|store|category|product_cat)(/|$)", re.I)
_EDUCATION_PATH = re.compile(r"/(blog|guide|faq|what-|how-|learn|storage|handling|research)(/|$)", re.I)
_NAV_TITLE = re.compile(
    r"\b(cart|checkout|contact|privacy|terms|login|home|cookie policy|shipping policy)\b",
    re.I,
)


def _path(url: str) -> str:
    return urlparse(url if "://" in url else f"https://{url}").path or "/"


def _domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.netloc or parsed.path or "").lower().removeprefix("www.")


def _truncate(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _unique_strings(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        text = " ".join(str(raw or "").split()).strip()
        if not text or _NAV_TITLE.search(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _compact_page(page: dict[str, Any]) -> dict[str, Any] | None:
    if str(page.get("status") or "") != "ok":
        return None
    url = str(page.get("url") or page.get("canonical_url") or "").strip()
    if not url or _UTILITY_PATH.search(_path(url)):
        return None
    content_type = str(page.get("content_type") or "page")
    h1 = _unique_strings([str(item) for item in (page.get("h1") or [])], limit=1)
    h2 = _unique_strings([str(item) for item in (page.get("h2") or [])], limit=4)
    return {
        "url": url,
        "path": _path(url),
        "title": _truncate(str(page.get("title") or ""), 120),
        "content_type": content_type,
        "h1": h1[0] if h1 else "",
        "topics": h2,
        "entities": _unique_strings([str(item) for item in (page.get("entities") or [])], limit=8),
        "questions": _unique_strings([str(item) for item in (page.get("questions") or [])], limit=3),
    }


def _rollup_pages(pages: list[dict[str, Any]]) -> dict[str, Any]:
    entity_counter: Counter[str] = Counter()
    question_counter: Counter[str] = Counter()
    product_names: list[str] = []
    category_pages: list[str] = []
    education_pages: list[str] = []

    for page in pages:
        url = str(page.get("url") or "")
        path = _path(url)
        title = _truncate(str(page.get("title") or ""), 100)
        if _PRODUCT_PATH.search(path) and title:
            product_names.append(title)
        if "category" in path.lower() or "product_cat" in path.lower():
            if title:
                category_pages.append(title)
        if _EDUCATION_PATH.search(path) or str(page.get("content_type") or "") in {"article", "guide", "faq"}:
            if title:
                education_pages.append(title)
        for entity in page.get("entities") or []:
            label = " ".join(str(entity).split()).strip()
            if label and not _NAV_TITLE.search(label):
                entity_counter[label] += 1
        for question in page.get("questions") or []:
            label = " ".join(str(question).split()).strip()
            if label:
                question_counter[label] += 1

    return {
        "product_page_titles": _unique_strings(product_names, limit=30),
        "category_pages": _unique_strings(category_pages, limit=15),
        "education_pages": _unique_strings(education_pages, limit=15),
        "top_entities": [item for item, _ in entity_counter.most_common(40)],
        "top_questions": [item for item, _ in question_counter.most_common(20)],
    }


def _compact_site(site: dict[str, Any], *, max_pages: int) -> dict[str, Any]:
    raw_pages = site.get("pages") or []
    compact_pages: list[dict[str, Any]] = []
    for page in raw_pages:
        if not isinstance(page, dict):
            continue
        compact = _compact_page(page)
        if compact:
            compact_pages.append(compact)
        if len(compact_pages) >= max_pages:
            break
    return {
        "url": str(site.get("url") or ""),
        "domain": _domain(str(site.get("url") or "")),
        "pages_analyzed": len(compact_pages),
        "pages": compact_pages,
        "rollup": _rollup_pages(compact_pages),
    }


def _compact_competitor(site: dict[str, Any], *, max_pages: int) -> dict[str, Any]:
    titles: list[str] = []
    entities: list[str] = []
    for page in site.get("pages") or []:
        if not isinstance(page, dict) or str(page.get("status") or "") != "ok":
            continue
        title = _truncate(str(page.get("title") or ""), 100)
        if title and not _NAV_TITLE.search(title):
            titles.append(title)
        entities.extend(str(item) for item in (page.get("entities") or [])[:5])
        if len(titles) >= max_pages:
            break
    return {
        "url": str(site.get("url") or ""),
        "domain": _domain(str(site.get("url") or "")),
        "pages_analyzed": len(titles),
        "sample_titles": _unique_strings(titles, limit=max_pages),
        "top_entities": _unique_strings(entities, limit=20),
    }


def build_website_analysis_digest(
    website: dict[str, Any],
    competitors: list[dict[str, Any]],
    *,
    vertical_context: dict[str, Any] | None = None,
    max_pages_per_site: int = 40,
    max_competitor_pages: int = 6,
) -> dict[str, Any]:
    """Compact crawl summary for website_analysis — avoids resending full page payloads."""
    per_competitor = max(1, max_competitor_pages)
    return {
        "website": _compact_site(website, max_pages=max(1, max_pages_per_site)),
        "competitors": [
            _compact_competitor(competitor, max_pages=per_competitor)
            for competitor in competitors
            if isinstance(competitor, dict)
        ],
        "detected_vertical": (vertical_context or {}).get("detected_vertical", "generic"),
        "vertical_confidence": (vertical_context or {}).get("vertical_confidence", 0),
        "vertical_profile_summary": (vertical_context or {}).get("vertical_profile_summary", {}),
        "vertical_adjacent_niches": (vertical_context or {}).get("vertical_adjacent_niches", {}),
    }
