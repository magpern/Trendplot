import re
from dataclasses import dataclass
from typing import Any

from app.rendering.render_surface import ArticleRenderSurface

_PUBLISHABLE_HTML_FORBIDDEN = (
    "Research Metadata",
    "Research Insights",
    "Research Notes To Verify",
    "References to verify",
    "Evidence gap",
)


FORBIDDEN_MEDICAL_PHRASES = (
    "treats",
    "cures",
    "safe for",
    "recommended dose",
    "patients should",
)

GENERIC_REGULATED_HINTS = (
    "research use",
    "biomedical",
    "preclinical",
    "ruo",
    "laboratory",
)

PEPTIDE_BIOMEDICAL_HINTS = (
    "peptide",
    "kisspeptin",
    "melanotan",
    "ghk",
    "bpc",
    "tb-500",
    "semaglutide",
    "clinical",
)
STRUCTURAL_SECTION_HEADINGS = (
    "key takeaways",
    "faq",
    "frequently asked questions",
    "references",
    "references to verify",
    "product notes",
)


@dataclass(slots=True)
class QualityCheckResult:
    passed: bool
    warnings: list[str]
    errors: list[str]
    word_count: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "word_count": self.word_count,
            "status": self.status,
        }


def run_article_quality_checks(
    article: dict[str, Any],
    markdown: str,
    product_url: str,
    youtube_video: dict[str, Any] | None,
    min_word_count: int = 1800,
    allow_placeholder_image: bool = False,
    rendered_html: str | None = None,
    publishable_html: str | None = None,
    required_disclaimer: str | None = None,
) -> QualityCheckResult:
    if hasattr(article, "model_dump"):
        article = article.model_dump()
    errors: list[str] = []
    warnings: list[str] = []
    resolved_disclaimer = _resolve_required_disclaimer(required_disclaimer)
    public_markdown = _publishable_markdown(article, markdown)
    text = _plain_text(public_markdown)
    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    lower_text = text.lower()
    normalized_text = _normalize_text(text)
    normalized_disclaimer = _normalize_text(resolved_disclaimer)
    sections = _sections(article)
    headings = [section.get("heading", "").strip() for section in sections if section.get("heading")]

    if word_count < min_word_count:
        errors.append(f"Article is too short: {word_count} words; minimum is {min_word_count}.")

    if not sections:
        errors.append("Structured article has no content sections.")

    empty_sections = [section.get("heading", "Untitled") for section in sections if not section.get("content_markdown", "").strip()]
    if empty_sections:
        errors.append(f"Structured article contains empty sections: {', '.join(empty_sections)}.")

    duplicate_headings = sorted({heading for heading in headings if headings.count(heading) > 1})
    if duplicate_headings:
        errors.append(f"Duplicate headings found: {', '.join(duplicate_headings)}.")

    repeated_paragraphs = _repeated_paragraphs(sections)
    if repeated_paragraphs:
        errors.append(f"Repeated paragraphs found in article sections: {len(repeated_paragraphs)} duplicate paragraph(s).")

    shallow_sections = [
        heading
        for heading, section in zip(headings, sections)
        if not _is_structural_section(heading)
        and len(re.findall(r"\b[\w'-]+\b", section.get("content_markdown", ""))) < 80
    ]
    if shallow_sections:
        warnings.append(f"Some sections may be too shallow: {', '.join(shallow_sections[:5])}.")

    if re.search(r"^#{1,6}\s*$", markdown, flags=re.MULTILINE):
        errors.append("Article contains an empty heading.")

    if product_url and product_url not in markdown and not _internal_links_contain_url(article, product_url):
        errors.append("Product URL is not included in the article/internal links.")

    if is_biomedical_article(article, public_markdown) and normalized_disclaimer not in normalized_text:
        errors.append("RUO disclaimer is missing for regulated research-oriented content.")
    disclaimer_count = normalized_text.count(normalized_disclaimer) if normalized_disclaimer else 0
    if disclaimer_count > 2:
        warnings.append("RUO disclaimer appears repeatedly; keep only required safety notices.")

    for phrase in FORBIDDEN_MEDICAL_PHRASES:
        if phrase in lower_text:
            errors.append(f"Forbidden medical claim phrase found: '{phrase}'.")

    faq = article.get("faq")
    if not isinstance(faq, list) or not faq:
        errors.append("FAQ section is missing.")

    required_sections = ("research context", "limitations and safety")
    searchable_headings = " | ".join(headings).lower()
    for required in required_sections:
        if required not in searchable_headings and required not in lower_text:
            errors.append(f"Required section is missing: {required}.")

    if not allow_placeholder_image and "placehold.co" in markdown.lower():
        errors.append("Placeholder image URL is present in the article.")

    if "related video" in lower_text and not (youtube_video and youtube_video.get("embed_url")):
        errors.append("Related Video heading exists without a valid video embed.")

    if rendered_html is not None:
        if not rendered_html.strip():
            errors.append("Rendered HTML is empty.")
        if "<section" not in rendered_html or "bp-ai-article" not in rendered_html:
            errors.append("Rendered HTML is missing expected article structure.")

    publishable_surface_html = publishable_html if publishable_html is not None else rendered_html
    if publishable_surface_html:
        for forbidden in _PUBLISHABLE_HTML_FORBIDDEN:
            if forbidden.lower() in publishable_surface_html.lower():
                errors.append(f"Publishable HTML must not contain internal verification heading: {forbidden}.")
                break

    if not _has_conclusion(article, markdown):
        warnings.append("Article conclusion or closing research-context summary is missing.")

    malformed_subsections = _malformed_subsections(article)
    if malformed_subsections:
        warnings.append(f"Malformed nested sections found: {', '.join(malformed_subsections[:5])}.")

    empty_components = _empty_rich_components(article)
    if empty_components:
        warnings.append(f"Empty rich components were returned and should be omitted: {', '.join(empty_components[:5])}.")

    if not article.get("backlink_plan"):
        warnings.append("Backlink plan is missing.")

    if not article.get("internal_links"):
        warnings.append("Internal link plan is missing.")

    references = article.get("references_to_verify")
    if not isinstance(references, list) or not references:
        if "suggested_external_references" in article and article.get("suggested_external_references"):
            warnings.append("References are using legacy suggested_external_references; prefer references_to_verify.")
        else:
            warnings.append("references_to_verify is missing.")

    return QualityCheckResult(
        passed=not errors,
        warnings=warnings,
        errors=errors,
        word_count=word_count,
        status="completed" if not errors else "failed_quality",
    )


def _plain_text(markdown: str) -> str:
    without_links = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    return re.sub(r"[#>*_`-]+", " ", without_links)


def _resolve_required_disclaimer(required_disclaimer: str | None) -> str:
    if required_disclaimer and str(required_disclaimer).strip():
        return str(required_disclaimer).strip()
    from app.config import Settings

    return Settings().biomedical_ruo_disclaimer


def is_biomedical_article(
    article: dict[str, Any],
    markdown: str,
    *,
    vertical_id: str | None = None,
    biomedical_keyword_hints: tuple[str, ...] | None = None,
) -> bool:
    if hasattr(article, "model_dump"):
        article = article.model_dump()
    values = [
        article.get("title", ""),
        article.get("primary_keyword", ""),
        " ".join(article.get("secondary_keywords", []) or []),
        markdown,
    ]
    haystack = " ".join(str(value).lower() for value in values)
    hints = list(GENERIC_REGULATED_HINTS)
    if biomedical_keyword_hints:
        hints.extend(str(item).lower() for item in biomedical_keyword_hints if str(item).strip())
    elif vertical_id == "peptides":
        hints.extend(PEPTIDE_BIOMEDICAL_HINTS)
    return any(hint in haystack for hint in hints)


def requires_ruo_disclaimer(
    article: dict[str, Any],
    markdown: str,
    *,
    vertical_id: str | None = None,
    vertical_compliance: dict[str, Any] | None = None,
) -> bool:
    compliance = vertical_compliance if isinstance(vertical_compliance, dict) else {}
    if compliance.get("requires_ruo_framing") is True:
        return True
    if compliance.get("requires_ruo_framing") is False:
        return False
    extra_hints = tuple(str(item) for item in (compliance.get("biomedical_keyword_hints") or []) if str(item).strip())
    return is_biomedical_article(
        article,
        markdown,
        vertical_id=vertical_id,
        biomedical_keyword_hints=extra_hints or None,
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _sections(article: dict[str, Any]) -> list[dict[str, str]]:
    raw_sections = article.get("sections") or []
    sections = []
    for section in raw_sections:
        if hasattr(section, "model_dump"):
            section = section.model_dump()
        if isinstance(section, dict):
            sections.append(
                {
                    "heading": str(section.get("heading", "")),
                    "content_markdown": str(section.get("content_markdown", "")),
                    "subsections": section.get("subsections") if isinstance(section.get("subsections"), list) else [],
                }
            )
    return sections


def _is_structural_section(heading: str) -> bool:
    normalized = heading.strip().lower()
    return any(label in normalized for label in STRUCTURAL_SECTION_HEADINGS)


def _internal_links_contain_url(article: dict[str, Any], product_url: str) -> bool:
    links = article.get("internal_links") or []
    if not isinstance(links, list):
        return False
    return any(isinstance(link, dict) and link.get("url") == product_url for link in links)


def _repeated_paragraphs(sections: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    repeated = []
    for section in sections:
        text = str(section.get("content_markdown") or "")
        for subsection in section.get("subsections") or []:
            if isinstance(subsection, dict):
                text += "\n\n" + str(subsection.get("content_markdown") or "")
        for paragraph in re.split(r"\n{2,}", text):
            normalized = _normalize_text(paragraph)
            if len(normalized.split()) < 12:
                continue
            if normalized in seen:
                repeated.append(paragraph[:80])
            seen.add(normalized)
    return repeated


def _has_conclusion(article: dict[str, Any], markdown: str) -> bool:
    headings = " | ".join(section.get("heading", "") for section in _sections(article)).lower()
    return any(label in headings or label in markdown.lower() for label in ("conclusion", "summary", "closing"))


def _malformed_subsections(article: dict[str, Any]) -> list[str]:
    malformed = []
    for section in article.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                malformed.append(str(section.get("heading") or "Untitled"))
                continue
            if not str(subsection.get("heading") or "").strip() or not str(subsection.get("content_markdown") or "").strip():
                malformed.append(str(section.get("heading") or "Untitled"))
    return malformed


def _publishable_markdown(article: dict[str, Any], fallback_markdown: str) -> str:
    from app.article_schema import ArticleSchema, article_to_markdown

    try:
        model = article if isinstance(article, ArticleSchema) else ArticleSchema.model_validate(article)
        return article_to_markdown(model, surface=ArticleRenderSurface.PUBLISHABLE)
    except Exception:
        return fallback_markdown


def _empty_rich_components(article: dict[str, Any]) -> list[str]:
    empty = []
    for key in (
        "callout_boxes",
        "definition_boxes",
        "caution_boxes",
        "comparison_tables",
        "related_topics",
    ):
        value = article.get(key)
        if isinstance(value, list) and any(
            isinstance(item, dict) and not any(str(v).strip() for v in item.values()) for item in value
        ):
            empty.append(key)
    return empty
