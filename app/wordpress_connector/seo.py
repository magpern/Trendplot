from __future__ import annotations

import json
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from app.seo.focus_keywords import (
    MAX_FOCUS_KEYWORDS,
    all_focus_keyword_phrases,
    normalize_seo_focus_keywords,
    parse_focus_keywords,
)

SEO_JOB_FIELDS = (
    "seo_title",
    "seo_description",
    "seo_focus_keyword",
    "seo_canonical_url",
    "seo_robots",
    "seo_schema_type",
    "seo_generated_at",
    "seo_synced_at",
    "seo_last_error",
    "rank_math_score",
    "recommended_slug",
    "seo_manually_edited",
    "suggested_featured_image_alt",
    "suggested_inline_image_alt",
    "seo_optimized_at",
)

SEO_PACKAGE_FIELDS = (
    "title",
    "description",
    "focus_keyword",
    "canonical_url",
    "robots",
    "schema_type",
)

_ROBOTS_ALLOWED = frozenset(
    {"noindex", "nofollow", "noarchive", "nosnippet", "noimageindex", "noodp"}
)
_ROBOTS_INDEX_FOLLOW = frozenset({"index, follow", "index,follow", "index follow", "index"})

_LLM_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "seo_title": ("seo_title", "meta_title", "title"),
    "seo_description": ("seo_description", "meta_description", "description"),
    "seo_focus_keyword": ("seo_focus_keyword", "focus_keyword", "primary_keyword", "target_keyword"),
    "seo_canonical_url": ("seo_canonical_url", "canonical_url", "canonical"),
    "seo_robots": ("seo_robots", "robots"),
    "seo_schema_type": ("seo_schema_type", "schema_type", "schema"),
}


def job_seo_snapshot(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {field: None for field in SEO_JOB_FIELDS}
    return {field: job.get(field) for field in SEO_JOB_FIELDS}


def seo_package_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM or connector payload into the public SEO package shape."""
    job_fields = normalize_seo_package_payload(payload)
    return {
        "title": job_fields.get("seo_title") or "",
        "description": job_fields.get("seo_description") or "",
        "focus_keyword": job_fields.get("seo_focus_keyword") or "",
        "canonical_url": job_fields.get("seo_canonical_url") or "",
        "robots": robots_for_connector(job_fields.get("seo_robots")),
        "schema_type": job_fields.get("seo_schema_type") or "Article",
    }


def normalize_seo_package_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    package_like = any(key in payload for key in SEO_PACKAGE_FIELDS)
    if package_like and not any(key.startswith("seo_") for key in payload):
        mapped: dict[str, Any] = {
            "seo_title": payload.get("title"),
            "seo_description": payload.get("description"),
            "seo_focus_keyword": payload.get("focus_keyword"),
            "seo_canonical_url": payload.get("canonical_url"),
            "seo_schema_type": payload.get("schema_type"),
        }
        robots = payload.get("robots")
        if isinstance(robots, list):
            mapped["seo_robots"] = robots_from_connector(robots)
        elif robots is not None:
            mapped["seo_robots"] = str(robots)
        return normalize_llm_seo_payload({k: v for k, v in mapped.items() if v is not None})
    return normalize_llm_seo_payload(payload)


def normalize_llm_seo_payload(payload: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for target, aliases in _LLM_KEY_ALIASES.items():
        for key in aliases:
            value = payload.get(key)
            if value is None:
                continue
            if key == "robots" and isinstance(value, list):
                normalized[target] = robots_from_connector(value)
                break
            text = str(value).strip()
            if text:
                normalized[target] = text
                break
    if normalized.get("seo_robots") is None:
        normalized["seo_robots"] = "index, follow"
    if normalized.get("seo_schema_type") is None:
        normalized["seo_schema_type"] = "Article"
    if normalized.get("seo_canonical_url") == "":
        normalized.pop("seo_canonical_url", None)
    return normalized


def apply_focus_keyword_strategy(
    seo_fields: dict[str, str],
    *,
    primary_fallback: str = "",
    product_name: str = "",
    related_products: Iterable[str] | None = None,
) -> dict[str, str]:
    if not seo_fields:
        return seo_fields
    raw = str(seo_fields.get("seo_focus_keyword") or "").strip()
    if not raw and not primary_fallback and not product_name:
        return seo_fields
    seo_fields["seo_focus_keyword"] = normalize_seo_focus_keywords(
        raw,
        primary_fallback=primary_fallback,
        product_name=product_name,
        related_products=related_products,
    )
    return seo_fields


def robots_for_connector(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip().lower() in _ROBOTS_ALLOWED]
    text = str(value or "").strip().lower()
    if not text or text in _ROBOTS_INDEX_FOLLOW:
        return []
    parts = [part.strip().lower() for part in text.replace(";", ",").split(",") if part.strip()]
    return [part for part in parts if part in _ROBOTS_ALLOWED]


def robots_from_connector(value: Any) -> str:
    if isinstance(value, list):
        directives = [str(item).strip().lower() for item in value if str(item).strip()]
        if not directives:
            return "index, follow"
        return ", ".join(directives)
    text = str(value or "").strip()
    return text or "index, follow"


def extract_rank_math_score(payload: dict[str, Any]) -> float | None:
    candidates: list[Any] = []
    for key in ("rank_math_score", "rankmath_score", "seo_score", "score"):
        if key in payload:
            candidates.append(payload.get(key))
    seo = payload.get("seo")
    if isinstance(seo, dict):
        for key in ("rank_math_score", "rankmath_score", "seo_score", "score"):
            if key in seo:
                candidates.append(seo.get(key))
    for value in candidates:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def normalize_connector_seo_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    seo = payload.get("seo") if isinstance(payload.get("seo"), dict) else payload
    if not isinstance(seo, dict):
        return {}
    recognizable = any(
        key in seo
        for key in (
            *SEO_PACKAGE_FIELDS,
            "seo_title",
            "seo_description",
            "seo_focus_keyword",
            "meta_title",
            "meta_description",
        )
    )
    if not recognizable:
        return {}
    normalized = normalize_seo_package_payload(seo)
    score = extract_rank_math_score(payload)
    result: dict[str, Any] = dict(normalized)
    if score is not None:
        result["rank_math_score"] = score
    return result


def seo_fields_for_connector(job_fields: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "seo_title": "title",
        "seo_description": "description",
        "seo_focus_keyword": "focus_keyword",
        "seo_canonical_url": "canonical_url",
        "seo_schema_type": "schema_type",
    }
    payload: dict[str, Any] = {}
    for job_key, connector_key in mapping.items():
        value = job_fields.get(job_key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            payload[connector_key] = text
    if "seo_robots" in job_fields or payload:
        payload["robots"] = robots_for_connector(job_fields.get("seo_robots"))
    return payload


def validate_seo_fields(fields: dict[str, Any], *, require_focus_keyword: bool = False) -> list[str]:
    errors: list[str] = []
    title = str(fields.get("seo_title") or "").strip()
    description = str(fields.get("seo_description") or "").strip()
    focus_keyword = str(fields.get("seo_focus_keyword") or "").strip()
    canonical_url = str(fields.get("seo_canonical_url") or "").strip()

    if not title:
        errors.append("SEO title is required.")
    elif len(title) > 70:
        errors.append("SEO title must be 70 characters or fewer.")

    if not description:
        errors.append("Meta description is required.")
    elif len(description) > 170:
        errors.append("Meta description must be 170 characters or fewer.")

    if require_focus_keyword and not focus_keyword:
        errors.append("Focus keyword is required before syncing to WordPress.")

    focus_parts = all_focus_keyword_phrases(focus_keyword)
    if len(focus_parts) > MAX_FOCUS_KEYWORDS:
        errors.append(f"Focus keyword supports at most {MAX_FOCUS_KEYWORDS} comma-separated phrases.")
    for part in focus_parts[:MAX_FOCUS_KEYWORDS]:
        if len(part.split()) > 8:
            errors.append("Each focus keyword phrase should be concise (eight words or fewer).")

    if canonical_url:
        parsed = urlparse(canonical_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("Canonical URL must be a valid http(s) URL.")

    robots = str(fields.get("seo_robots") or "").strip()
    if robots:
        invalid = [
            part.strip().lower()
            for part in robots.replace(";", ",").split(",")
            if part.strip()
            and part.strip().lower() not in _ROBOTS_ALLOWED
            and part.strip().lower() not in {"index", "follow"}
        ]
        if invalid:
            errors.append(
                "Robots must use index/follow defaults or Rank Math directives: "
                + ", ".join(sorted(_ROBOTS_ALLOWED))
                + "."
            )

    return errors


def sanitize_seo_save_fields(fields: dict[str, Any]) -> dict[str, str | None]:
    cleaned: dict[str, str | None] = {}
    for field in SEO_JOB_FIELDS:
        if field in {"seo_generated_at", "seo_synced_at", "seo_last_error", "rank_math_score"}:
            continue
        if field not in fields:
            continue
        value = fields.get(field)
        if value is None:
            cleaned[field] = None
            continue
        text = str(value).strip()
        cleaned[field] = text or None
    return cleaned


def parse_llm_json_payload(generated_text: str | None, generated_json: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(generated_json, dict) and generated_json:
        return generated_json
    if not generated_text:
        return {}
    try:
        parsed = json.loads(generated_text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
