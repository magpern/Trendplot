import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.publishing_memory.models import CoverageSummary


class PublishingMemoryService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings
        self.refresh_threshold_days = getattr(settings, "coverage_refresh_threshold_days", 180)
        self.saturation_threshold = getattr(settings, "coverage_saturation_threshold", 0.8)
        self.cannibalization_threshold = getattr(settings, "cannibalization_risk_threshold", 0.7)

    def build_memory(
        self,
        *,
        workspace: dict[str, Any],
        understanding: dict[str, Any] | None,
        published_content: list[dict[str, Any]],
        plan_items: list[dict[str, Any]],
        trend_signals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        understanding = understanding or {}
        records = _records(published_content, plan_items)
        expected_entities = _expected_entities(understanding, trend_signals or [])
        entities = []
        clusters = []
        coverage = []

        entity_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
        cluster_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
        audience_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
        intent_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)

        audiences = _audiences(understanding)
        for record in records:
            title = str(record.get("title") or "")
            tokens = _entities_from_title(title)
            for token in tokens:
                entity_hits[token].append(record)
                entities.append({**_record_ref(record), "entity": token, "entity_type": "topic", "confidence": 0.55})
            cluster = _cluster_name(title, tokens)
            if cluster:
                cluster_hits[cluster].append(record)
                clusters.append({**_record_ref(record), "cluster": cluster, "confidence": 0.55})
            for audience in audiences:
                if _overlaps(title, audience):
                    audience_hits[audience].append(record)
            intent = _intent(title)
            intent_hits[intent].append(record)

        for entity in expected_entities:
            entity_hits.setdefault(entity, [])

        for name, hits in entity_hits.items():
            coverage.append(self._summary("entity", name, hits).as_dict())
        for name, hits in cluster_hits.items():
            coverage.append(self._summary("cluster", name, hits).as_dict())
        for name, hits in audience_hits.items():
            coverage.append(self._summary("audience", name, hits).as_dict())
        for name, hits in intent_hits.items():
            coverage.append(self._summary("search_intent", name, hits).as_dict())

        top_gaps = sorted(coverage, key=lambda item: item.get("gap_score") or 0, reverse=True)[:10]
        refresh_candidates = sorted(
            [item for item in coverage if item.get("refresh_candidate")],
            key=lambda item: item.get("refresh_score") or 0,
            reverse=True,
        )[:10]
        return {
            "entities": entities,
            "clusters": clusters,
            "coverage": coverage,
            "summary": {
                "workspace_id": workspace.get("id"),
                "known_entities": len(entity_hits),
                "known_clusters": len(cluster_hits),
                "coverage_items": len(coverage),
                "coverage_gaps": top_gaps,
                "refresh_candidates": refresh_candidates,
            },
        }

    def _summary(self, coverage_type: str, name: str, records: list[dict[str, Any]]) -> CoverageSummary:
        published_count = sum(1 for record in records if record.get("record_type") == "published")
        draft_count = sum(1 for record in records if record.get("record_type") == "plan")
        content_count = len(records)
        latest = _latest_date(records)
        age_days = _age_days(latest)
        freshness = 1.0 if age_days is None else max(0.0, min(1.0, 1 - (age_days / max(1, self.refresh_threshold_days))))
        coverage_score = min(1.0, content_count / 3)
        gap_score = round(max(0.0, 1 - coverage_score), 3)
        saturation = round(min(1.0, content_count / 5), 3)
        duplicate_risk = round(min(1.0, max(0, content_count - 1) / 4), 3)
        cannibalization = duplicate_risk if saturation >= self.saturation_threshold else duplicate_risk * 0.65
        refresh_score = 0.0
        refresh_reason = ""
        if published_count and age_days is not None:
            refresh_score = round(min(1.0, age_days / max(1, self.refresh_threshold_days)), 3)
            if refresh_score >= 0.75:
                refresh_reason = f"Published coverage appears older than {self.refresh_threshold_days} days."
        return CoverageSummary(
            coverage_type=coverage_type,
            name=name,
            coverage_score=round(coverage_score, 3),
            freshness_score=round(freshness, 3),
            content_count=content_count,
            published_count=published_count,
            draft_count=draft_count,
            gap_score=gap_score,
            saturation_score=saturation,
            cannibalization_risk=round(cannibalization, 3),
            duplicate_topic_risk=duplicate_risk,
            refresh_score=refresh_score,
            refresh_candidate=bool(refresh_reason),
            refresh_reason=refresh_reason,
            last_published=latest,
            last_updated=latest,
            last_major_update=latest,
            metadata={"source_records": [_record_ref(record) for record in records[:5]]},
        )


def _records(published_content: list[dict[str, Any]], plan_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for item in published_content:
        records.append(
            {
                "record_type": "published",
                "post_id": item.get("id"),
                "job_id": item.get("job_id"),
                "content_plan_item_id": item.get("content_plan_item_id"),
                "title": item.get("title") or item.get("url") or "",
                "date": item.get("last_checked_at") or item.get("published_at") or item.get("updated_at") or item.get("created_at"),
                "status": item.get("status"),
            }
        )
    for item in plan_items:
        if item.get("state") in {"skipped", "cancelled"}:
            continue
        records.append(
            {
                "record_type": "plan",
                "post_id": None,
                "job_id": item.get("generated_job_id"),
                "content_plan_item_id": item.get("id"),
                "title": item.get("title") or item.get("target_keyword") or "",
                "date": item.get("updated_at") or item.get("scheduled_for") or item.get("created_at"),
                "status": item.get("state"),
            }
        )
    return records


def _expected_entities(understanding: dict[str, Any], trends: list[dict[str, Any]]) -> list[str]:
    values = []
    values.extend(_string_items(understanding.get("products_services")))
    values.extend(_string_items(understanding.get("content_gaps")))
    values.extend(str(signal.get("trend_topic") or "") for signal in trends[:20])
    return _dedupe(values)[:60]


def _audiences(understanding: dict[str, Any]) -> list[str]:
    return _dedupe(_string_items(understanding.get("audiences")))[:20]


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = [value] if value else []
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(str(item.get("name") or item.get("title") or item.get("topic") or item.get("description") or ""))
        else:
            result.append(str(item or ""))
    return result


def _entities_from_title(title: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", " ", title)
    words = [word.strip("-").lower() for word in cleaned.split() if len(word.strip("-")) > 3]
    ignored = {
        "with",
        "from",
        "that",
        "this",
        "your",
        "guide",
        "what",
        "when",
        "where",
        "about",
        "best",
        "complete",
        "ultimate",
    }
    return _dedupe([word for word in words if word not in ignored])[:6]


def _cluster_name(title: str, tokens: list[str]) -> str:
    if len(tokens) >= 2:
        return " ".join(tokens[:2])
    return tokens[0] if tokens else ""


def _intent(title: str) -> str:
    lower = title.lower()
    if any(word in lower for word in ["vs", "versus", "compare", "comparison", "alternative"]):
        return "comparison"
    if any(word in lower for word in ["how", "guide", "steps", "tutorial"]):
        return "how_to"
    if any(word in lower for word in ["best", "top", "review"]):
        return "commercial_investigation"
    if any(word in lower for word in ["what", "why", "meaning", "definition"]):
        return "informational"
    return "topical_article"


def _overlaps(title: str, audience: str) -> bool:
    title_words = set(title.lower().split())
    audience_words = {word for word in audience.lower().split() if len(word) > 3}
    return bool(title_words & audience_words)


def _record_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_id": record.get("post_id"),
        "job_id": record.get("job_id"),
        "content_plan_item_id": record.get("content_plan_item_id"),
    }


def _latest_date(records: list[dict[str, Any]]) -> str | None:
    dates = [str(record.get("date") or "") for record in records if record.get("date")]
    return max(dates) if dates else None


def _age_days(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - parsed).days)


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value or "").split()).strip(" -:,.")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result
