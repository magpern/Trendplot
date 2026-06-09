from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.ai_opportunity_ideation.models import (
    AIOpportunity,
    CONTENT_TYPES,
    RECOMMENDATION_TYPES,
    SEARCH_INTENTS,
)

_SAFETY_VIOLATION = re.compile(
    r"\b(dose|dosing|dosage|treatment|prescription|clinical trial for humans|"
    r"human consumption|veterinary use|take orally|inject yourself|patient outcomes)\b",
    re.I,
)
_RUO_IN_HEADLINE = re.compile(r"\bRUO\b|\(RUO\)|research[- ]use[- ]only", re.I)
_RUO_HEADLINE_ALLOWED = re.compile(
    r"\b(ruo labeling|ruo status|ruo compliance|ruo documentation|regulatory terminology|"
    r"compliance framing|research[- ]use[- ]only labeling|research[- ]use[- ]only disclaimer|"
    r"labeling and documentation|documentation requirements)\b",
    re.I,
)


def parse_opportunities_response(
    payload: dict[str, Any] | None,
    *,
    min_ideas: int = 40,
    max_ideas: int = 60,
    catalog_products: list[str] | None = None,
) -> tuple[list[AIOpportunity], list[str]]:
    warnings: list[str] = []
    if not isinstance(payload, dict):
        warnings.append("response_not_object")
        return [], warnings

    raw = payload.get("opportunities")
    if raw is None:
        warnings.append("missing_opportunities_key")
        return [], warnings
    if not isinstance(raw, list):
        warnings.append("opportunities_not_list")
        return [], warnings

    parsed: list[AIOpportunity] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            warnings.append(f"row_{index}_not_object")
            continue
        opp, row_warnings = _parse_row(item)
        warnings.extend(row_warnings)
        if opp is None:
            continue
        key = _headline_key(opp.headline)
        if key in seen:
            warnings.append(f"duplicate_headline:{opp.headline[:60]}")
            continue
        seen.add(key)
        if _SAFETY_VIOLATION.search(f"{opp.headline} {opp.abstract}"):
            warnings.append(f"safety_violation:{opp.headline[:60]}")
            continue
        if _RUO_IN_HEADLINE.search(opp.headline) and not _RUO_HEADLINE_ALLOWED.search(opp.headline):
            warnings.append(f"ruo_in_headline:{opp.headline[:60]}")
        parsed.append(opp)
        if len(parsed) >= max_ideas:
            break

    if len(parsed) < min_ideas:
        warnings.append(f"below_min_ideas:{len(parsed)}<{min_ideas}")

    if catalog_products:
        coverage_warnings = _catalog_coverage_warnings(parsed, catalog_products)
        warnings.extend(coverage_warnings)

    return parsed, warnings


def merge_opportunity_lists(
    existing: list[AIOpportunity],
    supplemental: list[AIOpportunity],
    *,
    max_ideas: int,
) -> tuple[list[AIOpportunity], list[str]]:
    """Merge supplemental opportunities, dedupe by headline, cap at max_ideas."""
    warnings: list[str] = []
    merged = list(existing)
    seen = {_headline_key(opp.headline) for opp in existing}
    for opp in supplemental:
        key = _headline_key(opp.headline)
        if key in seen:
            warnings.append(f"duplicate_headline:{opp.headline[:60]}")
            continue
        seen.add(key)
        merged.append(opp)
        if len(merged) >= max_ideas:
            break
    return merged, warnings


def _parse_row(item: dict[str, Any]) -> tuple[AIOpportunity | None, list[str]]:
    warnings: list[str] = []
    headline = " ".join(str(item.get("headline") or "").split()).strip()
    abstract = " ".join(str(item.get("abstract") or "").split()).strip()
    if not headline:
        warnings.append("missing_headline")
        return None, warnings
    if not abstract:
        warnings.append(f"missing_abstract:{headline[:40]}")
        return None, warnings

    search_intent = str(item.get("search_intent") or "informational").strip().lower()
    content_type = str(item.get("content_type") or "guide").strip().lower()
    recommendation_type = str(item.get("recommendation_type") or "create").strip().lower()

    if search_intent not in SEARCH_INTENTS:
        warnings.append(f"invalid_search_intent:{search_intent}")
        search_intent = "informational"
    if content_type not in CONTENT_TYPES:
        warnings.append(f"invalid_content_type:{content_type}")
        content_type = "guide"
    if recommendation_type not in RECOMMENDATION_TYPES:
        warnings.append(f"invalid_recommendation_type:{recommendation_type}")
        recommendation_type = "create"

    related_products = _string_list(item.get("related_products"))
    related_topics = _string_list(item.get("related_topics"))
    safety_notes = _string_list(item.get("safety_notes"))

    return (
        AIOpportunity(
            headline=headline,
            abstract=abstract,
            search_intent=search_intent,
            content_type=content_type,
            related_products=related_products,
            related_topics=related_topics,
            target_audience=str(item.get("target_audience") or "").strip(),
            priority_reason=str(item.get("priority_reason") or "").strip(),
            safety_notes=safety_notes,
            recommendation_type=recommendation_type,
        ),
        warnings,
    )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _headline_key(headline: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip()


def _catalog_coverage_warnings(opportunities: list[AIOpportunity], catalog_products: list[str]) -> list[str]:
    if len(catalog_products) > 75:
        return []
    blob_parts: list[str] = []
    for opp in opportunities:
        blob_parts.append(opp.headline.lower())
        blob_parts.extend(p.lower() for p in opp.related_products)
    blob = " ".join(blob_parts)
    missing = [
        product
        for product in catalog_products
        if product.lower() not in blob and product.lower().replace("-", " ") not in blob
    ]
    if missing:
        return [f"catalog_products_not_fully_covered:{len(missing)}"]
    return []


def loads_ideation_payload(content: str) -> tuple[dict[str, Any], list[str]]:
    """Parse ideation LLM JSON, salvaging complete opportunity objects from truncated output."""
    warnings: list[str] = []
    text = content.strip()
    if not text:
        raise json.JSONDecodeError("empty ideation response", text, 0)

    match = re.search(r"\{[\s\S]*", text)
    blob = match.group(0) if match else text
    try:
        payload = json.loads(blob)
    except json.JSONDecodeError as exc:
        try:
            payload = salvage_opportunities_payload(blob)
        except ValueError:
            raise exc
        count = len(payload.get("opportunities") or [])
        warnings.append(f"salvaged_truncated_json:{count}")
        if count == 0:
            raise exc

    if not isinstance(payload, dict):
        raise ValueError("Ideation response was not a JSON object.")
    return payload, warnings


def salvage_opportunities_payload(text: str) -> dict[str, Any]:
    """Extract complete opportunity objects from a truncated opportunities array."""
    opportunities: list[dict[str, Any]] = []
    anchor = text.find('"opportunities"')
    if anchor < 0:
        raise ValueError("missing opportunities key")
    array_start = text.find("[", anchor)
    if array_start < 0:
        raise ValueError("missing opportunities array")

    decoder = json.JSONDecoder()
    pos = array_start + 1
    length = len(text)
    while pos < length:
        while pos < length and text[pos] in " \t\n\r,":
            pos += 1
        if pos >= length or text[pos] == "]":
            break
        if text[pos] != "{":
            break
        try:
            item, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            break
        if isinstance(item, dict):
            opportunities.append(item)
        pos = end

    if not opportunities:
        raise ValueError("no salvageable opportunity objects")
    return {"opportunities": opportunities}


def brief_cache_key(brief: dict[str, Any]) -> str:
    stable = {
        "workspace_id": brief.get("workspace_id"),
        "analysis_job_id": brief.get("analysis_job_id"),
        "catalog_products": sorted(brief.get("catalog_products") or []),
        "existing_page_titles": sorted((brief.get("existing_page_titles") or [])[:40]),
        "competitor_gap_topics": sorted((brief.get("competitor_gap_topics") or [])[:15]),
    }
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:32]
