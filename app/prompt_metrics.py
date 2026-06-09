from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token) when tiktoken is unavailable."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def json_payload_chars(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def measure_context(label: str, payload: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "label": label,
        "chars": len(serialized),
        "estimated_tokens": estimate_tokens(serialized),
    }
