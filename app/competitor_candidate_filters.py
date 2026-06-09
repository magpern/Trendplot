from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from urllib.parse import urlparse
from urllib.parse import urlparse as _urlparse

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "pinterest.com",
    "reddit.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "youtube.com",
}

DIRECTORY_DOMAINS = {
    "wikipedia.org",
    "yellowpages.com",
    "yelp.com",
    "g2.com",
    "capterra.com",
    "semrush.com",
    "ahrefs.com",
    "crunchbase.com",
}

PLATFORM_DOMAINS = {
    "amazon.com",
    "ebay.com",
    "shopify.com",
    "etsy.com",
}


LINK_AGGREGATOR_DOMAINS = {
    "linktr.ee",
    "lnk.bio",
    "bio.link",
    "carrd.co",
}

EXTRA_SOCIAL_DOMAINS = {
    "t.me",
    "telegram.me",
    "telegram.org",
    "youtu.be",
    "discord.gg",
    "discord.com",
    "discordapp.com",
}

def _domain_of(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().lstrip("www.")


def _registrable_domain(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) < 2:
        return domain
    return ".".join(parts[-2:])


def _to_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    normalized_path = parsed.path or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{normalized_path}"


REJECTION_REASON_LABELS = {
    "invalid_url": "invalid URL",
    "same_domain": "same domain",
    "social_domain": "social domain",
    "owned_social_channel": "owned social/channel",
    "directory": "directory",
    "marketplace": "marketplace",
    "duplicate_domain": "duplicate domain",
}


def all_social_domains() -> set[str]:
    return set(SOCIAL_DOMAINS) | set(EXTRA_SOCIAL_DOMAINS)


def is_social_domain(domain: str) -> bool:
    normalized = domain.lower().lstrip("www.")
    for blocked in all_social_domains():
        if normalized == blocked or normalized.endswith(f".{blocked}"):
            return True
    return False


def is_directory_domain(domain: str) -> bool:
    normalized = domain.lower().lstrip("www.")
    for blocked in DIRECTORY_DOMAINS:
        if normalized == blocked or normalized.endswith(f".{blocked}"):
            return True
    return False


def is_marketplace_domain(domain: str) -> bool:
    normalized = domain.lower().lstrip("www.")
    for blocked in PLATFORM_DOMAINS:
        if normalized == blocked or normalized.endswith(f".{blocked}"):
            return True
    return False


def is_link_aggregator_domain(domain: str) -> bool:
    normalized = domain.lower().lstrip("www.")
    for blocked in LINK_AGGREGATOR_DOMAINS:
        if normalized == blocked or normalized.endswith(f".{blocked}"):
            return True
    return False


def brand_tokens(website_url: str, workspace: dict[str, Any] | None = None) -> set[str]:
    tokens: set[str] = set()
    registrable = _registrable_domain(_domain_of(website_url))
    if registrable and "." in registrable:
        label = registrable.split(".")[0].strip().lower()
        if len(label) >= 3:
            tokens.add(label)
    workspace = workspace or {}
    for value in (workspace.get("name"), workspace.get("website_url")):
        text = str(value or "").strip().lower()
        if not text:
            continue
        for part in re.split(r"[^a-z0-9]+", text):
            if len(part) >= 3:
                tokens.add(part)
    return tokens


def official_profile_urls(crawl_site: dict[str, Any] | None) -> set[str]:
    urls: set[str] = set()
    for page in (crawl_site or {}).get("pages") or []:
        if not isinstance(page, dict):
            continue
        for link in page.get("outbound_links") or []:
            if not isinstance(link, dict):
                continue
            normalized = _to_url(link.get("url"))
            if normalized:
                urls.add(normalized)
    return urls


def competitor_rejection_reason(
    url: str,
    *,
    website_url: str,
    workspace: dict[str, Any] | None = None,
    crawl_site: dict[str, Any] | None = None,
    seen_registrable: set[str] | None = None,
) -> str | None:
    normalized = _to_url(url)
    if not normalized:
        return "invalid_url"
    domain = _domain_of(normalized)
    if not domain:
        return "invalid_url"
    base_domain = _domain_of(website_url)
    if domain == base_domain:
        return "same_domain"
    registrable = _registrable_domain(domain)
    if seen_registrable is not None and registrable in seen_registrable:
        return "duplicate_domain"
    if is_social_domain(domain) or is_link_aggregator_domain(domain):
        if _is_owned_brand_channel(normalized, website_url=website_url, workspace=workspace):
            return "owned_social_channel"
        return "social_domain"
    if is_directory_domain(domain):
        return "directory"
    if is_marketplace_domain(domain):
        return "marketplace"
    official = official_profile_urls(crawl_site)
    if normalized in official and (is_social_domain(domain) or is_link_aggregator_domain(domain)):
        return "owned_social_channel"
    return None


def _is_owned_brand_channel(url: str, *, website_url: str, workspace: dict[str, Any] | None) -> bool:
    parsed = _urlparse(url)
    path = (parsed.path or "").lower().strip("/")
    host = parsed.netloc.lower()
    if not is_social_domain(host) and not is_link_aggregator_domain(host):
        return False
    tokens = brand_tokens(website_url, workspace)
    if not tokens:
        return False
    haystack = " ".join([path.replace("-", " "), path.replace("_", " "), host])
    return any(token in haystack for token in tokens)


class CompetitorRejectionTracker:
    def __init__(self, *, sample_limit: int = 8) -> None:
        self.sample_limit = sample_limit
        self.rejected_by_reason: dict[str, int] = {}
        self.rejected_samples: list[dict[str, str]] = []

    def record(self, url: str, reason: str) -> None:
        self.rejected_by_reason[reason] = self.rejected_by_reason.get(reason, 0) + 1
        if len(self.rejected_samples) < self.sample_limit:
            self.rejected_samples.append(
                {
                    "url": url,
                    "reason": REJECTION_REASON_LABELS.get(reason, reason.replace("_", " ")),
                    "reason_code": reason,
                }
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "rejected_by_reason": dict(self.rejected_by_reason),
            "rejected_samples": list(self.rejected_samples),
        }
