import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.article_schema import ArticleSchema, ArticleSection, article_to_markdown
from app.rendering.render_surface import ArticleRenderSurface
from app.prompts import render_prompt
from app.providers.base import GeneratedContent
from app.providers.model_router import ModelTask


KEY_SECTION_HINTS = (
    "what is",
    "mechanism",
    "pathway",
    "how it works",
    "research context",
    "research applications",
    "applications",
    "limitations",
    "safety",
    "handling",
    "storage",
    "documentation",
    "terminology",
)


BIOMEDICAL_TOPICS = (
    "mechanism of action or signaling pathway",
    "research context and study models",
    "limitations and safety boundaries",
    "handling, storage, and documentation considerations",
    "terminology and related concepts",
)


@dataclass(slots=True)
class SectionExpansionRequest:
    article: ArticleSchema
    request_data: dict[str, Any]
    quality_result: dict[str, Any]
    target_article_word_count: int
    target_section_min_words: int
    max_passes: int
    max_sections_per_pass: int
    is_biomedical: bool
    required_disclaimer: str


@dataclass(slots=True)
class SectionExpansionPromptRecord:
    pass_number: int
    target_type: str
    target_index: int | None
    heading: str
    prompt: str
    generated: GeneratedContent | None = None


@dataclass(slots=True)
class SectionExpansionResult:
    article: ArticleSchema
    summary: dict[str, Any]
    prompt_records: list[SectionExpansionPromptRecord] = field(default_factory=list)


@dataclass(slots=True)
class ExpansionCandidate:
    target_type: str
    heading: str
    content: str
    index: int | None
    word_count: int
    priority: int


class SectionExpansionService:
    async def expand(
        self,
        content_provider: Any,
        request: SectionExpansionRequest,
    ) -> SectionExpansionResult:
        article = request.article.model_copy(deep=True)
        prompt_records: list[SectionExpansionPromptRecord] = []
        word_count_before = count_words(article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE))
        expanded_sections: list[dict[str, Any]] = []
        stopped_reason = "article already meets target word count"

        if word_count_before >= request.target_article_word_count and not _has_shallow_sections(
            article,
            request.target_section_min_words,
        ):
            return SectionExpansionResult(
                article=article,
                summary={
                    "attempted": False,
                    "pass_count": 0,
                    "word_count_before": word_count_before,
                    "word_count_after": word_count_before,
                    "target_word_count": request.target_article_word_count,
                    "remaining_deficit": 0,
                    "expanded_sections": [],
                    "stopped_reason": stopped_reason,
                },
                prompt_records=[],
            )

        for pass_number in range(1, max(0, request.max_passes) + 1):
            current_word_count = count_words(article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE))
            deficit = max(request.target_article_word_count - current_word_count, 0)
            candidates = _rank_candidates(article, request.target_section_min_words)
            if not candidates:
                stopped_reason = "no expandable sections remain"
                break
            if deficit <= 0 and not candidates:
                stopped_reason = "article meets target word count"
                break

            selected = candidates[: max(1, request.max_sections_per_pass)]
            recommended_words = _recommended_additional_words(
                deficit=deficit,
                selected_count=len(selected),
                target_section_min_words=request.target_section_min_words,
            )

            for candidate in selected:
                current_word_count = count_words(article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE))
                if (
                    current_word_count >= request.target_article_word_count
                    and candidate.word_count >= request.target_section_min_words
                ):
                    continue

                prompt = build_section_expansion_prompt(
                    request=request,
                    candidate=candidate,
                    pass_number=pass_number,
                    current_article_word_count=current_word_count,
                    recommended_additional_words=recommended_words,
                )
                record = SectionExpansionPromptRecord(
                    pass_number=pass_number,
                    target_type=candidate.target_type,
                    target_index=candidate.index,
                    heading=candidate.heading,
                    prompt=prompt,
                )
                try:
                    generated = await content_provider.generate_article(
                        prompt,
                        task_type=ModelTask.SECTION_EXPANSION,
                    )
                except Exception:
                    stopped_reason = "model/API failure during section expansion"
                    prompt_records.append(record)
                    return SectionExpansionResult(
                        article=article,
                        summary=_summary(
                            attempted=True,
                            pass_count=pass_number,
                            word_count_before=word_count_before,
                            article=article,
                            target_word_count=request.target_article_word_count,
                            expanded_sections=expanded_sections,
                            stopped_reason=stopped_reason,
                        ),
                        prompt_records=prompt_records,
                    )

                record.generated = generated
                prompt_records.append(record)
                payload = generated.content_json or {}
                expanded_content = str(
                    payload.get("expanded_content_markdown")
                    or payload.get("content_markdown")
                    or generated.content_text
                    or ""
                ).strip()
                if not expanded_content:
                    continue

                before_words = candidate.word_count
                _apply_expanded_content(article, candidate, expanded_content)
                after_words = count_words(expanded_content)
                expanded_sections.append(
                    {
                        "pass_number": pass_number,
                        "heading": candidate.heading,
                        "target_type": candidate.target_type,
                        "word_count_before": before_words,
                        "word_count_after": after_words,
                        "added_topics": _string_list(payload.get("added_topics")),
                    }
                )

            if count_words(article_to_markdown(article)) >= request.target_article_word_count:
                stopped_reason = "article meets target word count"
                break
            stopped_reason = "max expansion passes reached"

        return SectionExpansionResult(
            article=article,
            summary=_summary(
                attempted=True,
                pass_count=max((item["pass_number"] for item in expanded_sections), default=0),
                word_count_before=word_count_before,
                article=article,
                target_word_count=request.target_article_word_count,
                expanded_sections=expanded_sections,
                stopped_reason=stopped_reason,
            ),
            prompt_records=prompt_records,
        )


def build_section_expansion_prompt(
    request: SectionExpansionRequest,
    candidate: ExpansionCandidate,
    pass_number: int,
    current_article_word_count: int,
    recommended_additional_words: int,
) -> str:
    target_section_words = max(
        request.target_section_min_words,
        candidate.word_count + recommended_additional_words,
    )
    missing_topics = _missing_topics(candidate, request.is_biomedical)
    biomedical_rules = (
        f'- Keep RUO framing and preserve this exact disclaimer where relevant: "{request.required_disclaimer}"'
        if request.is_biomedical
        else "- Use cautious factual language and avoid unsupported claims."
    )

    return render_prompt(
        "section_expansion",
        {
            "article_title": request.article.title,
            "target_keyword": request.request_data.get("target_keyword", request.article.primary_keyword),
            "product_name": request.request_data.get("product_name", ""),
            "product_url": request.request_data.get("product_url", ""),
            "current_article_word_count": current_article_word_count,
            "target_article_word_count": request.target_article_word_count,
            "pass_number": pass_number,
            "section_heading": candidate.heading,
            "existing_section_content": candidate.content,
            "missing_topics_json": json.dumps(missing_topics, ensure_ascii=False, indent=2),
            "target_section_words": target_section_words,
            "biomedical_rules": biomedical_rules,
        },
    )


def count_words(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value))


def _rank_candidates(article: ArticleSchema, target_section_min_words: int) -> list[ExpansionCandidate]:
    candidates: list[ExpansionCandidate] = []
    if article.research_context:
        candidates.append(
            ExpansionCandidate(
                target_type="research_context",
                heading="Research Context",
                content=article.research_context,
                index=None,
                word_count=count_words(article.research_context),
                priority=_priority("Research Context"),
            )
        )
    for index, section in enumerate(article.sections):
        if not section.heading or not section.content_markdown:
            continue
        candidates.append(
            ExpansionCandidate(
                target_type="section",
                heading=section.heading,
                content=section.content_markdown,
                index=index,
                word_count=count_words(section.content_markdown),
                priority=_priority(section.heading),
            )
        )
    if article.limitations_and_safety:
        candidates.append(
            ExpansionCandidate(
                target_type="limitations_and_safety",
                heading="Limitations and Safety Notes",
                content=article.limitations_and_safety,
                index=None,
                word_count=count_words(article.limitations_and_safety),
                priority=_priority("Limitations and Safety Notes"),
            )
        )

    return sorted(
        candidates,
        key=lambda item: (
            item.word_count >= target_section_min_words,
            item.priority,
            item.word_count,
        ),
    )


def _priority(heading: str) -> int:
    lower_heading = heading.lower()
    for index, hint in enumerate(KEY_SECTION_HINTS):
        if hint in lower_heading:
            return index
    return len(KEY_SECTION_HINTS)


def _recommended_additional_words(deficit: int, selected_count: int, target_section_min_words: int) -> int:
    if selected_count <= 0:
        return target_section_min_words
    if deficit <= 0:
        return target_section_min_words
    return max(150, min(300, (deficit // selected_count) + 75))


def _missing_topics(candidate: ExpansionCandidate, is_biomedical: bool) -> list[str]:
    topics = []
    content = candidate.content.lower()
    if "study" not in content and "research" not in content:
        topics.append("research study context")
    if "limit" not in content and "safety" not in content:
        topics.append("limitations and safety boundaries")
    if "mechanism" in candidate.heading.lower() or "pathway" in candidate.heading.lower():
        topics.append("signaling pathway terminology")
    if is_biomedical:
        topics.extend(topic for topic in BIOMEDICAL_TOPICS if topic.split()[0] not in content)
    return list(dict.fromkeys(topics))


def _apply_expanded_content(article: ArticleSchema, candidate: ExpansionCandidate, expanded_content: str) -> None:
    if candidate.target_type == "research_context":
        article.research_context = expanded_content
    elif candidate.target_type == "limitations_and_safety":
        article.limitations_and_safety = expanded_content
    elif candidate.target_type == "section" and candidate.index is not None:
        article.sections[candidate.index] = ArticleSection(
            heading=candidate.heading,
            content_markdown=expanded_content,
        )


def _has_shallow_sections(article: ArticleSchema, target_section_min_words: int) -> bool:
    return any(candidate.word_count < target_section_min_words for candidate in _rank_candidates(article, target_section_min_words))


def _summary(
    attempted: bool,
    pass_count: int,
    word_count_before: int,
    article: ArticleSchema,
    target_word_count: int,
    expanded_sections: list[dict[str, Any]],
    stopped_reason: str,
) -> dict[str, Any]:
    word_count_after = count_words(article_to_markdown(article, surface=ArticleRenderSurface.PUBLISHABLE))
    return {
        "attempted": attempted,
        "pass_count": pass_count,
        "word_count_before": word_count_before,
        "word_count_after": word_count_after,
        "target_word_count": target_word_count,
        "remaining_deficit": max(target_word_count - word_count_after, 0),
        "expanded_sections": expanded_sections,
        "stopped_reason": stopped_reason,
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
