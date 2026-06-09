"""Platform compliance rules for article sanity and review (brand-agnostic defaults)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

SAFE_STORAGE_HANDLING_FALLBACK = (
    "Storage and handling practices reported online can vary by formulation, batch, and supplier documentation. "
    "Researchers should verify handling requirements against the product label, Certificate of Analysis, "
    "and supplied documentation before use."
)

DEFAULT_COMPLIANCE_RULES: dict[str, Any] = {
    "brand_name": "",
    "research_use_only": True,
    "approved_storage_claims": [],
    "approved_handling_claims": [],
    "safe_storage_handling_fallback": SAFE_STORAGE_HANDLING_FALLBACK,
    "rules": [
        "Content is informational blog content, not product instructions.",
        "It may summarize what researchers and public sources commonly discuss online.",
        "Do not present human dosing guidance as instructions.",
        "Do not present therapeutic or disease-treatment claims as established product uses.",
        "Do not present storage, reconstitution, aliquot, or freezing details as definitive instructions unless framed as source-dependent.",
        "Allow compliance phrasing such as no dosing instructions, not for treatment, not for human use, and research-use-only.",
        "Prefer cautious wording for operational details, because handling practices may vary by supplier, batch, and formulation.",
        (
            "If storage or handling guidance is uncertain, use cautious wording: "
            f"{SAFE_STORAGE_HANDLING_FALLBACK}"
        ),
    ],
}

GENERIC_PUBLISHER_FALLBACK = "Publisher"


def default_publisher_name(
    *,
    product_name: str = "",
    product_url: str = "",
    workspace_name: str = "",
    site_name: str = "",
) -> str:
    for candidate in (workspace_name, site_name, product_name):
        text = str(candidate or "").strip()
        if text:
            return text
    if product_url:
        host = urlparse(product_url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            label = host.split(".")[0]
            return label.replace("-", " ").title() if label else GENERIC_PUBLISHER_FALLBACK
    return GENERIC_PUBLISHER_FALLBACK


def build_compliance_rules(
    *,
    brand_name: str = "",
    approved_storage_claims: list[str] | None = None,
    approved_handling_claims: list[str] | None = None,
    vertical_compliance: dict[str, Any] | None = None,
    workspace_compliance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vertical = vertical_compliance if isinstance(vertical_compliance, dict) else {}
    workspace = workspace_compliance if isinstance(workspace_compliance, dict) else {}
    rules = dict(DEFAULT_COMPLIANCE_RULES)
    rules["brand_name"] = (
        str(brand_name or "").strip()
        or str(workspace.get("brand_name") or "").strip()
        or str(vertical.get("brand_name") or "").strip()
    )
    rules["approved_storage_claims"] = _merge_claim_lists(
        approved_storage_claims,
        workspace.get("approved_storage_claims"),
        vertical.get("approved_storage_claims"),
    )
    rules["approved_handling_claims"] = _merge_claim_lists(
        approved_handling_claims,
        workspace.get("approved_handling_claims"),
        vertical.get("approved_handling_claims"),
    )
    if workspace.get("safe_storage_handling_fallback"):
        rules["safe_storage_handling_fallback"] = str(workspace["safe_storage_handling_fallback"])
    extra_rules = vertical.get("rules") or workspace.get("rules")
    if isinstance(extra_rules, list) and extra_rules:
        merged = list(rules["rules"])
        merged.extend(str(item) for item in extra_rules if str(item).strip())
        rules["rules"] = merged
    return rules


def _merge_claim_lists(*sources: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, list):
            continue
        for item in source:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged
