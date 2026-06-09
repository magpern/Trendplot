from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.catalog.filters import is_entity_quality_junk, is_navigation_label, normalize_topic_label

_CATALOG_SKIP = re.compile(
    r"\b(shop|checkout|cart|clear|customer|gift|focused|fulfillment|comparison discussions)\b",
    re.I,
)

_PRODUCT_PATH_MARKERS = frozenset({"product", "products"})
_SKIP_SLUGS = frozenset({"gift-card", "gift", "cart", "sample"})

# Generic spelling normalizations for catalog labels (not brand-specific).
_NAME_ALIASES: dict[str, str] = {
    "bactriostatic": "Bacteriostatic Water",
    "bactiostatic": "Bacteriostatic Water",
    "bacteriostatic water": "Bacteriostatic Water",
}

_SKU_LIKE = re.compile(
    r"\b[A-Z]{2,}(?:[-+][A-Z0-9]{1,16})+\b|\b[A-Z]{2,}\d{2,}\b",
    re.I,
)

_SHORT_UPPER_TOKENS = frozenset({"dac", "ipa", "cu", "ii", "ruo"})


def catalog_dedupe_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
    return key.replace("bactriostatic", "bacteriostatic").replace("bactiostatic", "bacteriostatic")


def _normalize_product_name(name: str) -> str:
    cleaned = normalize_topic_label(str(name or "").strip())
    alias = _NAME_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    return cleaned


def _catalog_label_from_product_slug(slug: str) -> str | None:
    """Format WooCommerce product slugs into readable catalog labels (generic rules)."""
    cleaned = slug.strip().lower()
    if not cleaned:
        return None
    tokens = cleaned.split("-")
    if len(tokens) == 1:
        return tokens[0].capitalize()

    head = ""
    if tokens[0].isalpha() and tokens[1].isdigit():
        head = f"{tokens[0].upper()}-{tokens[1]}"
        tokens = tokens[2:]
    elif len(tokens) == 2 and tokens[0].isalpha() and tokens[1].isalpha() and len(tokens[1]) <= 3:
        return f"{tokens[0].upper()}-{tokens[1].upper()}"

    parts: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "no":
            parts.append("No")
            index += 1
            continue
        if token in _SHORT_UPPER_TOKENS:
            chunk = [token.upper()]
            next_index = index + 1
            while next_index < len(tokens) and tokens[next_index] in _SHORT_UPPER_TOKENS:
                chunk.append(tokens[next_index].upper())
                next_index += 1
            parts.append(" + ".join(chunk) if len(chunk) > 1 else chunk[0])
            index = next_index
            continue
        if token.isdigit() or re.fullmatch(r"\d+[a-z]*", token):
            parts.append(token)
        elif token.isalpha() and len(token) <= 4:
            parts.append(token.upper())
        else:
            parts.append(token.capitalize())
        index += 1

    body = " ".join(parts).strip()
    if head and body:
        return f"{head} {body}"
    if head:
        return head
    return body or None


def product_name_from_url(url: str) -> str | None:
    """Derive a catalog label from WooCommerce-style /product/{slug}/ URLs."""
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
    if len(segments) < 2:
        return None
    if segments[-2].lower() not in _PRODUCT_PATH_MARKERS:
        return None
    slug = segments[-1].strip().lower()
    if not slug or slug in _SKIP_SLUGS:
        return None
    return _catalog_label_from_product_slug(slug)


def is_product_page_url(url: str) -> bool:
    return bool(product_name_from_url(str(url or "").strip()))


def resolve_product_page_url(
    *,
    product_name: str,
    product_url: str,
    catalog_urls: list[str] | None = None,
) -> str:
    """Prefer a catalog product-page URL over a site root when names match."""
    url = str(product_url or "").strip()
    if is_product_page_url(url):
        return url
    if not catalog_urls:
        return url

    target_key = catalog_dedupe_key(product_name)
    if not target_key:
        return url

    best_url = url
    best_score = 0
    for candidate in catalog_urls:
        candidate = str(candidate or "").strip()
        if not is_product_page_url(candidate):
            continue
        label = product_name_from_url(candidate) or ""
        candidate_key = catalog_dedupe_key(label)
        score = 0
        if candidate_key and candidate_key == target_key:
            score = 100
        elif candidate_key and (target_key in candidate_key or candidate_key in target_key):
            score = 80
        elif label and product_name and label.lower() in product_name.lower():
            score = 70
        elif label and product_name and product_name.lower() in label.lower():
            score = 65
        if score > best_score:
            best_score = score
            best_url = candidate
    return best_url if best_score >= 65 else url


def product_name_from_page_title(title: str) -> str | None:
    """Extract product name from a product page title (strip site suffix)."""
    text = normalize_topic_label(str(title or "").strip())
    if not text:
        return None
    for sep in (" | ", " – ", " - ", " — "):
        if sep in text:
            text = text.split(sep)[0].strip()
    text = re.sub(r"\s*(buy|shop|order)\s+online\s*$", "", text, flags=re.I).strip()
    return _normalize_product_name(text) if _looks_like_catalog_product(text) else None


def _looks_like_catalog_product(name: str) -> bool:
    text = _normalize_product_name(name)
    if not text or len(text) < 3 or len(text) > 80:
        return False
    if _CATALOG_SKIP.search(text):
        return False
    if _SKU_LIKE.search(text) or "+" in text or re.search(r"\bNo DAC\b", text, re.I):
        return True
    if is_navigation_label(text) or is_entity_quality_junk(text):
        return False
    if text[0].isupper() and " " not in text and len(text) >= 4:
        if text.isupper() and len(text) <= 6:
            return True
        if any(ch.islower() for ch in text[1:]):
            return True
    return False


def _is_product_inventory_row(row: dict[str, Any]) -> bool:
    content_type = str(row.get("content_type") or "").lower()
    if content_type == "product":
        return True
    url = str(row.get("url") or row.get("canonical_url") or "")
    if url and product_name_from_url(url):
        return True
    return False


def build_catalog_products(
    *,
    profile_products: list[str] | None = None,
    niche_products: list[str] | None = None,
    niche_entities: list[str] | None = None,
    strategy_products: list[str] | None = None,
    services_products: list[str] | None = None,
    sitemap_products: list[str] | None = None,
    inventory: list[Any] | None = None,
    product_urls: list[str] | None = None,
    max_products: int = 75,
) -> list[str]:
    """Clean, deduped catalog SKUs for opportunity ideation coverage."""
    candidates: list[str] = []
    for source in (
        sitemap_products or [],
        profile_products or [],
        strategy_products or [],
        niche_products or [],
        services_products or [],
        niche_entities or [],
    ):
        for item in source:
            text = str(item if not isinstance(item, dict) else item.get("name") or item.get("title") or "").strip()
            if text:
                candidates.append(text)

    for url in product_urls or []:
        name = product_name_from_url(str(url))
        if name:
            candidates.append(name)

    for row in inventory or []:
        if not isinstance(row, dict):
            continue
        if _is_product_inventory_row(row):
            title = str(row.get("title") or "").strip()
            if title:
                from_title = product_name_from_page_title(title)
                candidates.append(from_title or title)
            url = str(row.get("url") or row.get("canonical_url") or "")
            if url:
                from_url = product_name_from_url(url)
                if from_url:
                    candidates.append(from_url)

    catalog: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        if not _looks_like_catalog_product(raw):
            continue
        name = _normalize_product_name(raw)
        key = catalog_dedupe_key(name)
        if key in seen:
            continue
        seen.add(key)
        catalog.append(name)

    return catalog[: max(1, max_products)]


def product_coverage(
    opportunities: list[dict[str, Any]] | list[str],
    catalog_products: list[str],
) -> dict[str, object]:
    if not catalog_products:
        return {"catalog_count": 0, "mentioned": [], "missing": [], "coverage_rate": 0.0}

    blobs: list[str] = []
    for item in opportunities:
        if isinstance(item, str):
            blobs.append(item.lower())
            continue
        if not isinstance(item, dict):
            continue
        parts = [
            str(item.get("headline") or item.get("title") or ""),
            str(item.get("abstract") or ""),
            " ".join(str(p) for p in (item.get("related_products") or [])),
        ]
        blobs.append(" ".join(parts).lower())
    blob = " ".join(blobs)

    mentioned: list[str] = []
    missing: list[str] = []
    for product in catalog_products:
        token = product.lower()
        if token in blob or token.replace("-", " ") in blob:
            mentioned.append(product)
        else:
            missing.append(product)

    rate = len(mentioned) / len(catalog_products) if catalog_products else 0.0
    return {
        "catalog_count": len(catalog_products),
        "mentioned": mentioned,
        "missing": missing,
        "coverage_rate": round(rate, 3),
    }


def infer_products_from_text(text: str, catalog_products: list[str]) -> list[str]:
    blob = str(text or "").lower()
    if not blob:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for product in catalog_products:
        name = str(product or "").strip()
        if len(name) < 3:
            continue
        key = catalog_dedupe_key(name)
        if key in seen:
            continue
        if name.lower() in blob:
            found.append(name)
            seen.add(key)
    return found
