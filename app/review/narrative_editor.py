import json
import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import pstdev
from typing import Any

from app.article_schema import ArticleSchema, article_outline, article_to_markdown
from app.prompts import render_prompt
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask
from app.review.ai_pattern_detector import AI_AUTHORITY_PHRASES
from app.review.editorial_rewriter import (
    FORBIDDEN_CLAIM_PATTERNS,
    _safety_constraints,
    validate_rewritten_section,
)
from app.review.sanity_checker import ArticleSanityChecker


OVERUSED_TERMS = (
    "research context",
    "documentation",
    "stability",
    "important",
    "critical",
    "robust",
    "reproducibility",
    "supplier documentation",
    "certificate of analysis",
)

DISCLAIMER_FRAGMENTS = (
    "for research use only",
    "not intended for human consumption",
    "therapeutic or diagnostic use",
    "product label",
    "certificate of analysis",
)


@dataclass(slots=True)
class NarrativeEdit:
    section_id: str
    original_text: str
    replacement_text: str
    reason: str = ""


@dataclass(slots=True)
class NarrativeEditorResult:
    article: ArticleSchema
    pattern_report: dict[str, Any]
    summary: dict[str, Any]
    edits_applied: list[dict[str, Any]] = field(default_factory=list)
    edits_skipped: list[dict[str, Any]] = field(default_factory=list)
    prompt: str = ""
    generated: GeneratedContent | None = None


class NarrativeEditor:
    async def edit(
        self,
        *,
        content_provider: Any,
        article: ArticleSchema,
        request_data: dict[str, Any],
        required_disclaimer: str,
        target_min_word_count: int,
        deterministic_checker: ArticleSanityChecker,
    ) -> NarrativeEditorResult:
        pattern_report = build_narrative_pattern_report(article, required_disclaimer)
        prompt = build_narrative_editor_prompt(
            article=article,
            request_data=request_data,
            required_disclaimer=required_disclaimer,
            pattern_report=pattern_report,
        )
        try:
            generated = await content_provider.generate_article(prompt, task_type=ModelTask.HUMANIZATION)
        except Exception as exc:
            return NarrativeEditorResult(
                article=article,
                pattern_report=pattern_report,
                summary={
                    "attempted": True,
                    "edits_requested": 0,
                    "edits_applied": 0,
                    "edits_skipped": 0,
                    "warnings": [f"Narrative editor model call failed: {exc}"],
                    "pattern_score_before": pattern_report.get("score", 0),
                    "pattern_score_after": pattern_report.get("score", 0),
                    "remaining_warnings": pattern_report.get("warnings", []),
                },
                prompt=prompt,
            )
        payload = _payload_from_generated(generated)
        edits = _edits_from_payload(payload)
        edited_article = article.model_copy(deep=True)
        edits_applied: list[dict[str, Any]] = []
        edits_skipped: list[dict[str, Any]] = []

        for edit in edits:
            candidate_article = edited_article.model_copy(deep=True)
            applied, reason = _apply_exact_edit(candidate_article, edit)
            if not applied:
                edits_skipped.append(_edit_record(edit, status="skipped", reason=reason))
                continue

            validation_errors = validate_rewritten_section(
                original_text=edit.original_text,
                rewritten_text=edit.replacement_text,
                required_disclaimer=required_disclaimer,
                is_safety_section=edit.section_id == "limitations_and_safety" or "safety" in edit.section_id.lower(),
            )
            missing_links = [link for link in _markdown_links(edit.original_text) if link not in edit.replacement_text]
            if missing_links:
                validation_errors.append(f"markdown links removed: {', '.join(missing_links[:3])}")
            if validation_errors:
                edits_skipped.append(_edit_record(edit, status="skipped", reason="; ".join(validation_errors)))
                continue

            if required_disclaimer and required_disclaimer not in json.dumps(candidate_article.model_dump(), ensure_ascii=False):
                edits_skipped.append(_edit_record(edit, status="skipped", reason="required disclaimer removed"))
                continue

            if _word_count(article_to_markdown(candidate_article)) < target_min_word_count:
                edits_skipped.append(_edit_record(edit, status="skipped", reason="word count would fall below threshold"))
                continue

            sanity_report = deterministic_checker.check(candidate_article, product_data=request_data)
            if not sanity_report.passed:
                reasons = [finding.message for finding in sanity_report.blocking_errors]
                edits_skipped.append(_edit_record(edit, status="skipped", reason="; ".join(reasons)))
                continue

            edited_article = candidate_article
            edits_applied.append(_edit_record(edit, status="applied", reason=edit.reason))

        final_report = build_narrative_pattern_report(edited_article, required_disclaimer)
        payload_summary = payload.get("summary") if isinstance(payload.get("summary"), str) else ""
        warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
        summary = {
            "attempted": True,
            "summary": str(payload_summary or "Narrative editor completed targeted exact-match edit review."),
            "edits_requested": len(edits),
            "edits_applied": len(edits_applied),
            "edits_skipped": len(edits_skipped),
            "warnings": [str(item) for item in warnings if str(item).strip()] if isinstance(warnings, list) else [],
            "pattern_score_before": pattern_report.get("score", 0),
            "pattern_score_after": final_report.get("score", 0),
            "remaining_warnings": final_report.get("warnings", []),
            "initial_pattern_report": pattern_report,
            "final_pattern_report": final_report,
        }
        return NarrativeEditorResult(
            article=edited_article,
            pattern_report={**final_report, "initial_report": pattern_report},
            summary=summary,
            edits_applied=edits_applied,
            edits_skipped=edits_skipped,
            prompt=prompt,
            generated=generated,
        )


def build_narrative_pattern_report(article: ArticleSchema, required_disclaimer: str) -> dict[str, Any]:
    locations = _text_locations(article)
    combined = "\n\n".join(location["text"] for location in locations)
    openings = _repeated_section_openings(article)
    closings = _repeated_section_closings(article)
    disclaimer_fragments = _phrase_counts(combined, DISCLAIMER_FRAGMENTS, threshold=2)
    overused_terms = _phrase_counts(combined, OVERUSED_TERMS, threshold=3)
    paragraph_lengths = _similar_paragraph_lengths(combined)
    bullet_symmetry = _symmetrical_bullet_lists(combined)
    repeated_phrases = _repeated_phrases(combined)
    score = min(
        100,
        len(openings) * 8
        + len(closings) * 8
        + min(20, sum(item["count"] for item in disclaimer_fragments))
        + min(20, sum(item["count"] for item in overused_terms))
        + len(paragraph_lengths) * 5
        + len(bullet_symmetry) * 6
        + min(20, len(repeated_phrases) * 4),
    )
    warnings = []
    if openings:
        warnings.append("Repeated section openings remain.")
    if closings:
        warnings.append("Repeated section closings remain.")
    if disclaimer_fragments:
        warnings.append("Disclaimer or compliance fragments are repeated.")
    if overused_terms:
        warnings.append("Technical phrasing is repeated across sections.")
    return {
        "score": score,
        "severity": _severity(score),
        "repeated_section_openings": openings,
        "repeated_section_closings": closings,
        "repeated_disclaimer_fragments": disclaimer_fragments,
        "overused_terms": overused_terms,
        "similar_paragraph_lengths": paragraph_lengths,
        "overly_symmetrical_bullet_lists": bullet_symmetry,
        "repeated_phrases": repeated_phrases,
        "required_disclaimer_present": bool(required_disclaimer and required_disclaimer in combined),
        "warnings": warnings,
        "section_count": len(article.sections),
    }


def build_narrative_editor_prompt(
    *,
    article: ArticleSchema,
    request_data: dict[str, Any],
    required_disclaimer: str,
    pattern_report: dict[str, Any],
) -> str:
    return render_prompt(
        "narrative_editor",
        {
            "article_context_json": json.dumps(_article_context(article, request_data), ensure_ascii=False, indent=2),
            "article_json": article.model_dump_json(indent=2),
            "narrative_pattern_report_json": json.dumps(pattern_report, ensure_ascii=False, indent=2),
            "required_disclaimer": required_disclaimer,
            "safety_constraints_json": json.dumps(_safety_constraints(), ensure_ascii=False, indent=2),
            "forbidden_claims_json": json.dumps(list(FORBIDDEN_CLAIM_PATTERNS), ensure_ascii=False, indent=2),
            "ai_phrases": ", ".join(AI_AUTHORITY_PHRASES),
        },
    )


def _text_locations(article: ArticleSchema) -> list[dict[str, str]]:
    locations: list[dict[str, str]] = []
    if article.excerpt:
        locations.append({"section_id": "intro", "text": article.excerpt})
    if article.research_context:
        locations.append({"section_id": "research_context", "text": article.research_context})
    for index, section in enumerate(article.sections):
        if section.content_markdown:
            locations.append({"section_id": f"section:{index}", "text": section.content_markdown})
        for sub_index, subsection in enumerate(section.subsections):
            if subsection.content_markdown:
                locations.append({"section_id": f"subsection:{index}:{sub_index}", "text": subsection.content_markdown})
    for index, item in enumerate(article.faq):
        if item.answer:
            locations.append({"section_id": f"faq:{index}", "text": item.answer})
    for index, item in enumerate(article.callout_boxes):
        if item.message:
            locations.append({"section_id": f"callout:{index}", "text": item.message})
    for index, item in enumerate(article.caution_boxes):
        if item.message:
            locations.append({"section_id": f"caution:{index}", "text": item.message})
    for index, item in enumerate(article.research_insights):
        if item.insight:
            locations.append({"section_id": f"research_insight:{index}:insight", "text": item.insight})
        if item.limitation:
            locations.append({"section_id": f"research_insight:{index}:limitation", "text": item.limitation})
    for index, item in enumerate(article.study_cards):
        if item.observed_finding:
            locations.append({"section_id": f"study_card:{index}:observed_finding", "text": item.observed_finding})
        if item.limitation:
            locations.append({"section_id": f"study_card:{index}:limitation", "text": item.limitation})
        if item.verification_needed:
            locations.append({"section_id": f"study_card:{index}:verification_needed", "text": item.verification_needed})
    for index, item in enumerate(article.definition_boxes):
        if item.definition:
            locations.append({"section_id": f"definition:{index}", "text": item.definition})
    for index, item in enumerate(article.related_topics):
        if item.angle:
            locations.append({"section_id": f"related_topic:{index}", "text": item.angle})
    if article.limitations_and_safety:
        locations.append({"section_id": "limitations_and_safety", "text": article.limitations_and_safety})
    return locations


def _apply_exact_edit(article: ArticleSchema, edit: NarrativeEdit) -> tuple[bool, str]:
    current = _get_text(article, edit.section_id)
    if current is None:
        return False, "unknown section_id"
    if edit.original_text not in current:
        return False, "original_text did not match target section exactly"
    if current.count(edit.original_text) > 1:
        return False, "original_text matched more than once in target section"
    replacement = current.replace(edit.original_text, edit.replacement_text, 1)
    _set_text(article, edit.section_id, replacement)
    return True, "applied"


def _get_text(article: ArticleSchema, section_id: str) -> str | None:
    parts = section_id.split(":")
    try:
        if section_id == "intro":
            return article.excerpt
        if section_id == "research_context":
            return article.research_context
        if section_id == "limitations_and_safety":
            return article.limitations_and_safety
        if parts[0] == "section" and len(parts) == 2:
            return article.sections[int(parts[1])].content_markdown
        if parts[0] == "subsection" and len(parts) == 3:
            return article.sections[int(parts[1])].subsections[int(parts[2])].content_markdown
        if parts[0] == "faq" and len(parts) == 2:
            return article.faq[int(parts[1])].answer
        if parts[0] == "callout" and len(parts) == 2:
            return article.callout_boxes[int(parts[1])].message
        if parts[0] == "caution" and len(parts) == 2:
            return article.caution_boxes[int(parts[1])].message
        if parts[0] == "research_insight" and len(parts) == 3:
            return str(getattr(article.research_insights[int(parts[1])], parts[2]))
        if parts[0] == "study_card" and len(parts) == 3:
            return str(getattr(article.study_cards[int(parts[1])], parts[2]))
        if parts[0] == "definition" and len(parts) == 2:
            return article.definition_boxes[int(parts[1])].definition
        if parts[0] == "related_topic" and len(parts) == 2:
            return article.related_topics[int(parts[1])].angle
    except (IndexError, ValueError, AttributeError):
        return None
    return None


def _set_text(article: ArticleSchema, section_id: str, value: str) -> None:
    parts = section_id.split(":")
    if section_id == "intro":
        article.excerpt = value
    elif section_id == "research_context":
        article.research_context = value
    elif section_id == "limitations_and_safety":
        article.limitations_and_safety = value
    elif parts[0] == "section" and len(parts) == 2:
        article.sections[int(parts[1])].content_markdown = value
    elif parts[0] == "subsection" and len(parts) == 3:
        article.sections[int(parts[1])].subsections[int(parts[2])].content_markdown = value
    elif parts[0] == "faq" and len(parts) == 2:
        article.faq[int(parts[1])].answer = value
    elif parts[0] == "callout" and len(parts) == 2:
        article.callout_boxes[int(parts[1])].message = value
    elif parts[0] == "caution" and len(parts) == 2:
        article.caution_boxes[int(parts[1])].message = value
    elif parts[0] == "research_insight" and len(parts) == 3:
        setattr(article.research_insights[int(parts[1])], parts[2], value)
    elif parts[0] == "study_card" and len(parts) == 3:
        setattr(article.study_cards[int(parts[1])], parts[2], value)
    elif parts[0] == "definition" and len(parts) == 2:
        article.definition_boxes[int(parts[1])].definition = value
    elif parts[0] == "related_topic" and len(parts) == 2:
        article.related_topics[int(parts[1])].angle = value


def _edits_from_payload(payload: dict[str, Any]) -> list[NarrativeEdit]:
    raw = payload.get("edits") if isinstance(payload.get("edits"), list) else []
    edits = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        section_id = str(item.get("section_id") or "").strip()
        original = str(item.get("original_text") or "")
        replacement = str(item.get("replacement_text") or "")
        if not section_id or not original.strip() or not replacement.strip():
            continue
        edits.append(
            NarrativeEdit(
                section_id=section_id,
                original_text=original,
                replacement_text=replacement,
                reason=str(item.get("reason") or ""),
            )
        )
    return edits[:20]


def _payload_from_generated(generated: GeneratedContent) -> dict[str, Any]:
    if isinstance(generated.content_json, dict):
        return generated.content_json
    text = str(generated.content_text or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _edit_record(edit: NarrativeEdit, *, status: str, reason: str) -> dict[str, Any]:
    return {
        "section_id": edit.section_id,
        "status": status,
        "reason": reason,
        "original_preview": edit.original_text[:220],
        "replacement_preview": edit.replacement_text[:220],
    }


def _article_context(article: ArticleSchema, request_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": article.title,
        "primary_keyword": article.primary_keyword,
        "product_name": request_data.get("product_name", ""),
        "outline": article_outline(article),
        "tone": "Professional, calm, human-edited, precise, and non-hype.",
    }


def _repeated_section_openings(article: ArticleSchema) -> list[dict[str, Any]]:
    openings = []
    for index, section in enumerate(article.sections):
        sentences = _sentences(section.content_markdown)
        if not sentences:
            continue
        openings.append((" ".join(_words(sentences[0])[:4]), section.heading or f"section:{index}"))
    return _repeated_patterns(openings, "opening")


def _repeated_section_closings(article: ArticleSchema) -> list[dict[str, Any]]:
    closings = []
    for index, section in enumerate(article.sections):
        sentences = _sentences(section.content_markdown)
        if not sentences:
            continue
        closings.append((" ".join(_words(sentences[-1])[:5]), section.heading or f"section:{index}"))
    return _repeated_patterns(closings, "closing")


def _repeated_patterns(items: list[tuple[str, str]], key: str) -> list[dict[str, Any]]:
    counts = Counter(pattern for pattern, _ in items if pattern)
    repeated = []
    for pattern, count in counts.items():
        if count <= 1:
            continue
        repeated.append({key: pattern, "count": count, "headings": [heading for item, heading in items if item == pattern]})
    return repeated


def _phrase_counts(value: str, phrases: tuple[str, ...], threshold: int) -> list[dict[str, Any]]:
    lower = _style_text(value).lower()
    found = []
    for phrase in phrases:
        count = len(re.findall(re.escape(phrase), lower, flags=re.IGNORECASE))
        if count >= threshold:
            found.append({"phrase": phrase, "count": count})
    return sorted(found, key=lambda item: item["count"], reverse=True)


def _similar_paragraph_lengths(value: str) -> list[dict[str, Any]]:
    paragraphs = [paragraph for paragraph in re.split(r"\n{2,}", value) if _word_count(paragraph) >= 20]
    lengths = [_word_count(paragraph) for paragraph in paragraphs]
    if len(lengths) < 4:
        return []
    buckets = Counter((length // 10) * 10 for length in lengths)
    repeated = [{"word_count_bucket": bucket, "count": count} for bucket, count in buckets.items() if count >= 3]
    if pstdev(lengths) <= 8:
        repeated.append({"word_count_bucket": "low_variance", "count": len(lengths)})
    return repeated


def _symmetrical_bullet_lists(value: str) -> list[dict[str, Any]]:
    lists = []
    current = []
    for line in value.splitlines():
        if line.strip().startswith(("-", "*")):
            current.append(line)
        elif current:
            lists.append(current)
            current = []
    if current:
        lists.append(current)
    symmetrical = []
    for index, items in enumerate(lists):
        if len(items) < 4:
            continue
        lengths = [_word_count(item) for item in items]
        if lengths and pstdev(lengths) <= 3:
            symmetrical.append({"list_index": index, "item_count": len(items), "average_words": round(sum(lengths) / len(lengths), 1)})
    return symmetrical


def _repeated_phrases(value: str) -> list[dict[str, Any]]:
    tokens = [token.lower() for token in re.findall(r"\b[a-z][a-z0-9'-]+\b", _style_text(value))]
    phrases = []
    for size in (3, 4):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrase = " ".join(tokens[index : index + size])
            if len(set(phrase.split())) > 1:
                phrases.append(phrase)
    counts = Counter(phrases)
    return [{"phrase": phrase, "count": count} for phrase, count in counts.most_common(12) if count >= 4]


def _sentences(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", value) if item.strip()]


def _words(value: str) -> list[str]:
    return re.findall(r"\b[a-z][a-z'-]*\b", value.lower())


def _style_text(value: str) -> str:
    without_links = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    without_urls = re.sub(r"https?://\S+", " ", without_links)
    return re.sub(r"\s+", " ", without_urls).strip()


def _word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value or ""))


def _markdown_links(value: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\([^)]+\)", value or "")


def _severity(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "minimal"
