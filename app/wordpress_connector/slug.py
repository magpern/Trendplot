from __future__ import annotations

from urllib.parse import urlparse


def slug_from_public_url(url: str) -> str:
    path = urlparse(str(url or "").strip()).path.strip("/")
    if not path:
        return ""
    return path.split("/")[-1].strip().lower()


def normalize_slug(value: str) -> str:
    return str(value or "").strip().strip("/").lower()


def evaluate_slug_sync(
    *,
    recommended_slug: str,
    request_slug: str,
    response_slug: str,
) -> str | None:
    """Return a user-facing warning when WP ignored the slug Trendplot sent."""
    recommended = normalize_slug(recommended_slug)
    if not recommended:
        return None
    sent = normalize_slug(request_slug)
    actual = normalize_slug(response_slug)
    if sent != recommended:
        return None
    if not actual:
        return None
    if actual == recommended:
        return None
    return (
        f"WordPress kept slug \"{actual}\" instead of recommended \"{recommended}\". "
        "The Trendplot Connector plugin must apply the request \"slug\" field on draft create/update."
    )
