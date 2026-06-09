import re
from dataclasses import dataclass, field
from typing import Any

from app.article_schema import ArticleSchema, normalize_article


@dataclass(slots=True)
class RedundancyReport:
    duplicate_headings: list[str] = field(default_factory=list)
    overlapping_sections: list[dict[str, Any]] = field(default_factory=list)
    repeated_phrases: list[dict[str, Any]] = field(default_factory=list)
    merge_candidates: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "duplicate_headings": self.duplicate_headings,
            "overlapping_sections": self.overlapping_sections,
            "repeated_phrases": self.repeated_phrases,
            "merge_candidates": self.merge_candidates,
            "recommended_actions": self.recommended_actions,
        }


class RedundancyChecker:
    def review(self, article: ArticleSchema, *, required_disclaimer: str | None = None) -> RedundancyReport:
        headings = [section.heading.strip() for section in article.sections if section.heading.strip()]
        normalized_headings = [_normalize_heading(heading) for heading in headings]
        duplicate_headings = sorted(
            {
                heading
                for heading, normalized in zip(headings, normalized_headings)
                if normalized and normalized_headings.count(normalized) > 1
            }
        )
        overlapping_sections = _overlapping_sections(article)
        repeated_phrases = _repeated_phrases(article, required_disclaimer=required_disclaimer)
        merge_candidates = [
            {"heading": item["section_b"], "merge_into": item["section_a"], "similarity": item["similarity"]}
            for item in overlapping_sections
            if item["similarity"] >= 0.72
        ]
        actions = []
        if duplicate_headings:
            actions.append("Merge or rename repeated headings.")
        if merge_candidates:
            actions.append("Remove duplicate sections or merge unique details into the first occurrence.")
        if repeated_phrases:
            actions.append("Reduce repeated safety, handling, CTA, or transition wording.")
        return RedundancyReport(
            duplicate_headings=duplicate_headings,
            overlapping_sections=overlapping_sections,
            repeated_phrases=repeated_phrases,
            merge_candidates=merge_candidates,
            recommended_actions=actions,
        )

    def cleanup(
        self,
        article: ArticleSchema,
        defaults: dict[str, str],
        *,
        required_disclaimer: str | None = None,
    ) -> tuple[ArticleSchema, dict[str, Any]]:
        report = self.review(article, required_disclaimer=required_disclaimer)
        if not (report.duplicate_headings or report.merge_candidates or report.repeated_phrases):
            return article, {"attempted": False, "changed_sections": [], "reason": "No significant redundancy found."}

        data = article.model_dump()
        seen_headings: set[str] = set()
        cleaned_sections = []
        changed_sections = []

        for section in data.get("sections", []):
            heading = str(section.get("heading") or "")
            normalized_heading = _normalize_heading(heading)
            if normalized_heading in seen_headings:
                changed_sections.append(heading)
                continue
            seen_headings.add(normalized_heading)
            section["content_markdown"] = _dedupe_paragraphs(str(section.get("content_markdown") or ""))
            section["subsections"] = _dedupe_subsections(section.get("subsections") or [])
            cleaned_sections.append(section)

        data["sections"] = cleaned_sections
        data["limitations_and_safety"] = _keep_single_disclaimer(
            str(data.get("limitations_and_safety") or ""),
            required_disclaimer=required_disclaimer,
        )
        cleaned_article = normalize_article(data, defaults=defaults)
        return cleaned_article, {
            "attempted": True,
            "changed_sections": changed_sections,
            "reason": "Duplicate headings, highly overlapping sections, and repeated paragraphs were removed.",
            "initial_report": report.as_dict(),
        }


def _overlapping_sections(article: ArticleSchema) -> list[dict[str, Any]]:
    overlaps = []
    sections = [
        (section.heading, _content_tokens(f"{section.content_markdown} " + " ".join(sub.content_markdown for sub in section.subsections)))
        for section in article.sections
    ]
    for index, (heading_a, tokens_a) in enumerate(sections):
        if not tokens_a:
            continue
        for heading_b, tokens_b in sections[index + 1 :]:
            if not tokens_b:
                continue
            similarity = _jaccard(tokens_a, tokens_b)
            if similarity >= 0.45:
                overlaps.append(
                    {
                        "section_a": heading_a,
                        "section_b": heading_b,
                        "similarity": round(similarity, 3),
                    }
                )
    return overlaps


def _repeated_phrases(article: ArticleSchema, *, required_disclaimer: str | None = None) -> list[dict[str, Any]]:
    text = " ".join(
        [
            article.research_context,
            article.limitations_and_safety,
            *[section.content_markdown for section in article.sections],
            *[sub.content_markdown for section in article.sections for sub in section.subsections],
        ]
    )
    disclaimer = _resolve_disclaimer(required_disclaimer)
    candidates = [
        disclaimer,
        "Researchers should",
        "researchers should",
        "refer to the product label",
        "Certificate of Analysis",
        "research-use context",
    ]
    repeated = []
    for phrase in candidates:
        if not phrase:
            continue
        count = len(re.findall(re.escape(phrase), text, flags=re.IGNORECASE))
        if count > 1:
            repeated.append({"phrase": phrase, "count": count})
    return repeated


def _dedupe_paragraphs(value: str) -> str:
    seen: set[str] = set()
    paragraphs = []
    for paragraph in re.split(r"\n{2,}", value):
        normalized = _normalize_text(paragraph)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        paragraphs.append(paragraph.strip())
    return "\n\n".join(paragraphs)


def _dedupe_subsections(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    cleaned = []
    for item in items:
        key = _normalize_heading(str(item.get("heading") or ""))
        if key in seen:
            continue
        seen.add(key)
        item["content_markdown"] = _dedupe_paragraphs(str(item.get("content_markdown") or ""))
        cleaned.append(item)
    return cleaned


def _resolve_disclaimer(required_disclaimer: str | None) -> str:
    if required_disclaimer and str(required_disclaimer).strip():
        return str(required_disclaimer).strip()
    from app.config import Settings

    return Settings().biomedical_ruo_disclaimer


def _keep_single_disclaimer(value: str, *, required_disclaimer: str | None = None) -> str:
    disclaimer = _resolve_disclaimer(required_disclaimer)
    if not disclaimer:
        return value
    parts = value.split(disclaimer)
    if len(parts) <= 2:
        return value
    return f"{parts[0].rstrip()}\n\n{disclaimer}{''.join(parts[1:]).replace(disclaimer, '').strip()}"


def _content_tokens(value: str) -> set[str]:
    stop = {"the", "and", "for", "with", "this", "that", "from", "into", "are", "can", "may", "should"}
    return {token for token in re.findall(r"\b[a-z][a-z0-9-]{3,}\b", value.lower()) if token not in stop}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _normalize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()
