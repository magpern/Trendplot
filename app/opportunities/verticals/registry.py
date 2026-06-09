from app.opportunities.verticals.base import VerticalProfile
from app.opportunities.verticals.fashion import FASHION_PROFILE
from app.opportunities.verticals.generic import GENERIC_PROFILE
from app.opportunities.verticals.peptides import PEPTIDES_PROFILE
from app.opportunities.verticals.shoes import SHOES_PROFILE
from app.opportunities.verticals.software import SOFTWARE_PROFILE
from app.opportunities.verticals.supplements import SUPPLEMENTS_PROFILE


REGISTERED_PROFILES: dict[str, VerticalProfile] = {
    profile.id: profile
    for profile in (
        GENERIC_PROFILE,
        PEPTIDES_PROFILE,
        FASHION_PROFILE,
        SHOES_PROFILE,
        SUPPLEMENTS_PROFILE,
        SOFTWARE_PROFILE,
    )
}

ALLOWED_VERTICALS = ("auto", *REGISTERED_PROFILES.keys())


def get_profile(vertical_id: str | None) -> VerticalProfile:
    return REGISTERED_PROFILES.get((vertical_id or "generic").lower(), GENERIC_PROFILE)


def registered_profiles() -> list[VerticalProfile]:
    return list(REGISTERED_PROFILES.values())
