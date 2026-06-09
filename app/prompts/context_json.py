from __future__ import annotations

import json
from typing import Any


def context_as_json(context: dict[str, Any]) -> str:
    """Compact JSON for LLM prompts (shared by ideation, strategist, reviewer)."""
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))
