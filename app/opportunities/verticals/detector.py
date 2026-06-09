from typing import Any

from app.opportunities.verticals.base import VerticalProfile
from app.opportunities.verticals.registry import get_profile, registered_profiles


LOW_CONFIDENCE_THRESHOLD = 0.22


def detect_vertical(
    *,
    website: dict[str, Any],
    competitors: list[dict[str, Any]],
    override: str = "auto",
) -> tuple[VerticalProfile, dict[str, Any]]:
    requested = (override or "auto").lower()
    if requested != "auto":
        profile = get_profile(requested)
        return profile, {
            "requested_vertical": requested,
            "detected_vertical": profile.id,
            "detected_vertical_confidence": 1.0,
            "mode": "override",
            "scores": {profile.id: 1.0},
            "profile_summary": profile.summary(),
        }

    signal_inventory = {"website": website, "competitors": competitors}
    scores = {
        profile.id: profile.detect_confidence(signal_inventory)
        for profile in registered_profiles()
        if profile.id != "generic"
    }
    detected_id = max(scores, key=scores.get, default="generic")
    confidence = scores.get(detected_id, 0.0)
    profile = get_profile(detected_id if confidence >= LOW_CONFIDENCE_THRESHOLD else "generic")
    return profile, {
        "requested_vertical": "auto",
        "detected_vertical": profile.id,
        "detected_vertical_confidence": round(confidence if profile.id != "generic" else confidence, 3),
        "mode": "auto",
        "scores": {key: round(value, 3) for key, value in sorted(scores.items())},
        "profile_summary": profile.summary(),
    }
