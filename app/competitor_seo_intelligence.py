from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlparse

from app.catalog.filters import is_entity_quality_junk, normalize_topic_label


_CHROME_TOPIC_LABELS = frozenset(
    {
        "home",
        "contact",
        "contact us",
        "about",
        "about us",
        "login",
        "sign in",
        "cart",
        "checkout",
        "privacy policy",
        "terms",
        "terms of service",
        "cookie policy",
        "search",
        "menu",
        "newsletter",
        "subscribe",
    }
)


def _is_competitor_chrome_signal(topic: str) -> bool:
    label = str(topic or "").strip().lower()
    if not label:
        return True
    if label in _CHROME_TOPIC_LABELS:
        return True
    return label.startswith(("privacy ", "terms ", "cookie "))


CONTENT_TYPE_HINTS: tuple[tuple[str, str], ...] = (
    ("faq", "faq"),
    ("help", "support"),
    ("support", "support"),
    ("guide", "guide"),
    ("blog", "blog"),
    ("article", "blog"),
    ("learn", "guide"),
    ("academy", "guide"),
    ("product", "product"),
    ("products", "product"),
    ("service", "service"),
    ("services", "service"),
    ("category", "category"),
    ("collections", "category"),
)


def _empty_competitor_seo_intelligence(workspace_site: dict[str, Any]) -> dict[str, Any]:
    workspace_pages = _page_signals(workspace_site, is_workspace=True)
    workspace_domain = _domain(workspace_site.get("url") or workspace_site.get("domain") or "")
    workspace_topics = _site_topics(workspace_pages)
    return {
        "workspace_domain": workspace_domain,
        "competitors_discovered": [],
        "pages_analyzed": {
            "workspace": len(workspace_pages),
            "competitors": {},
            "total_competitor_pages": 0,
        },
        "signals_collected": {},
        "workspace_coverage_topics": sorted(workspace_topics)[:120],
        "competitor_coverage_topics": {},
        "coverage_gaps": [],
        "opportunity_signals": [],
        "benchmark_metrics": {},
        "seo_observations": [],
        "top_competitor_topics": {},
    }


def build_competitor_seo_intelligence(
    *,
    workspace_site: dict[str, Any],
    competitor_sites: list[dict[str, Any]],
    max_gap_signals: int = 30,
    target_context: Any | None = None,
) -> dict[str, Any]:
    if not competitor_sites:
        return _empty_competitor_seo_intelligence(workspace_site)

    from app.competitor_target_mapping import TargetSiteContext, build_target_site_context

    context = target_context if isinstance(target_context, TargetSiteContext) else build_target_site_context(
        workspace_site=workspace_site,
    )
    workspace_pages = _page_signals(workspace_site, is_workspace=True)
    competitor_pages_by_domain: dict[str, list[dict[str, Any]]] = {}
    for competitor in competitor_sites:
        domain = _domain(competitor.get("url") or competitor.get("domain") or "")
        if not domain:
            continue
        competitor_pages_by_domain[domain] = _page_signals(competitor, is_workspace=False)

    workspace_topics = _site_topics(workspace_pages)
    competitor_topics: dict[str, set[str]] = {
        domain: _site_topics(pages)
        for domain, pages in competitor_pages_by_domain.items()
    }
    coverage_gaps = _coverage_gaps(
        workspace_topics,
        competitor_topics,
        limit=max_gap_signals,
        target_context=context,
    )

    benchmark = _benchmark_metrics(workspace_pages, competitor_pages_by_domain)
    observations = _seo_observations(benchmark, coverage_gaps)

    return {
        "workspace_domain": _domain(workspace_site.get("url") or workspace_site.get("domain") or ""),
        "competitors_discovered": sorted(competitor_pages_by_domain.keys()),
        "pages_analyzed": {
            "workspace": len(workspace_pages),
            "competitors": {domain: len(pages) for domain, pages in competitor_pages_by_domain.items()},
            "total_competitor_pages": sum(len(pages) for pages in competitor_pages_by_domain.values()),
        },
        "signals_collected": {
            "title": True,
            "meta_description": True,
            "url_structure": True,
            "canonical": True,
            "h1_h2_h3": True,
            "schema_types": True,
            "internal_links": True,
            "outbound_links": True,
            "faq_presence": True,
            "word_count": True,
            "image_count": True,
            "entity_topics": True,
            "content_type": True,
        },
        "workspace_coverage_topics": sorted(workspace_topics)[:120],
        "competitor_coverage_topics": {
            domain: sorted(topics)[:120]
            for domain, topics in competitor_topics.items()
        },
        "coverage_gaps": coverage_gaps,
        "opportunity_signals": [
            {
                "signal_type": "competitor_seo_gap",
                "topic": item.get("recommended_topic") or item["topic"],
                "mapped_entity": item.get("mapped_entity"),
                "seo_pattern": item.get("seo_pattern"),
                "raw_signal": item.get("raw_signal") or item["topic"],
                "competitors": item["competitors"],
                "reason": item["reason"],
                "mapping": item.get("mapping"),
            }
            for item in coverage_gaps
        ],
        "benchmark_metrics": benchmark,
        "seo_observations": observations,
        "top_competitor_topics": _top_topics(competitor_pages_by_domain),
    }


def _page_signals(site: dict[str, Any], *, is_workspace: bool) -> list[dict[str, Any]]:
    site_url = str(site.get("url") or "")
    domain = _domain(site_url)
    signals: list[dict[str, Any]] = []
    for page in site.get("pages", []):
        if page.get("status") != "ok":
            continue
        page_url = str(page.get("url") or "")
        internal_links = _links(page.get("navigation_links", []))
        outbound_links = [link for link in _links(page.get("outbound_links", [])) if _domain(link) and _domain(link) != domain]
        schema_types = [
            str(item).strip()
            for item in page.get("schema_types", [])
            if str(item).strip()
        ][:20]
        h1 = _as_list(page.get("h1"))
        h2 = _as_list(page.get("h2"))
        h3 = _as_list(page.get("h3"))
        headings = h1 + h2 + h3
        entities = [str(item).strip() for item in page.get("entities", []) if str(item).strip()][:60]
        content_type = _content_type_for_page(
            page_url,
            title=str(page.get("title") or ""),
            headings=headings,
            faq_present=bool(page.get("faq_present")),
        )
        signal = {
            "url": page_url,
            "domain": domain,
            "url_path": urlparse(page_url).path or "/",
            "url_depth": _url_depth(page_url),
            "title": str(page.get("title") or ""),
            "meta_description": str(page.get("meta_description") or ""),
            "canonical": str(page.get("canonical_url") or ""),
            "h1": h1,
            "h2": h2,
            "h3": h3,
            "schema_types": schema_types,
            "internal_links": internal_links[:120],
            "outbound_links": outbound_links[:120],
            "internal_links_count": len(internal_links),
            "outbound_links_count": len(outbound_links),
            "faq_present": bool(page.get("faq_present")),
            "word_count": int(page.get("word_count") or 0),
            "image_count": int(page.get("image_count") or 0),
            "entity_topics": entities,
            "content_type": content_type,
            "is_workspace": is_workspace,
            "discovery_reason": str(page.get("discovery_reason") or ""),
        }
        signal["topics"] = _topics_from_page_signal(signal)
        signals.append(signal)
    return signals


def _coverage_gaps(
    workspace_topics: set[str],
    competitor_topics: dict[str, set[str]],
    *,
    limit: int,
    target_context: Any | None = None,
) -> list[dict[str, Any]]:
    from app.competitor_target_mapping import (
        TargetSiteContext,
        map_competitor_signal_to_target,
        mapped_seo_gap_topic,
    )

    context = target_context if isinstance(target_context, TargetSiteContext) else TargetSiteContext()
    topic_to_domains: dict[str, set[str]] = defaultdict(set)
    topic_meta: dict[str, dict[str, Any]] = {}
    for domain, topics in competitor_topics.items():
        for topic in topics:
            if topic in workspace_topics:
                continue
            mapping = map_competitor_signal_to_target(topic, context, competitor_domain=domain)
            if not mapping.create_allowed:
                continue
            gap_topic = mapped_seo_gap_topic(mapping) or topic
            topic_to_domains[gap_topic].add(domain)
            topic_meta[gap_topic] = {
                "raw_signal": mapping.raw_signal,
                "mapped_entity": mapping.mapped_entity,
                "seo_pattern": mapping.seo_pattern,
                "mapping": mapping.as_dict(),
            }

    ranked = sorted(
        topic_to_domains.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[: max(1, limit)]
    gaps = []
    for topic, domains in ranked:
        ordered_domains = sorted(domains)
        meta = topic_meta.get(topic, {})
        gaps.append(
            {
                "topic": topic,
                "recommended_topic": topic,
                "raw_signal": meta.get("raw_signal") or topic,
                "mapped_entity": meta.get("mapped_entity"),
                "seo_pattern": meta.get("seo_pattern"),
                "mapping": meta.get("mapping"),
                "competitors": ordered_domains,
                "competitor_count": len(ordered_domains),
                "reason": (
                    f"Competitor SEO gap for {meta.get('mapped_entity') or topic} "
                    f"({meta.get('seo_pattern') or 'coverage'}) — missing on workspace."
                ),
            }
        )
    return gaps


def _benchmark_metrics(
    workspace_pages: list[dict[str, Any]],
    competitor_pages_by_domain: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    competitor_pages = [page for pages in competitor_pages_by_domain.values() for page in pages]
    workspace = _metric_averages(workspace_pages)
    competitor = _metric_averages(competitor_pages)
    return {
        "workspace": workspace,
        "competitor_average": competitor,
        "delta_competitor_minus_workspace": {
            key: round(float(competitor.get(key) or 0) - float(workspace.get(key) or 0), 2)
            for key in ("avg_word_count", "avg_faq_count", "avg_internal_links", "avg_outbound_links", "avg_image_count")
        },
    }


def _seo_observations(benchmark: dict[str, Any], coverage_gaps: list[dict[str, Any]]) -> list[str]:
    observations: list[str] = []
    workspace = benchmark.get("workspace") if isinstance(benchmark.get("workspace"), dict) else {}
    competitor = benchmark.get("competitor_average") if isinstance(benchmark.get("competitor_average"), dict) else {}
    if float(competitor.get("avg_word_count") or 0) > float(workspace.get("avg_word_count") or 0) * 1.2:
        observations.append("Competitor pages are longer on average than workspace pages.")
    if float(competitor.get("avg_internal_links") or 0) > float(workspace.get("avg_internal_links") or 0) * 1.2:
        observations.append("Competitors use denser internal linking patterns.")
    if float(competitor.get("avg_faq_count") or 0) > float(workspace.get("avg_faq_count") or 0) * 1.2:
        observations.append("Competitors include FAQ sections more often.")
    if coverage_gaps:
        observations.append(
            f"{len(coverage_gaps)} competitor-covered topic gap(s) detected for opportunity review."
        )
    return observations


def _top_topics(competitor_pages_by_domain: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for domain, pages in competitor_pages_by_domain.items():
        counts: Counter[str] = Counter()
        for page in pages:
            counts.update(page.get("topics") or [])
        out[domain] = [topic for topic, _ in counts.most_common(25)]
    return out


def _site_topics(pages: list[dict[str, Any]]) -> set[str]:
    topics: set[str] = set()
    for page in pages:
        for topic in page.get("topics") or []:
            topics.add(topic)
    return topics


def _topics_from_page_signal(signal: dict[str, Any]) -> list[str]:
    candidates = []
    candidates.extend(_as_list(signal.get("entity_topics")))
    candidates.extend(_as_list(signal.get("h1")))
    candidates.extend(_as_list(signal.get("h2")))
    candidates.extend(_as_list(signal.get("h3")))
    title = str(signal.get("title") or "").strip()
    if title:
        candidates.append(title)
    cleaned: list[str] = []
    for value in candidates:
        normalized = normalize_topic_label(str(value))
        if not normalized or is_entity_quality_junk(normalized):
            continue
        if _is_competitor_chrome_signal(normalized):
            continue
        if len(normalized.split()) > 12:
            continue
        cleaned.append(normalized)
    return list(dict.fromkeys(cleaned))[:80]


def _metric_averages(pages: list[dict[str, Any]]) -> dict[str, float]:
    if not pages:
        return {
            "pages_count": 0.0,
            "avg_word_count": 0.0,
            "avg_faq_count": 0.0,
            "avg_internal_links": 0.0,
            "avg_outbound_links": 0.0,
            "avg_image_count": 0.0,
        }
    count = float(len(pages))
    return {
        "pages_count": count,
        "avg_word_count": round(sum(max(0, int(page.get("word_count") or 0)) for page in pages) / count, 2),
        "avg_faq_count": round(sum(1 for page in pages if page.get("faq_present")) / count, 2),
        "avg_internal_links": round(sum(max(0, int(page.get("internal_links_count") or 0)) for page in pages) / count, 2),
        "avg_outbound_links": round(sum(max(0, int(page.get("outbound_links_count") or 0)) for page in pages) / count, 2),
        "avg_image_count": round(sum(max(0, int(page.get("image_count") or 0)) for page in pages) / count, 2),
    }


def _content_type_for_page(url: str, *, title: str, headings: list[str], faq_present: bool) -> str:
    if faq_present:
        return "faq"
    path = (urlparse(url).path or "").lower()
    haystack = " ".join([title.lower(), *[str(item).lower() for item in headings][:6], path])
    if path in {"", "/"}:
        return "homepage"
    for hint, content_type in CONTENT_TYPE_HINTS:
        if f"/{hint}" in path or f"{hint} " in haystack:
            return content_type
    return "page"


def _url_depth(url: str) -> int:
    path = (urlparse(url).path or "/").strip("/")
    return 0 if not path else len([part for part in path.split("/") if part])


def _links(value: Any) -> list[str]:
    out: list[str] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict):
            candidate = str(item.get("url") or "").strip()
        else:
            candidate = str(item or "").strip()
        if candidate:
            out.append(candidate)
    return out


def _domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc.lower().lstrip("www.")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        text = str(value).strip()
        return [text] if text else []
    return []
