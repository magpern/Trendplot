from __future__ import annotations

import csv
import io
import re
from typing import Any, Callable, Iterable

DEFAULT_EXPORT_ACTIONS: tuple[str, ...] = ("create", "refresh", "monitor")

ColumnExtractor = tuple[str, Callable[[dict[str, Any]], Any]]


def _existing_url_value(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for key in ("inventory_url", "url", "existing_url"):
        value = metadata.get(key)
        if value:
            return str(value)
    return ""


def _reasons_text(item: dict[str, Any]) -> str:
    reasons = item.get("reasons")
    if not isinstance(reasons, list):
        return ""
    return "; ".join(str(reason) for reason in reasons if reason)


COLUMN_EXTRACTORS: tuple[ColumnExtractor, ...] = (
    ("action", lambda item: item.get("action")),
    ("priority", lambda item: item.get("priority")),
    ("title", lambda item: item.get("title")),
    ("topic", lambda item: item.get("topic")),
    ("target_keyword", lambda item: item.get("target_keyword")),
    ("score", lambda item: item.get("score")),
    ("confidence", lambda item: item.get("confidence")),
    ("source_type", lambda item: item.get("source_type")),
    ("explanation", lambda item: item.get("explanation")),
    ("existing_url", _existing_url_value),
    ("reasons", lambda item: _reasons_text(item)),
    ("demand_summary", lambda item: item.get("demand_summary")),
    ("related_content_id", lambda item: item.get("related_content_id")),
    ("id", lambda item: item.get("id")),
)


def normalize_export_actions(actions: Iterable[str] | None) -> set[str]:
    if not actions:
        return set(DEFAULT_EXPORT_ACTIONS)
    normalized = {str(action).strip().lower() for action in actions if str(action).strip()}
    return normalized or set(DEFAULT_EXPORT_ACTIONS)


def recommendations_to_csv(
    recommendations: Iterable[dict[str, Any]],
    *,
    actions: Iterable[str] | None = None,
) -> str:
    allowed_actions = normalize_export_actions(actions)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([name for name, _ in COLUMN_EXTRACTORS])
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").lower()
        if action not in allowed_actions:
            continue
        writer.writerow([_csv_cell(extractor(item)) for _, extractor in COLUMN_EXTRACTORS])
    return buffer.getvalue()


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value % 1 else str(int(value))
    return str(value)


def export_filename(*, website_url: str | None = None, workspace_name: str | None = None) -> str:
    label = workspace_name or website_url or "workspace"
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "workspace"
    return f"recommendations-{slug[:80]}.csv"
