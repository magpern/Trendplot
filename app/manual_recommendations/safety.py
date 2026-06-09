from __future__ import annotations

import re
from typing import Any

_BLOCKED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("treatment", re.compile(r"\b(treat(?:ment)?|cure|therapeutic use|prescribe|patient outcomes)\b", re.I)),
    ("human_use", re.compile(r"\b(human consumption|take orally|inject yourself|self-administer)\b", re.I)),
    (
        "combined_use_recommendation",
        re.compile(
            r"\b(recommend (?:combining|using together|stacking)|should (?:combine|stack|use together)|"
            r"best (?:stack|combination) for|protocol for combining)\b",
            re.I,
        ),
    ),
]


def validate_enrichment_safety(payload: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    blob = " ".join(
        str(payload.get(key) or "")
        for key in (
            "headline",
            "abstract",
            "priority_reason",
            "target_audience",
        )
    )
    blob += " " + " ".join(str(item) for item in payload.get("related_topics") or [])
    for label, pattern in _BLOCKED_PATTERNS:
        if pattern.search(blob):
            violations.append(label)
    return violations


def default_safety_notes(*, content_type: str = "") -> list[str]:
    notes = [
        "Research-use-only framing; no dosing or treatment guidance.",
        "Do not recommend combined use or purchasing decisions.",
    ]
    if content_type == "relationship":
        notes.append("Discuss literature overlap only; no combined-use recommendations.")
    return notes
