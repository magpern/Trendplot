from __future__ import annotations

import csv
import io

from app.recommendations_export import (
    DEFAULT_EXPORT_ACTIONS,
    export_filename,
    normalize_export_actions,
    recommendations_to_csv,
)


def _sample_recommendations() -> list[dict]:
    return [
        {
            "id": "rec-1",
            "action": "create",
            "priority": "high",
            "title": "Guide to widgets",
            "topic": "widgets",
            "target_keyword": "widget guide",
            "score": 0.9123,
            "confidence": 0.8,
            "source_type": "market",
            "explanation": "Strong gap vs competitors.",
            "reasons": ["coverage gap", "demand signal"],
            "demand_summary": "Rising interest",
        },
        {
            "id": "rec-2",
            "action": "refresh",
            "priority": "medium",
            "title": "Old widget post",
            "topic": "widgets",
            "target_keyword": "widgets",
            "score": 0.7,
            "confidence": 0.6,
            "source_type": "inventory",
            "metadata": {"inventory_url": "https://example.com/widgets/"},
            "reasons": ["stale content"],
        },
        {
            "id": "rec-3",
            "action": "monitor",
            "priority": "low",
            "title": "Emerging trend",
            "topic": "trend",
            "target_keyword": "trend",
            "score": 0.4,
            "confidence": 0.5,
            "source_type": "trend",
        },
        {
            "id": "rec-4",
            "action": "ignore",
            "priority": "low",
            "title": "Noise",
            "topic": "noise",
            "target_keyword": "noise",
            "score": 0.1,
            "confidence": 0.2,
            "source_type": "inferred",
        },
    ]


def test_recommendations_to_csv_excludes_ignore_by_default() -> None:
    csv_text = recommendations_to_csv(_sample_recommendations())
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0][0] == "action"
    assert len(rows) == 4
    actions = {row[0] for row in rows[1:]}
    assert actions == set(DEFAULT_EXPORT_ACTIONS)
    assert "ignore" not in actions


def test_recommendations_to_csv_includes_existing_url_and_reasons() -> None:
    csv_text = recommendations_to_csv(_sample_recommendations())
    rows = list(csv.reader(io.StringIO(csv_text)))
    refresh_row = next(row for row in rows[1:] if row[0] == "refresh")
    assert refresh_row[9] == "https://example.com/widgets/"
    assert refresh_row[10] == "stale content"


def test_normalize_export_actions_falls_back_to_default() -> None:
    assert normalize_export_actions([]) == set(DEFAULT_EXPORT_ACTIONS)
    assert normalize_export_actions(["Create", " REFRESH "]) == {"create", "refresh"}


def test_export_filename_slugifies_workspace_label() -> None:
    assert export_filename(workspace_name="My Site!").startswith("recommendations-my-site")
    assert export_filename(website_url="https://Example.com/blog").startswith("recommendations-https-example-com-blog")
