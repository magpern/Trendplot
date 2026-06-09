from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.competitor_candidate_filters import (
    brand_tokens,
    competitor_rejection_reason,
    is_directory_domain,
    is_link_aggregator_domain,
    is_marketplace_domain,
    is_social_domain,
)

CLASSIFICATION_LABELS = {
    "competitor": "competitor",
    "authority_source": "authority source",
    "academic_source": "academic source",
    "government_source": "government source",
    "community": "community",
    "tool": "tool",
    "marketplace": "marketplace",
    "social_or_owned": "social/owned",
    "directory": "directory",
    "unknown": "unknown",
}

GOVERNMENT_TLD_SUFFIXES = (".gov", ".mil", ".gouv", ".go.jp")
ACADEMIC_DOMAIN_HINTS = (
    "pubmed",
    "scholar.google",
    "arxiv",
    "ncbi.nlm.nih",
    "crossref",
    "doi.org",
    "semanticscholar",
    "researchgate",
    "sciencedirect",
    "springer",
    "wiley",
    "plos",
    "biomedcentral",
    "frontiersin",
)
ACADEMIC_TLD_HINTS = (".edu", ".ac.uk", ".edu.au", ".ac.jp")
COMMUNITY_DOMAIN_HINTS = (
    "reddit.com",
    "stackoverflow.com",
    "stackexchange.com",
    "quora.com",
    "discord.com",
    "discord.gg",
)
TOOL_DOMAIN_HINTS = (
    "google-analytics.com",
    "googletagmanager.com",
    "hotjar.com",
    "segment.com",
    "cloudflare.com",
    "stripe.com",
    "paypal.com",
    "shopify.com",
    "mailchimp.com",
    "hubspot.com",
)
AUTHORITY_PATH_HINTS = ("/news/", "/article/", "/press/", "/blog/", "/insights/", "/magazine/")
AUTHORITY_DOMAIN_HINTS = (
    "forbes.com",
    "reuters.com",
    "bbc.co.uk",
    "bbc.com",
    "nytimes.com",
    "theguardian.com",
    "nature.com",
    "sciencemag.org",
    "techcrunch.com",
)


def classification_display_label(classification: str) -> str:
    return CLASSIFICATION_LABELS.get(classification, classification.replace("_", " "))


def classify_domain(
    domain: str,
    url: str = "",
    *,
    website_url: str = "",
    workspace: dict[str, Any] | None = None,
) -> dict[str, str]:
    normalized = domain.lower().lstrip("www.")
    page_url = str(url or "").strip()
    if not page_url and normalized:
        page_url = f"https://{normalized}"

    rejection = competitor_rejection_reason(
        page_url or normalized,
        website_url=website_url,
        workspace=workspace,
    )
    if rejection == "owned_social_channel":
        return {"domain": normalized, "classification": "social_or_owned", "reason": "owned social or brand channel"}

    if _matches_any(normalized, ACADEMIC_DOMAIN_HINTS) or any(normalized.endswith(suffix) for suffix in ACADEMIC_TLD_HINTS):
        return {"domain": normalized, "classification": "academic_source", "reason": "scientific or academic publication source"}
    if _is_nih_gov_domain(normalized):
        return {"domain": normalized, "classification": "academic_source", "reason": "NIH scientific publication source"}
    if _is_government_domain(normalized):
        return {"domain": normalized, "classification": "government_source", "reason": "government domain"}

    if _matches_any(normalized, COMMUNITY_DOMAIN_HINTS):
        return {"domain": normalized, "classification": "community", "reason": "community discussion platform"}
    if rejection in {"social_domain"} or is_social_domain(normalized) or is_link_aggregator_domain(normalized):
        return {"domain": normalized, "classification": "social_or_owned", "reason": "social or community host"}

    if is_directory_domain(normalized):
        return {"domain": normalized, "classification": "directory", "reason": "directory or listing site"}
    if is_marketplace_domain(normalized):
        return {"domain": normalized, "classification": "marketplace", "reason": "marketplace or large platform"}
    if _matches_any(normalized, TOOL_DOMAIN_HINTS):
        return {"domain": normalized, "classification": "tool", "reason": "software, analytics, or infrastructure tool"}

    path = (urlparse(page_url).path or "").lower() if page_url else ""
    if _matches_any(normalized, AUTHORITY_DOMAIN_HINTS) or any(hint in path for hint in AUTHORITY_PATH_HINTS):
        return {"domain": normalized, "classification": "authority_source", "reason": "publisher or authority content site"}

    if _looks_like_commercial_domain(normalized, website_url=website_url, workspace=workspace):
        return {"domain": normalized, "classification": "competitor", "reason": "commercial site in the same market"}

    return {"domain": normalized, "classification": "unknown", "reason": "domain role unclear"}


def partition_candidates_by_classification(
    candidates: list[dict[str, Any]],
    *,
    website_url: str,
    workspace: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    competitor_pool: list[dict[str, Any]] = []
    other_domains: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    seen_other: set[str] = set()

    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if not url:
            continue
        domain = urlparse(url if "://" in url else f"https://{url}").netloc.lower().lstrip("www.")
        if not domain:
            continue
        profile = classify_domain(domain, url, website_url=website_url, workspace=workspace)
        classification = profile["classification"]
        counts[classification] = counts.get(classification, 0) + 1
        if classification == "competitor":
            enriched = dict(candidate)
            enriched["classification"] = "competitor"
            enriched["classification_reason"] = profile["reason"]
            competitor_pool.append(enriched)
            continue
        if domain in seen_other:
            continue
        seen_other.add(domain)
        other_domains.append(
            {
                "domain": domain,
                "url": url,
                "classification": classification,
                "reason": profile["reason"],
                "origin": str(candidate.get("origin") or "discovered"),
            }
        )

    return competitor_pool, other_domains, counts


def enrich_candidate_classification(
    candidate: dict[str, Any],
    *,
    website_url: str,
    workspace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = str(candidate.get("url") or "").strip()
    domain = urlparse(url if "://" in url else f"https://{url}").netloc.lower().lstrip("www.")
    profile = classify_domain(domain, url, website_url=website_url, workspace=workspace)
    enriched = dict(candidate)
    enriched["classification"] = profile["classification"]
    enriched["classification_reason"] = profile["reason"]
    enriched["domain"] = domain or enriched.get("domain")
    return enriched


def is_competitor_classification(classification: str) -> bool:
    return str(classification or "").lower() == "competitor"


def reclassify_historical_competitor_url(
    url: str,
    *,
    website_url: str,
    workspace: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Re-run domain classification for a persisted competitor URL."""
    domain = urlparse(url if "://" in url else f"https://{url}").netloc.lower().lstrip("www.")
    return classify_domain(domain, url, website_url=website_url, workspace=workspace)


def _matches_any(domain: str, hints: tuple[str, ...]) -> bool:
    labels = domain.split(".")
    for hint in hints:
        if domain == hint or domain.endswith(f".{hint}") or hint in labels:
            return True
        if "." in hint and (domain == hint or domain.startswith(f"{hint}.")):
            return True
    return False


def _is_nih_gov_domain(domain: str) -> bool:
    return domain == "nih.gov" or domain.endswith(".nih.gov")


def _is_government_domain(domain: str) -> bool:
    if _matches_any(domain, ACADEMIC_DOMAIN_HINTS):
        return False
    if domain.endswith(".gov.uk") or domain.endswith(".ac.uk"):
        return False
    if domain.endswith(".gov") and not domain.endswith(".nih.gov"):
        return True
    return any(domain.endswith(suffix) for suffix in GOVERNMENT_TLD_SUFFIXES if suffix != ".gov")


def _looks_like_commercial_domain(
    domain: str,
    *,
    website_url: str,
    workspace: dict[str, Any] | None,
) -> bool:
    tokens = brand_tokens(website_url, workspace)
    label = domain.split(".")[0]
    if label in tokens:
        return False
    if domain.count(".") == 0:
        return False
    return True


def _path_segments(path: str) -> list[str]:
    return [segment for segment in re.split(r"[/._-]+", path.lower()) if segment]
