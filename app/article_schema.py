from typing import Any
import ast
import json
import re

from pydantic import BaseModel, Field

from app.rendering.render_surface import ArticleRenderSurface


class ArticleSection(BaseModel):
    heading: str = ""
    content_markdown: str = ""
    subsections: list["ArticleSubsection"] = Field(default_factory=list)


class ArticleSubsection(BaseModel):
    heading: str = ""
    content_markdown: str = ""


class FAQItem(BaseModel):
    question: str = ""
    answer: str = ""


class InternalLinkSuggestion(BaseModel):
    anchor_text: str = ""
    url: str = ""
    reason: str = ""


class ReferenceToVerify(BaseModel):
    title: str = ""
    search_query: str = ""
    reason: str = ""


class SocialPosts(BaseModel):
    x: str = ""
    threads: str = ""


class BacklinkPlanItem(BaseModel):
    target_type: str = ""
    angle: str = ""
    suggested_anchor: str = ""
    notes: str = ""


class CalloutBox(BaseModel):
    title: str = ""
    message: str = ""


class ResearchInsight(BaseModel):
    title: str = ""
    insight: str = ""
    limitation: str = ""


class StudyCard(BaseModel):
    title: str = ""
    source_label: str = ""
    model_or_context: str = ""
    observed_finding: str = ""
    limitation: str = ""
    verification_needed: str = ""


class DefinitionBox(BaseModel):
    term: str = ""
    definition: str = ""


class CautionBox(BaseModel):
    title: str = ""
    message: str = ""


class ComparisonTable(BaseModel):
    title: str = ""
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ResearchMetadataPanel(BaseModel):
    research_status: str = ""
    study_types: list[str] = Field(default_factory=list)
    human_use_status: str = ""
    ruo_status: str = ""
    confidence_notes: str = ""


class RelatedTopic(BaseModel):
    title: str = ""
    angle: str = ""
    suggested_url: str = ""


class InlineCitationMarker(BaseModel):
    marker: str = ""
    reference_title: str = ""
    context: str = ""


class EditorialArtifacts(BaseModel):
    references_to_verify: list[ReferenceToVerify] = Field(default_factory=list)
    study_cards: list[StudyCard] = Field(default_factory=list)
    research_insights: list[ResearchInsight] = Field(default_factory=list)
    research_metadata_panel: ResearchMetadataPanel | None = None
    backlink_plan: list[BacklinkPlanItem] = Field(default_factory=list)
    inline_citation_markers: list[InlineCitationMarker] = Field(default_factory=list)


class ArticleSchema(BaseModel):
    title: str = ""
    slug: str = ""
    excerpt: str = ""
    meta_title: str = ""
    meta_description: str = ""
    primary_keyword: str = ""
    secondary_keywords: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    table_of_contents: list[str] = Field(default_factory=list)
    sections: list[ArticleSection] = Field(default_factory=list)
    faq: list[FAQItem] = Field(default_factory=list)
    research_context: str = ""
    limitations_and_safety: str = ""
    internal_links: list[InternalLinkSuggestion] = Field(default_factory=list)
    references_to_verify: list[ReferenceToVerify] = Field(default_factory=list)
    related_video: dict[str, Any] | None = None
    social_posts: SocialPosts = Field(default_factory=SocialPosts)
    backlink_plan: list[BacklinkPlanItem] = Field(default_factory=list)
    callout_boxes: list[CalloutBox] = Field(default_factory=list)
    research_insights: list[ResearchInsight] = Field(default_factory=list)
    study_cards: list[StudyCard] = Field(default_factory=list)
    definition_boxes: list[DefinitionBox] = Field(default_factory=list)
    caution_boxes: list[CautionBox] = Field(default_factory=list)
    comparison_tables: list[ComparisonTable] = Field(default_factory=list)
    research_metadata_panel: ResearchMetadataPanel | None = None
    related_topics: list[RelatedTopic] = Field(default_factory=list)
    inline_citation_markers: list[InlineCitationMarker] = Field(default_factory=list)
    editorial_artifacts: EditorialArtifacts | None = None
    article_schema_version: int | None = None


def normalize_article(raw: dict[str, Any], defaults: dict[str, str]) -> ArticleSchema:
    data = dict(raw or {})

    if "references_to_verify" not in data and "suggested_external_references" in data:
        data["references_to_verify"] = data.get("suggested_external_references")

    if not data.get("sections") and data.get("article_markdown"):
        data["sections"] = _sections_from_markdown(str(data["article_markdown"]))

    data.setdefault("title", defaults.get("title", ""))
    data.setdefault("meta_title", data.get("title") or defaults.get("title", ""))
    data.setdefault("primary_keyword", defaults.get("target_keyword", ""))
    data.setdefault("secondary_keywords", [])
    data.setdefault("key_takeaways", [])
    data.setdefault("table_of_contents", [])
    data["table_of_contents"] = _normalize_table_of_contents(data.get("table_of_contents"))
    data["sections"] = _normalize_sections(data.get("sections"))
    data.setdefault("faq", [])
    data.setdefault("research_context", "")
    data.setdefault("limitations_and_safety", "")
    data["research_context"] = _normalize_prose_block(data.get("research_context"))
    data["limitations_and_safety"] = _normalize_prose_block(data.get("limitations_and_safety"))
    data.setdefault("references_to_verify", [])
    data["references_to_verify"] = _normalize_references_to_verify(data.get("references_to_verify"))
    data.setdefault("backlink_plan", [])
    data["backlink_plan"] = _normalize_backlink_plan(data.get("backlink_plan"))
    data.setdefault("social_posts", {})
    data["social_posts"] = _normalize_social_posts(data.get("social_posts"))
    data["callout_boxes"] = _normalize_message_boxes(data.get("callout_boxes"))
    data["research_insights"] = _normalize_research_insights(data.get("research_insights"))
    data["study_cards"] = _normalize_study_cards(data.get("study_cards"))
    data["definition_boxes"] = _normalize_definition_boxes(data.get("definition_boxes"))
    data["caution_boxes"] = _normalize_message_boxes(data.get("caution_boxes"))
    data["comparison_tables"] = _normalize_comparison_tables(data.get("comparison_tables"))
    data["related_topics"] = _normalize_related_topics(data.get("related_topics"))
    data["inline_citation_markers"] = _normalize_inline_citation_markers(data.get("inline_citation_markers"))
    if data.get("research_metadata_panel") is not None and not isinstance(data.get("research_metadata_panel"), dict):
        data["research_metadata_panel"] = None
    elif isinstance(data.get("research_metadata_panel"), dict):
        data["research_metadata_panel"] = _normalize_research_metadata_panel(data.get("research_metadata_panel"))
    data.setdefault(
        "internal_links",
        [
            {
                "anchor_text": defaults.get("product_name", ""),
                "url": defaults.get("product_url", ""),
                "reason": "Primary product or category link.",
            }
        ],
    )
    data["internal_links"] = _normalize_internal_links(data.get("internal_links"), defaults)

    article = ArticleSchema.model_validate(data)
    if not article.table_of_contents:
        article.table_of_contents = [section.heading for section in article.sections if section.heading]
    article = _sync_editorial_artifacts(article)
    return article


def _sync_editorial_artifacts(article: ArticleSchema) -> ArticleSchema:
    """Dual-read nested editorial artifacts and keep top-level mirrors populated."""
    nested = article.editorial_artifacts
    if nested is not None:
        if nested.references_to_verify and not article.references_to_verify:
            article.references_to_verify = list(nested.references_to_verify)
        if nested.study_cards and not article.study_cards:
            article.study_cards = list(nested.study_cards)
        if nested.research_insights and not article.research_insights:
            article.research_insights = list(nested.research_insights)
        if nested.research_metadata_panel and article.research_metadata_panel is None:
            article.research_metadata_panel = nested.research_metadata_panel
        if nested.backlink_plan and not article.backlink_plan:
            article.backlink_plan = list(nested.backlink_plan)
        if nested.inline_citation_markers and not article.inline_citation_markers:
            article.inline_citation_markers = list(nested.inline_citation_markers)
    article.editorial_artifacts = EditorialArtifacts(
        references_to_verify=list(article.references_to_verify),
        study_cards=list(article.study_cards),
        research_insights=list(article.research_insights),
        research_metadata_panel=article.research_metadata_panel,
        backlink_plan=list(article.backlink_plan),
        inline_citation_markers=list(article.inline_citation_markers),
    )
    return article


def article_to_markdown(
    article: ArticleSchema,
    *,
    surface: ArticleRenderSurface | str = ArticleRenderSurface.EDITORIAL_FULL,
) -> str:
    parts = [f"# {article.title}".strip()]

    if article.excerpt:
        parts.append(article.excerpt)

    if article.key_takeaways:
        parts.append("## Key Takeaways\n" + "\n".join(f"- {item}" for item in article.key_takeaways))

    if article.research_context:
        parts.append(f"## Research Context\n{article.research_context}")

    for section in article.sections:
        if section.heading and section.content_markdown:
            parts.append(f"## {section.heading}\n{section.content_markdown}")
        for subsection in section.subsections:
            if subsection.heading and subsection.content_markdown:
                parts.append(f"### {subsection.heading}\n{subsection.content_markdown}")

    publishable = ArticleRenderSurface(str(surface)) == ArticleRenderSurface.PUBLISHABLE

    if not publishable and article.study_cards:
        cards = "\n\n".join(
            (
                f"### {card.title}\n"
                f"- Source: {card.source_label or 'reference to verify'}\n"
                f"- Context: {card.model_or_context}\n"
                f"- Observed finding: {card.observed_finding}\n"
                f"- Limitation: {card.limitation}\n"
                f"- Verification needed: {card.verification_needed}"
            )
            for card in article.study_cards
            if card.title
        )
        if cards:
            parts.append(f"## Research Notes To Verify\n{cards}")

    if article.limitations_and_safety:
        parts.append(f"## Limitations and Safety Notes\n{article.limitations_and_safety}")

    if not publishable and article.references_to_verify:
        references = "\n".join(
            f"- {reference.title}: {reference.search_query} ({reference.reason})"
            for reference in article.references_to_verify
        )
        parts.append(f"## References to verify\n{references}")

    if article.faq:
        faq = "\n\n".join(f"### {item.question}\n{item.answer}" for item in article.faq)
        parts.append(f"## FAQ\n{faq}")

    return "\n\n".join(part for part in parts if part.strip())


def article_outline(article: ArticleSchema) -> str:
    headings = [section.heading for section in article.sections if section.heading]
    if article.research_context:
        headings.insert(0, "Research Context")
    if article.limitations_and_safety:
        headings.append("Limitations and Safety Notes")
    return "\n".join(f"- {heading}" for heading in headings[:20])


def _sections_from_markdown(markdown: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_heading or current_lines:
                sections.append(
                    {
                        "heading": current_heading,
                        "content_markdown": "\n".join(current_lines).strip(),
                    }
                )
            current_heading = line.strip("# ").strip()
            current_lines = []
        elif not line.startswith("# "):
            current_lines.append(line)

    if current_heading or current_lines:
        sections.append(
            {
                "heading": current_heading or "Introduction",
                "content_markdown": "\n".join(current_lines).strip(),
            }
        )

    return [section for section in sections if section["content_markdown"]]


def _normalize_sections(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            normalized.append({"heading": "Section", "content_markdown": item, "subsections": []})
            continue
        if not isinstance(item, dict):
            continue
        section = dict(item)
        section["heading"] = _string_from_value(section.get("heading") or section.get("title"))
        section["content_markdown"] = _string_from_value(
            section.get("content_markdown") or section.get("content") or section.get("markdown")
        )
        section["subsections"] = _normalize_subsections(section.get("subsections") or section.get("children"))
        normalized.append(section)
    return normalized


def _normalize_subsections(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            normalized.append({"heading": "Subtopic", "content_markdown": item})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "heading": _string_from_value(item.get("heading") or item.get("title")),
                    "content_markdown": _string_from_value(
                        item.get("content_markdown") or item.get("content") or item.get("markdown")
                    ),
                }
            )
    return [item for item in normalized if item["heading"] or item["content_markdown"]]


def _normalize_social_posts(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "x": str(value.get("x") or value.get("twitter") or value.get("X") or ""),
            "threads": str(value.get("threads") or value.get("Threads") or ""),
        }
    if isinstance(value, list):
        normalized = {"x": "", "threads": ""}
        for item in value:
            if not isinstance(item, dict):
                continue
            platform = str(item.get("platform") or item.get("name") or "").strip().lower()
            content = str(item.get("content") or item.get("post") or item.get("text") or "").strip()
            if platform in {"x", "twitter"}:
                normalized["x"] = content
            elif platform == "threads":
                normalized["threads"] = content
            elif not normalized["x"]:
                normalized["x"] = content
            elif not normalized["threads"]:
                normalized["threads"] = content
        return normalized
    return {}


def _normalize_table_of_contents(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("heading")
                or item.get("title")
                or item.get("label")
                or item.get("text")
                or item.get("id")
                or ""
            ).strip()
        else:
            text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_references_to_verify(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        return [_normalize_reference_item(item) for item in value if _reference_has_text(item)]

    if isinstance(value, dict):
        for nested_key in ("references_to_verify", "references", "sources", "items"):
            nested_value = value.get(nested_key)
            if isinstance(nested_value, list):
                return _normalize_references_to_verify(nested_value)
        return [_normalize_reference_item(value)] if _reference_has_text(value) else []

    if isinstance(value, str) and value.strip():
        return [_normalize_reference_item(value)]

    return []


def _normalize_reference_item(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        title = _string_from_value(
            value.get("title")
            or value.get("name")
            or value.get("citation")
            or value.get("source")
            or value.get("reference")
        )
        search_query = _string_from_value(
            value.get("search_query")
            or value.get("query")
            or value.get("url")
            or value.get("link")
            or title
        )
        reason = _string_from_value(
            value.get("reason")
            or value.get("notes")
            or value.get("description")
            or "Source lead returned by the model; verify details before publishing."
        )
        return {
            "title": title or search_query,
            "search_query": search_query or title,
            "reason": reason,
        }

    text = _string_from_value(value)
    return {
        "title": text,
        "search_query": text,
        "reason": "Source lead returned by the model; verify details before publishing.",
    }


def _reference_has_text(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_string_from_value(item) for item in value.values())
    return bool(_string_from_value(value))


def _normalize_backlink_plan(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        return [_normalize_backlink_plan_item(item) for item in value]

    if isinstance(value, dict):
        for nested_key in ("backlink_plan", "plan", "items"):
            nested_value = value.get(nested_key)
            if isinstance(nested_value, list):
                return _normalize_backlink_plan(nested_value)

        targets = value.get("targets")
        if isinstance(targets, list):
            shared = _normalize_backlink_plan_item(value)
            return [
                {
                    **shared,
                    "target_type": _string_from_value(target),
                }
                for target in targets
                if _string_from_value(target)
            ]

        return [_normalize_backlink_plan_item(value)]

    if isinstance(value, str) and value.strip():
        return [{"target_type": value.strip(), "angle": "", "suggested_anchor": "", "notes": ""}]

    return []


def _normalize_backlink_plan_item(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "target_type": _string_from_value(
                value.get("target_type")
                or value.get("target")
                or value.get("type")
                or value.get("site_type")
                or value.get("audience")
            ),
            "angle": _string_from_value(value.get("angle") or value.get("pitch") or value.get("topic")),
            "suggested_anchor": _string_from_value(
                value.get("suggested_anchor") or value.get("anchor") or value.get("anchor_text")
            ),
            "notes": _string_from_value(
                value.get("notes") or value.get("reason") or value.get("rationale") or value.get("description")
            ),
        }

    return {
        "target_type": _string_from_value(value),
        "angle": "",
        "suggested_anchor": "",
        "notes": "",
    }


def _normalize_message_boxes(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"title": "Research note", "message": item})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "title": _string_from_value(item.get("title") or item.get("heading") or item.get("type")),
                    "message": _string_from_value(item.get("message") or item.get("content") or item.get("text")),
                }
            )
    return [item for item in normalized if item["title"] or item["message"]]


def _normalize_research_insights(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"title": "Research insight", "insight": item, "limitation": ""})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "title": _string_from_value(item.get("title") or item.get("heading") or "Research insight"),
                    "insight": _string_from_value(item.get("insight") or item.get("message") or item.get("summary")),
                    "limitation": _string_from_value(item.get("limitation") or item.get("limits") or item.get("notes")),
                }
            )
    return [item for item in normalized if item["insight"]]


def _normalize_study_cards(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append(
                {
                    "title": item,
                    "source_label": "reference to verify",
                    "model_or_context": "",
                    "observed_finding": "",
                    "limitation": "",
                    "verification_needed": "Verify source details before publishing.",
                }
            )
        elif isinstance(item, dict):
            normalized.append(
                {
                    "title": _string_from_value(item.get("title") or item.get("heading")),
                    "source_label": _string_from_value(item.get("source_label") or item.get("source") or "reference to verify"),
                    "model_or_context": _string_from_value(item.get("model_or_context") or item.get("context") or item.get("model")),
                    "observed_finding": _string_from_value(
                        item.get("observed_finding") or item.get("finding") or item.get("summary") or item.get("result")
                    ),
                    "limitation": _string_from_value(item.get("limitation") or item.get("limitations") or item.get("notes")),
                    "verification_needed": _string_from_value(
                        item.get("verification_needed") or item.get("verification") or "Verify source details before publishing."
                    ),
                }
            )
    return [item for item in normalized if item["title"]]


def _normalize_definition_boxes(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"term": item, "definition": ""})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "term": _string_from_value(item.get("term") or item.get("title") or item.get("name")),
                    "definition": _string_from_value(item.get("definition") or item.get("message") or item.get("content")),
                }
            )
    return [item for item in normalized if item["term"] or item["definition"]]


def _normalize_comparison_tables(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows = item.get("rows") if isinstance(item.get("rows"), list) else []
        normalized.append(
            {
                "title": _string_from_value(item.get("title") or item.get("heading")),
                "headers": [_string_from_value(header) for header in item.get("headers", []) if _string_from_value(header)]
                if isinstance(item.get("headers"), list)
                else [],
                "rows": [[_string_from_value(cell) for cell in row] for row in rows if isinstance(row, list)],
            }
        )
    return [item for item in normalized if item["headers"] and item["rows"]]


def _normalize_related_topics(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"title": item, "angle": "", "suggested_url": ""})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "title": _string_from_value(item.get("title") or item.get("topic") or item.get("name")),
                    "angle": _string_from_value(item.get("angle") or item.get("description") or item.get("reason")),
                    "suggested_url": _string_from_value(item.get("suggested_url") or item.get("url") or item.get("link")),
                }
            )
    return [item for item in normalized if item["title"]]


def _normalize_inline_citation_markers(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append({"marker": item, "reference_title": "reference to verify", "context": ""})
        elif isinstance(item, dict):
            normalized.append(
                {
                    "marker": _string_from_value(item.get("marker") or item.get("label") or item.get("id")),
                    "reference_title": _string_from_value(
                        item.get("reference_title") or item.get("reference") or item.get("source") or "reference to verify"
                    ),
                    "context": _string_from_value(item.get("context") or item.get("note") or item.get("reason")),
                }
            )
    return [item for item in normalized if item["marker"]]


def _normalize_research_metadata_panel(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "research_status": _string_from_value(value.get("research_status") or value.get("status")),
        "study_types": value.get("study_types")
        if isinstance(value.get("study_types"), list)
        else value.get("commonly_used_models")
        if isinstance(value.get("commonly_used_models"), list)
        else [],
        "human_use_status": _string_from_value(value.get("human_use_status") or value.get("human_status")),
        "ruo_status": _string_from_value(value.get("ruo_status") or value.get("research_use_label") or value.get("ruo")),
        "confidence_notes": _string_from_value(value.get("confidence_notes") or value.get("notes") or value.get("limitations")),
    }


def _normalize_prose_block(value: Any) -> str:
    """Convert object-shaped or stringified context/safety blocks into reader-facing markdown."""
    if isinstance(value, dict):
        return _sanitize_prose_block(_prose_from_mapping(value))
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            parsed = _parse_mapping_literal(text)
            if isinstance(parsed, dict):
                return _sanitize_prose_block(_prose_from_mapping(parsed))
        return _sanitize_prose_block(text)
    return _sanitize_prose_block(_string_from_value(value))


def _parse_mapping_literal(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, dict) else None
    except (SyntaxError, ValueError):
        return None


_SCHEMA_ARTIFACT_KEYS = frozenset(
    {
        "content_markdown",
        "content",
        "markdown",
        "body",
        "text",
        "html",
        "value",
        "content_html",
        "markdown_content",
        "summary",
        "points",
        "bullets",
        "items",
    }
)

_INTERNAL_FIELD_KEYS = frozenset(
    {
        "heading",
        "title",
        "label",
        "name",
        "type",
        "id",
        "key",
        "field",
        "section",
        "section_id",
        "block_type",
        "block",
        "research_context",
        "limitations_and_safety",
    }
)

_SEMANTIC_FIELD_LABELS = {
    "overview": "Overview",
    "workflow_relevance": "Workflow relevance",
    "evidence_limits": "Evidence limitations",
    "evidence_limitations": "Evidence limitations",
    "limitations": "Limitations",
    "disclaimer": "Disclaimer",
    "scope": "Scope",
    "interpretation_limit": "Interpretation limits",
    "safety_notes": "Safety notes",
    "practical_notes": "Practical notes",
}

_PROSE_CONTENT_KEYS = ("content_markdown", "markdown", "content", "text", "body")

_INTERNAL_BOLD_LABEL_RE = re.compile(
    r"^\*\*(?:Heading|Content Markdown|Summary|Points|Limitations and safety|Research context)\*\*\s*$",
    re.I | re.M,
)


def _prose_field_label(key: str) -> str | None:
    normalized = str(key or "").strip().lower().replace("-", "_")
    if not normalized or normalized in _SCHEMA_ARTIFACT_KEYS or normalized in _INTERNAL_FIELD_KEYS:
        return None
    if normalized in _SEMANTIC_FIELD_LABELS:
        return _SEMANTIC_FIELD_LABELS[normalized]
    if normalized.endswith("_markdown") or normalized.endswith("_json") or normalized.endswith("_html"):
        return None
    return None


def _normalize_field_key(key: str) -> str:
    return str(key or "").strip().lower().replace("-", "_")


def _mapping_has_prose_content(value: dict[str, Any]) -> bool:
    return any(
        isinstance(value.get(prose_key), str) and str(value.get(prose_key) or "").strip()
        for prose_key in _PROSE_CONTENT_KEYS
    )


def _prose_from_mapping(value: dict[str, Any]) -> str:
    for prose_key in _PROSE_CONTENT_KEYS:
        direct = value.get(prose_key)
        if isinstance(direct, str) and direct.strip():
            extras: list[str] = []
            for key, item in value.items():
                if key == prose_key:
                    continue
                normalized_key = _normalize_field_key(str(key))
                if normalized_key in ("heading", "title"):
                    continue
                label = _prose_field_label(str(key))
                extra = _extract_prose_fragment(item, label=label)
                if extra:
                    extras.append(extra)
            return _sanitize_prose_block("\n\n".join([direct.strip(), *extras]).strip())

    parts: list[str] = []
    for key, item in value.items():
        normalized_key = _normalize_field_key(str(key))
        if normalized_key in _SCHEMA_ARTIFACT_KEYS:
            fragment = _extract_prose_fragment(item, label=None)
        elif normalized_key in ("heading", "title"):
            if _mapping_has_prose_content(value):
                continue
            fragment = _string_from_value(item)
        else:
            label = _prose_field_label(str(key))
            fragment = _extract_prose_fragment(item, label=label)
        if fragment:
            parts.append(fragment)
    if parts:
        return _sanitize_prose_block("\n\n".join(parts).strip())
    return _sanitize_prose_block(_string_from_value(value))


def _sanitize_prose_block(text: str) -> str:
    if not text:
        return ""
    lines = [line for line in text.splitlines() if not _INTERNAL_BOLD_LABEL_RE.match(line.strip())]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_prose_fragment(item: Any, *, label: str | None) -> str:
    if isinstance(item, dict):
        nested = _prose_from_mapping(item)
        if not nested:
            return ""
        return f"**{label}**\n\n{nested}" if label else nested
    if isinstance(item, list):
        bullets = "\n".join(f"- {_string_from_value(entry)}" for entry in item if _string_from_value(entry))
        if not bullets:
            return ""
        return f"**{label}**\n\n{bullets}" if label else bullets
    text = _string_from_value(item)
    if not text:
        return ""
    return f"**{label}**\n\n{text}" if label else text


def _normalize_internal_links(value: Any, defaults: dict[str, str]) -> list[dict[str, str]]:
    product_url = str(defaults.get("product_url") or "").strip()
    product_name = str(defaults.get("product_name") or "").strip()
    links: list[dict[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                links.append(
                    {
                        "anchor_text": _string_from_value(item.get("anchor_text") or item.get("text") or product_name),
                        "url": _string_from_value(item.get("url") or item.get("href") or product_url),
                        "reason": _string_from_value(item.get("reason") or item.get("notes") or ""),
                    }
                )
    if not links and product_url:
        links.append(
            {
                "anchor_text": product_name or "View product",
                "url": product_url,
                "reason": "Primary product or category link.",
            }
        )
    if product_url:
        from app.catalog.products import is_product_page_url

        for link in links:
            current_url = str(link.get("url") or "").strip()
            if current_url == product_url:
                continue
            if not is_product_page_url(current_url) and is_product_page_url(product_url):
                link["url"] = product_url
    return [link for link in links if link.get("url")]


def _string_from_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = []
        for key in ("summary", "content", "text", "description", "notes", "message", "title", "name", "target", "type", "target_type"):
            item = value.get(key)
            if item:
                parts.append(_string_from_value(item))
        for key in ("bullets", "items", "points", "warnings", "rules", "limitations", "safety_notes"):
            item = value.get(key)
            if isinstance(item, list):
                parts.extend(_string_from_value(entry) for entry in item if _string_from_value(entry))
        return "\n\n".join(part for part in parts if part).strip() or str(value).strip()
    if isinstance(value, list):
        return "\n".join(_string_from_value(item) for item in value if _string_from_value(item)).strip()
    return str(value).strip()


ArticleSection.model_rebuild()
