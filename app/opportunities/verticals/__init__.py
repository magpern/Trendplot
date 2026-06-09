from app.opportunities.verticals.base import VerticalProfile
from app.opportunities.verticals.detector import detect_vertical
from app.opportunities.verticals.registry import ALLOWED_VERTICALS, get_profile, registered_profiles

__all__ = ["ALLOWED_VERTICALS", "VerticalProfile", "detect_vertical", "get_profile", "registered_profiles"]
