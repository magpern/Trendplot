import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.article_schema import ArticleSchema, article_outline, article_to_markdown, normalize_article
from app.prompts import render_prompt
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask
from app.review.ai_pattern_detector import AI_AUTHORITY_PHRASES, AIPatternDetector
from app.review.article_repair import sanitize_article_safety
from app.review.humanizer import cleanup_text


RewriteMode = Literal["light", "editorial", "deep_editorial"]
RewriteStrength = Literal["light_cleanup", "editorial_rewrite", "deep_editorial_rewrite"]

FORBIDDEN_CLAIM_PATTERNS = (
    r"\brecommended dose\b",
    r"\bdosage\b",
    r"\bhuman dosing\b",
    r"\badminister(?:ed|ing|s)?\b",
    r"\binject(?:ed|ion|ing|s)?\b",
    r"\bpatients should\b",
    r"\bclinical use\b",
    r"\bhuman use\b",
    r"\bhuman consumption\b",
    r"\btreats\b",
    r"\bcures?\b",
    r"\bfor treating\b",
    r"\bsafe for human use\b",
)

SOURCE_DEPENDENT_STORAGE_NOTE = (
    "Storage and handling requirements can vary by formulation, batch, and supplier documentation. "
    "Researchers should refer to the product label, Certificate of Analysis, and supplied handling instructions."
)

SECTION_MIN_WORDS = 18


@dataclass(slots=True)
class EditorialRewriteSection:
    section_id: str
    section_type: str
    heading: str
    parent_heading: str
    raw_text: str
    context_summary: str
    safety_context: str
    related_entities: list[str]
    rewrite_priority: int
    rewrite_mode: RewriteMode

    def as_prompt_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_type": self.section_type,
            "heading": self.heading,
            "parent_heading": self.parent_heading,
            "raw_text": self.raw_text,
            "context_summary": self.context_summary,
            "safety_context": self.safety_context,
            "related_entities": self.related_entities,
            "rewrite_priority": self.rewrite_priority,
            "rewrite_mode": self.rewrite_mode,
        }


@dataclass(slots=True)
class EditorialRewriteAttempt:
    section_id: str
    attempt_number: int
    rewrite_mode: RewriteMode
    prompt: str
    status: str
    validation_errors: list[str] = field(default_factory=list)
    generated: GeneratedContent | None = None
    word_count_before: int = 0
    word_count_after: int = 0

    def as_dict(self, include_prompt: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "section_id": self.section_id,
            "attempt_number": self.attempt_number,
            "rewrite_mode": self.rewrite_mode,
            "status": self.status,
            "validation_errors": self.validation_errors,
            "word_count_before": self.word_count_before,
            "word_count_after": self.word_count_after,
        }
        if self.generated is not None:
            payload["model"] = self.generated.model
            payload["provider"] = self.generated.provider
            payload["usage"] = {
                "token_input": self.generated.usage.token_input if self.generated.usage else None,
                "token_output": self.generated.usage.token_output if self.generated.usage else None,
                "estimated_cost": self.generated.usage.estimated_cost if self.generated.usage else None,
            }
        if include_prompt:
            payload["prompt"] = self.prompt
        return payload


@dataclass(slots=True)
class EditorialRewriteRequest:
    article: ArticleSchema
    request_data: dict[str, Any]
    required_disclaimer: str
    target_min_word_count: int
    vertical_profile: dict[str, Any] | None = None
    rewrite_strength: RewriteStrength = "editorial_rewrite"
    redundancy_report: dict[str, Any] | None = None


@dataclass(slots=True)
class EditorialRewriteResult:
    article: ArticleSchema
    prompt: str
    summary: dict[str, Any]
    ai_pattern_report: dict[str, Any]
    rewritten_sections: list[dict[str, Any]]
    reverted_sections: list[dict[str, Any]]
    rewrite_attempts: list[dict[str, Any]]
    humanization_quality_report: dict[str, Any]
    generated: GeneratedContent | None = None
    generations: list[GeneratedContent] = field(default_factory=list)
    prompt_records: list[EditorialRewriteAttempt] = field(default_factory=list)


class EditorialRewriter:
    async def humanize(
        self,
        content_provider: Any,
        article: ArticleSchema,
        request_data: dict[str, Any],
        required_disclaimer: str,
        target_min_word_count: int,
        vertical_profile: dict[str, Any] | None = None,
        rewrite_strength: RewriteStrength = "editorial_rewrite",
        redundancy_report: dict[str, Any] | None = None,
    ) -> EditorialRewriteResult:
        return await self.rewrite(
            content_provider,
            EditorialRewriteRequest(
                article=article,
                request_data=request_data,
                required_disclaimer=required_disclaimer,
                target_min_word_count=target_min_word_count,
                vertical_profile=vertical_profile or {},
                rewrite_strength=rewrite_strength,
                redundancy_report=redundancy_report or {},
            ),
        )

    async def rewrite(self, content_provider: Any, request: EditorialRewriteRequest) -> EditorialRewriteResult:
        detector = AIPatternDetector()
        pattern_report = detector.analyze(request.article, required_disclaimer=request.required_disclaimer).as_dict()
        sections = extract_editorial_rewrite_sections(request.article, request, pattern_report)
        article = request.article.model_copy(deep=True)
        attempts: list[EditorialRewriteAttempt] = []
        rewritten_sections: list[dict[str, Any]] = []
        reverted_sections: list[dict[str, Any]] = []
        generations: list[GeneratedContent] = []
        article_context = _article_context(request.article, request, pattern_report)

        for index, section in enumerate(sections):
            neighbors = _neighboring_section_summaries(sections, index)
            rewritten_text = ""
            validation_errors: list[str] = []
            status = "reverted"
            for attempt_number in (1, 2):
                mode = section.rewrite_mode if attempt_number == 1 else "light"
                prompt = build_editorial_section_rewrite_prompt(
                    section=section,
                    article_context=article_context,
                    neighboring_sections=neighbors,
                    vertical_profile=request.vertical_profile or {},
                    required_disclaimer=request.required_disclaimer,
                    rewrite_mode=mode,
                    retry_errors=validation_errors,
                )
                attempt = EditorialRewriteAttempt(
                    section_id=section.section_id,
                    attempt_number=attempt_number,
                    rewrite_mode=mode,
                    prompt=prompt,
                    status="requested",
                    word_count_before=_word_count(section.raw_text),
                )
                try:
                    generated = await content_provider.generate_article(prompt, task_type=ModelTask.HUMANIZATION)
                except Exception as exc:
                    attempt.status = "model_error"
                    attempt.validation_errors = [str(exc)]
                    attempts.append(attempt)
                    validation_errors = attempt.validation_errors
                    continue

                attempt.generated = generated
                generations.append(generated)
                candidate = _candidate_text(generated)
                candidate = cleanup_text(candidate)
                validation_errors = validate_rewritten_section(
                    original_text=section.raw_text,
                    rewritten_text=candidate,
                    required_disclaimer=request.required_disclaimer,
                    is_safety_section=section.section_id == "limitations_and_safety" or "safety" in section.heading.lower(),
                )
                attempt.word_count_after = _word_count(candidate)
                attempt.status = "accepted" if not validation_errors else "validation_failed"
                attempt.validation_errors = validation_errors
                attempts.append(attempt)
                if not validation_errors:
                    rewritten_text = candidate
                    status = "rewritten"
                    break

            if status == "rewritten" and rewritten_text:
                _apply_rewritten_text(article, section.section_id, rewritten_text)
                rewritten_sections.append(
                    {
                        "section_id": section.section_id,
                        "section_type": section.section_type,
                        "heading": section.heading,
                        "rewrite_mode": section.rewrite_mode,
                        "rewrite_priority": section.rewrite_priority,
                        "word_count_before": _word_count(section.raw_text),
                        "word_count_after": _word_count(rewritten_text),
                    }
                )
            else:
                reverted_sections.append(
                    {
                        "section_id": section.section_id,
                        "section_type": section.section_type,
                        "heading": section.heading,
                        "rewrite_mode": section.rewrite_mode,
                        "validation_errors": validation_errors,
                    }
                )

        cleaned = sanitize_article_safety(article.model_dump())
        cleaned = _dedupe_repeated_section_paragraphs(cleaned)
        cleaned = _consolidate_required_disclaimer(cleaned, request.required_disclaimer)
        cleaned = _preserve_protected_article_fields(request.article.model_dump(), cleaned)
        cleaned = _ensure_required_disclaimer(cleaned, request.required_disclaimer)
        final_article = normalize_article(
            cleaned,
            defaults={
                "title": str(request.request_data.get("title") or request.article.title),
                "target_keyword": str(request.request_data.get("target_keyword") or request.article.primary_keyword),
                "product_name": str(request.request_data.get("product_name") or ""),
                "product_url": str(request.request_data.get("product_url") or ""),
            },
        )
        final_pattern_report = detector.analyze(final_article, required_disclaimer=request.required_disclaimer).as_dict()
        repeated_removed = _removed_repeated_phrases(pattern_report, final_pattern_report)
        quality_report = {
            "ai_pattern_score_before": pattern_report.get("score", 0),
            "ai_pattern_score_after": final_pattern_report.get("score", 0),
            "remaining_ai_pattern_warnings": final_pattern_report.get("warnings", []),
            "sections_rewritten": len(rewritten_sections),
            "sections_reverted": len(reverted_sections),
            "repeated_phrases_removed": repeated_removed,
            "word_count_before": _word_count(article_to_markdown(request.article)),
            "word_count_after": _word_count(article_to_markdown(final_article)),
            "schema_preserved": set(request.article.model_dump().keys()) == set(final_article.model_dump().keys()),
        }
        summary = {
            "attempted": True,
            "mode": "section_based_editorial_rewrite",
            "rewrite_strength_requested": request.rewrite_strength,
            "rewrite_strength_used": _strength_used(rewritten_sections),
            "ai_pattern_score_before": pattern_report.get("score", 0),
            "ai_pattern_score_after": final_pattern_report.get("score", 0),
            "sections_considered": len(sections),
            "sections_rewritten": len(rewritten_sections),
            "sections_reverted": len(reverted_sections),
            "repeated_phrases_removed": repeated_removed,
            "safety_preserved": request.required_disclaimer in json.dumps(final_article.model_dump()) if request.required_disclaimer else True,
            "warnings": final_pattern_report.get("warnings", []),
        }
        return EditorialRewriteResult(
            article=final_article,
            prompt="Section-based editorial rewrite. See rewrite_attempts for per-section prompts.",
            summary=summary,
            ai_pattern_report=pattern_report,
            rewritten_sections=rewritten_sections,
            reverted_sections=reverted_sections,
            rewrite_attempts=[attempt.as_dict() for attempt in attempts],
            humanization_quality_report=quality_report,
            generated=generations[-1] if generations else None,
            generations=generations,
            prompt_records=attempts,
        )


def extract_editorial_rewrite_sections(
    article: ArticleSchema,
    request: EditorialRewriteRequest,
    pattern_report: dict[str, Any],
) -> list[EditorialRewriteSection]:
    section_scores = {
        item.get("section_id"): int(item.get("score") or 0)
        for item in pattern_report.get("section_scores", [])
        if isinstance(item, dict)
    }
    entities = _entity_glossary(article, request.request_data)
    sections: list[EditorialRewriteSection] = []

    def add(
        *,
        section_id: str,
        section_type: str,
        heading: str,
        parent_heading: str = "",
        raw_text: str,
        safety_context: str = "",
    ) -> None:
        text = str(raw_text or "").strip()
        if _word_count(text) < SECTION_MIN_WORDS:
            return
        priority = _rewrite_priority(section_id, section_type, text, section_scores, request)
        sections.append(
            EditorialRewriteSection(
                section_id=section_id,
                section_type=section_type,
                heading=heading,
                parent_heading=parent_heading,
                raw_text=text,
                context_summary=_summarize_text(text),
                safety_context=safety_context or _safety_context_for_text(text, request.required_disclaimer),
                related_entities=[entity for entity in entities if entity.lower() in text.lower()][:12],
                rewrite_priority=priority,
                rewrite_mode=_rewrite_mode(priority, request.rewrite_strength),
            )
        )

    add(section_id="intro", section_type="intro", heading="Intro", raw_text=article.excerpt)
    add(section_id="research_context", section_type="research_context", heading="Research Context", raw_text=article.research_context)
    for index, section in enumerate(article.sections):
        add(section_id=f"section:{index}", section_type="section_body", heading=section.heading, raw_text=section.content_markdown)
        for sub_index, subsection in enumerate(section.subsections):
            add(
                section_id=f"subsection:{index}:{sub_index}",
                section_type="subsection_body",
                heading=subsection.heading,
                parent_heading=section.heading,
                raw_text=subsection.content_markdown,
            )
    for index, item in enumerate(article.faq):
        add(section_id=f"faq:{index}", section_type="faq_answer", heading=item.question, raw_text=item.answer)
    for index, item in enumerate(article.callout_boxes):
        add(section_id=f"callout:{index}", section_type="callout_message", heading=item.title, raw_text=item.message)
    for index, item in enumerate(article.caution_boxes):
        add(section_id=f"caution:{index}", section_type="caution_message", heading=item.title, raw_text=item.message)
    for index, item in enumerate(article.research_insights):
        add(section_id=f"research_insight:{index}:insight", section_type="research_insight", heading=item.title, raw_text=item.insight)
        add(
            section_id=f"research_insight:{index}:limitation",
            section_type="research_limitation",
            heading=item.title,
            raw_text=item.limitation,
        )
    for index, item in enumerate(article.study_cards):
        add(
            section_id=f"study_card:{index}:observed_finding",
            section_type="study_card_observed_finding",
            heading=item.title,
            raw_text=item.observed_finding,
        )
        add(section_id=f"study_card:{index}:limitation", section_type="study_card_limitation", heading=item.title, raw_text=item.limitation)
        add(
            section_id=f"study_card:{index}:verification_needed",
            section_type="study_card_verification",
            heading=item.title,
            raw_text=item.verification_needed,
        )
    for index, item in enumerate(article.definition_boxes):
        add(section_id=f"definition:{index}", section_type="definition", heading=item.term, raw_text=item.definition)
    for index, item in enumerate(article.related_topics):
        add(section_id=f"related_topic:{index}", section_type="related_topic_summary", heading=item.title, raw_text=item.angle)
    add(
        section_id="limitations_and_safety",
        section_type="limitations_and_safety",
        heading="Limitations and Safety Notes",
        raw_text=article.limitations_and_safety,
        safety_context="Preserve required disclaimer exactly and avoid adding operational instructions.",
    )
    return sorted(sections, key=lambda item: item.rewrite_priority, reverse=True)


def build_editorial_section_rewrite_prompt(
    *,
    section: EditorialRewriteSection,
    article_context: dict[str, Any],
    neighboring_sections: list[dict[str, str]],
    vertical_profile: dict[str, Any],
    required_disclaimer: str,
    rewrite_mode: RewriteMode,
    retry_errors: list[str],
) -> str:
    return render_prompt(
        "editorial_section_rewrite",
        {
            "article_context_json": json.dumps(article_context, ensure_ascii=False, indent=2),
            "section_json": json.dumps({**section.as_prompt_dict(), "rewrite_mode": rewrite_mode}, ensure_ascii=False, indent=2),
            "neighboring_sections_json": json.dumps(neighboring_sections, ensure_ascii=False, indent=2),
            "vertical_profile_json": json.dumps(vertical_profile or {}, ensure_ascii=False, indent=2),
            "required_disclaimer": required_disclaimer,
            "safety_constraints_json": json.dumps(_safety_constraints(), ensure_ascii=False, indent=2),
            "forbidden_claims_json": json.dumps(list(FORBIDDEN_CLAIM_PATTERNS), ensure_ascii=False, indent=2),
            "ai_phrases": ", ".join(AI_AUTHORITY_PHRASES),
            "rewrite_mode": rewrite_mode or "editorial",
            "retry_errors_json": json.dumps(retry_errors, ensure_ascii=False, indent=2),
        },
    )


def validate_rewritten_section(
    *,
    original_text: str,
    rewritten_text: str,
    required_disclaimer: str,
    is_safety_section: bool,
) -> list[str]:
    errors: list[str] = []
    original = str(original_text or "")
    rewritten = str(rewritten_text or "").strip()
    if not rewritten:
        return ["rewritten section is empty"]
    original_words = _word_count(original)
    rewritten_words = _word_count(rewritten)
    if original_words >= 80 and rewritten_words < max(45, int(original_words * 0.55)):
        errors.append("rewritten section became too short")
    if original_words < 80 and rewritten_words < max(SECTION_MIN_WORDS, int(original_words * 0.5)):
        errors.append("rewritten section lost too much substance")
    missing_urls = [url for url in _urls(original) if url not in rewritten]
    if missing_urls:
        errors.append(f"URLs removed: {', '.join(missing_urls[:3])}")
    if required_disclaimer and required_disclaimer in original and required_disclaimer not in rewritten:
        errors.append("required disclaimer was not preserved exactly")
    if is_safety_section and required_disclaimer and required_disclaimer not in rewritten:
        errors.append("safety section is missing required disclaimer")
    unsafe = _unsafe_claims_added(original, rewritten)
    if unsafe:
        errors.append(f"unsafe claim language added: {', '.join(unsafe[:5])}")
    if _unsafe_storage_added(original, rewritten):
        errors.append("unsafe or overly specific storage/handling language was added")
    return errors


def _candidate_text(generated: GeneratedContent) -> str:
    payload = generated.content_json or {}
    for key in ("rewritten_text", "content_markdown", "answer", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return str(generated.content_text or "").strip()


def _apply_rewritten_text(article: ArticleSchema, section_id: str, rewritten_text: str) -> None:
    parts = section_id.split(":")
    if section_id == "intro":
        article.excerpt = rewritten_text
    elif section_id == "research_context":
        article.research_context = rewritten_text
    elif section_id == "limitations_and_safety":
        article.limitations_and_safety = rewritten_text
    elif parts[0] == "section" and len(parts) == 2:
        article.sections[int(parts[1])].content_markdown = rewritten_text
    elif parts[0] == "subsection" and len(parts) == 3:
        article.sections[int(parts[1])].subsections[int(parts[2])].content_markdown = rewritten_text
    elif parts[0] == "faq" and len(parts) == 2:
        article.faq[int(parts[1])].answer = rewritten_text
    elif parts[0] == "callout" and len(parts) == 2:
        article.callout_boxes[int(parts[1])].message = rewritten_text
    elif parts[0] == "caution" and len(parts) == 2:
        article.caution_boxes[int(parts[1])].message = rewritten_text
    elif parts[0] == "research_insight" and len(parts) == 3:
        setattr(article.research_insights[int(parts[1])], parts[2], rewritten_text)
    elif parts[0] == "study_card" and len(parts) == 3:
        setattr(article.study_cards[int(parts[1])], parts[2], rewritten_text)
    elif parts[0] == "definition" and len(parts) == 2:
        article.definition_boxes[int(parts[1])].definition = rewritten_text
    elif parts[0] == "related_topic" and len(parts) == 2:
        article.related_topics[int(parts[1])].angle = rewritten_text


def _preserve_protected_article_fields(original: dict[str, Any], rewritten: dict[str, Any]) -> dict[str, Any]:
    protected = (
        "title",
        "slug",
        "meta_title",
        "meta_description",
        "primary_keyword",
        "secondary_keywords",
        "table_of_contents",
        "internal_links",
        "references_to_verify",
        "related_video",
        "social_posts",
        "backlink_plan",
        "comparison_tables",
        "research_metadata_panel",
        "inline_citation_markers",
    )
    merged = dict(rewritten)
    for key in protected:
        if key in original:
            merged[key] = original[key]
    return merged


def _ensure_required_disclaimer(article_json: dict[str, Any], required_disclaimer: str) -> dict[str, Any]:
    if not required_disclaimer:
        return article_json
    text = json.dumps(article_json, ensure_ascii=False)
    if required_disclaimer in text:
        return article_json
    limitations = str(article_json.get("limitations_and_safety") or "")
    article_json["limitations_and_safety"] = f"{limitations.rstrip()}\n\n{required_disclaimer}".strip()
    return article_json


def _consolidate_required_disclaimer(article_json: dict[str, Any], required_disclaimer: str) -> dict[str, Any]:
    if not required_disclaimer:
        return article_json

    def visit(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str):
            return value.replace(required_disclaimer, "").strip()
        return value

    cleaned = visit(article_json)
    limitations = str(cleaned.get("limitations_and_safety") or "")
    cleaned["limitations_and_safety"] = f"{limitations.rstrip()}\n\n{required_disclaimer}".strip()
    return cleaned


def _dedupe_repeated_section_paragraphs(article_json: dict[str, Any]) -> dict[str, Any]:
    data = dict(article_json or {})
    sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    seen: set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            continue
        section["content_markdown"] = _dedupe_text_paragraphs(str(section.get("content_markdown") or ""), seen)
        subsections = section.get("subsections") if isinstance(section.get("subsections"), list) else []
        for subsection in subsections:
            if isinstance(subsection, dict):
                subsection["content_markdown"] = _dedupe_text_paragraphs(str(subsection.get("content_markdown") or ""), seen)
    return data


def _dedupe_text_paragraphs(value: str, seen: set[str]) -> str:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", value) if paragraph.strip()]
    kept = []
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", " ", paragraph).strip().lower()
        if _word_count(paragraph) >= 12 and normalized in seen:
            continue
        if _word_count(paragraph) >= 12:
            seen.add(normalized)
        kept.append(paragraph)
    return "\n\n".join(kept) if kept else value


def _article_context(
    article: ArticleSchema,
    request: EditorialRewriteRequest,
    pattern_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": article.title,
        "primary_keyword": article.primary_keyword,
        "product_name": request.request_data.get("product_name", ""),
        "audience": request.request_data.get("audience", "research-informed readers"),
        "article_summary": _summarize_text(article_to_markdown(article), max_words=90),
        "outline": article_outline(article),
        "tone_guidance": "Calm, editorial, precise, non-hype, and less SEO-templated.",
        "entity_glossary": _entity_glossary(article, request.request_data),
        "writing_style_summary": "Vary sentence length, paragraph shape, and transitions while preserving meaning.",
        "ai_pattern_score": pattern_report.get("score"),
        "ai_pattern_warnings": pattern_report.get("warnings", []),
        "rewrite_strength_requested": request.rewrite_strength,
    }


def _neighboring_section_summaries(
    sections: list[EditorialRewriteSection],
    index: int,
) -> list[dict[str, str]]:
    neighbors = []
    for offset in (-1, 1):
        neighbor_index = index + offset
        if 0 <= neighbor_index < len(sections):
            neighbor = sections[neighbor_index]
            neighbors.append(
                {
                    "section_id": neighbor.section_id,
                    "heading": neighbor.heading,
                    "summary": neighbor.context_summary,
                }
            )
    return neighbors


def _rewrite_priority(
    section_id: str,
    section_type: str,
    text: str,
    section_scores: dict[str, int],
    request: EditorialRewriteRequest,
) -> int:
    score = section_scores.get(section_id, 0)
    if request.rewrite_strength == "deep_editorial_rewrite":
        score += 25
    elif request.rewrite_strength == "light_cleanup":
        score -= 20
    if section_type in {"section_body", "subsection_body", "intro", "conclusion"}:
        score += 15
    if _word_count(text) >= 120:
        score += 10
    repeated = request.redundancy_report or {}
    repeated_phrases = repeated.get("repeated_phrases") if isinstance(repeated.get("repeated_phrases"), list) else []
    if any(str(item.get("phrase", "")).lower() in text.lower() for item in repeated_phrases if isinstance(item, dict)):
        score += 15
    return max(0, min(100, score))


def _rewrite_mode(priority: int, strength: RewriteStrength) -> RewriteMode:
    if strength == "light_cleanup":
        return "light"
    if strength == "deep_editorial_rewrite" or priority >= 65:
        return "deep_editorial"
    if priority <= 20:
        return "light"
    return "editorial"


def _safety_context_for_text(text: str, required_disclaimer: str) -> str:
    notes = []
    lower = text.lower()
    if required_disclaimer and required_disclaimer in text:
        notes.append("The required disclaimer appears here and must be preserved exactly.")
    if any(term in lower for term in ("storage", "handling", "reconstitution", "aliquot", "dose", "human")):
        notes.append("Avoid adding dosing, human-use, clinical, or overly specific storage/handling instructions.")
    return " ".join(notes)


def _safety_constraints() -> list[str]:
    return [
        "Do not add dosing, administration, injection, clinical-use, treatment, diagnostic, or human-use guidance.",
        "Do not add new scientific findings, citations, PubMed IDs, DOIs, or product documentation claims.",
        "Preserve URLs, markdown links, and required disclaimer text exactly.",
        "If storage or handling is discussed, frame it as source-dependent supplier documentation.",
        SOURCE_DEPENDENT_STORAGE_NOTE,
    ]


def _unsafe_claims_added(original: str, rewritten: str) -> list[str]:
    original_lower = original.lower()
    rewritten_lower = rewritten.lower()
    added = []
    for pattern in FORBIDDEN_CLAIM_PATTERNS:
        for match in re.finditer(pattern, rewritten_lower, flags=re.IGNORECASE):
            text = match.group(0)
            if text in original_lower or _has_safe_negation(rewritten_lower, match.start()):
                continue
            added.append(text)
    return sorted(set(added))


def _unsafe_storage_added(original: str, rewritten: str) -> bool:
    if "supplier documentation" in rewritten.lower() or "product label" in rewritten.lower():
        return False
    pattern = re.compile(r"\b(?:store|stored|storage|reconstitut|aliquot|freez)\w*\b[^.\n]{0,100}\b-?\d{1,3}\s*(?:°|deg|degrees?)?\s*c\b", re.I)
    original_hits = {match.group(0).lower() for match in pattern.finditer(original)}
    return any(match.group(0).lower() not in original_hits for match in pattern.finditer(rewritten))


def _has_safe_negation(text: str, start: int) -> bool:
    window = text[max(0, start - 28) : start]
    return any(prefix in window for prefix in ("not ", "no ", "do not ", "avoid ", "without ", "not intended for "))


def _entity_glossary(article: ArticleSchema, request_data: dict[str, Any]) -> list[str]:
    candidates = [
        article.title,
        article.primary_keyword,
        str(request_data.get("product_name") or ""),
        str(request_data.get("target_keyword") or ""),
        *article.secondary_keywords,
    ]
    text = " ".join([article_to_markdown(article), *candidates])
    candidates.extend(re.findall(r"\b[A-Z][A-Za-z0-9+-]{2,}(?:\s+[A-Z][A-Za-z0-9+-]{2,}){0,3}\b", text))
    seen: set[str] = set()
    entities = []
    for candidate in candidates:
        cleaned = re.sub(r"\s+", " ", str(candidate or "")).strip()
        key = cleaned.lower()
        if not cleaned or key in seen or len(cleaned) > 80:
            continue
        seen.add(key)
        entities.append(cleaned)
    return entities[:40]


def _summarize_text(value: str, max_words: int = 45) -> str:
    words = re.findall(r"\S+", value)
    if len(words) <= max_words:
        return value.strip()
    return " ".join(words[:max_words]).strip() + "..."


def _urls(value: str) -> list[str]:
    return re.findall(r"https?://[^\s)\]\"']+", value)


def _word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value or ""))


def _removed_repeated_phrases(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    after_phrases = {
        str(item.get("phrase", "")).lower()
        for item in after.get("repeated_phrases", [])
        if isinstance(item, dict)
    }
    return [
        str(item.get("phrase"))
        for item in before.get("repeated_phrases", [])
        if isinstance(item, dict) and str(item.get("phrase", "")).lower() not in after_phrases
    ]


def _strength_used(rewritten_sections: list[dict[str, Any]]) -> str:
    modes = {str(item.get("rewrite_mode")) for item in rewritten_sections}
    if "deep_editorial" in modes:
        return "deep_editorial_rewrite"
    if "editorial" in modes:
        return "editorial_rewrite"
    return "light_cleanup"
