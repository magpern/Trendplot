from __future__ import annotations

import copy
import re
from typing import Any

from app.ai_opportunity_ideation.article_brief import resolve_article_content_type
from app.review.comparison_matrix import build_comparison_matrix, matrix_cells_are_distinct

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "in",
        "on",
        "for",
        "to",
        "of",
        "and",
        "or",
        "that",
        "this",
        "with",
        "as",
        "by",
        "be",
        "can",
        "may",
        "not",
        "when",
        "from",
        "into",
        "often",
        "usually",
        "more",
        "most",
        "should",
        "because",
        "which",
        "what",
        "how",
        "why",
        "where",
        "while",
        "than",
        "also",
        "only",
        "their",
        "they",
        "it",
        "its",
        "at",
        "has",
        "have",
        "been",
        "being",
        "was",
        "were",
        "will",
        "would",
        "could",
        "about",
        "such",
        "through",
        "across",
        "between",
        "both",
        "each",
        "other",
        "some",
        "any",
        "all",
        "very",
        "just",
        "does",
        "do",
        "did",
        "but",
        "if",
        "so",
        "then",
        "there",
        "these",
        "those",
        "them",
        "one",
        "two",
        "your",
        "reader",
        "readers",
        "literature",
        "research",
        "study",
        "studies",
        "paper",
        "papers",
    }
)

_CONCEPT_THEMES: list[tuple[str, re.Pattern[str]]] = [
    (
        "kinetics_timing",
        re.compile(
            r"\b(kinetic|kinetics|timing|pulse|pulsatile|exposure|duration|half-?life|"
            r"pharmacokinetic|timepoint|onset|clearance)\b",
            re.I,
        ),
    ),
    (
        "sampling_endpoints",
        re.compile(
            r"\b(sampling|endpoint|endpoints|measurement|assay|readout|timepoint|"
            r"biomarker|serial draw)\b",
            re.I,
        ),
    ),
    (
        "interpretation_caution",
        re.compile(
            r"\b(interpret(?:ation)?|extrapolat|should not be read|read cautiously|"
            r"do not treat|misleading to compare)\b",
            re.I,
        ),
    ),
    (
        "nomenclature",
        re.compile(
            r"\b(nomenclature|naming|label(?:ing)?|terminology|not interchangeable|"
            r"shorthand|abbreviation)\b",
            re.I,
        ),
    ),
    (
        "model_design",
        re.compile(
            r"\b(model (?:type|system|design)|preclinical|in vitro|ex vivo|"
            r"experimental (?:setup|design)|animal model)\b",
            re.I,
        ),
    ),
    (
        "receptor_signaling",
        re.compile(
            r"\b(receptor|signaling|signalling|pathway|pathways|GHRH|GHSR|secretagogue)\b",
            re.I,
        ),
    ),
    (
        "summary_restatement",
        re.compile(
            r"\b(in summary|takeaway|bottom line|cleanest (?:takeaway|distinction)|"
            r"the (?:main|central) (?:point|difference)|overall)\b",
            re.I,
        ),
    ),
]

_CALLOUT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Common Misconception", re.compile(r"\b(not the same|misconception|often confused|mistakenly|incorrect to assume)\b", re.I)),
    ("Key Distinction", re.compile(r"\b(key distinction|central difference|main difference|not interchangeable|real distinction)\b", re.I)),
    ("Practical Interpretation", re.compile(r"\b(practical rule|read this as|when evaluating|best way to read|interpret(?:ation)? should)\b", re.I)),
]

_SECTION_INTEGRATION_HINTS = re.compile(
    r"\b(experimental|model|assay|sampling|evaluat|practical|interpret|where|fits|timing)\b",
    re.I,
)

_MAX_THEME_SENTENCES = 2

_COMPOSITION_PROFILES: dict[str, list[str]] = {
    "comparison": ["comparison_matrix", "terminology_summary", "key_distinction_callout"],
    "mechanism": ["mechanism_summary_table", "concept_cheatsheet", "interpretation_callout"],
    "mechanism_explainer": ["mechanism_summary_table", "concept_cheatsheet", "interpretation_callout"],
    "research_overview": ["concept_cheatsheet", "quick_interpretation_guide"],
    "relationship": ["relationship_summary_table", "key_distinction_callout"],
    "product_relationship": ["relationship_summary_table", "key_distinction_callout"],
}


def apply_article_composition_refinement(
    article_json: dict[str, Any],
    *,
    opportunity_context: dict[str, Any] | None,
    defaults: dict[str, str],
) -> dict[str, Any]:
    data = copy.deepcopy(article_json or {})
    content_type = resolve_article_content_type(opportunity_context)
    profile = _COMPOSITION_PROFILES.get(content_type, _COMPOSITION_PROFILES["research_overview"])

    data = compress_repeated_concepts(data)
    data = promote_callouts_from_content(data, profile=profile)
    data = build_type_structured_elements(
        data,
        content_type=content_type,
        defaults=defaults,
        profile=profile,
        opportunity_context=opportunity_context,
    )
    return data


def compress_repeated_concepts(article_json: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(article_json or {})
    kept_by_theme: dict[str, str] = {}
    theme_occurrences: dict[str, int] = {}
    theme_sentence_counts: dict[str, int] = {}

    if data.get("research_context"):
        data["research_context"] = _compress_text_block(
            str(data["research_context"]),
            kept_by_theme=kept_by_theme,
            theme_occurrences=theme_occurrences,
            theme_sentence_counts=theme_sentence_counts,
            field_priority=0,
        )

    sections = data.get("sections")
    if isinstance(sections, list):
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            heading = str(section.get("heading") or "")
            section["content_markdown"] = _compress_text_block(
                str(section.get("content_markdown") or ""),
                kept_by_theme=kept_by_theme,
                theme_occurrences=theme_occurrences,
                theme_sentence_counts=theme_sentence_counts,
                field_priority=10 + index,
                is_summary_section=_is_summary_section(heading),
            )
            for sub_index, subsection in enumerate(section.get("subsections") or []):
                if isinstance(subsection, dict):
                    subsection["content_markdown"] = _compress_text_block(
                        str(subsection.get("content_markdown") or ""),
                        kept_by_theme=kept_by_theme,
                        theme_occurrences=theme_occurrences,
                        theme_sentence_counts=theme_sentence_counts,
                        field_priority=100 + index * 10 + sub_index,
                    )

    takeaways = data.get("key_takeaways")
    if isinstance(takeaways, list):
        filtered: list[str] = []
        for item in takeaways:
            text = str(item or "").strip()
            if not text:
                continue
            themes = _sentence_themes(text)
            if themes and all(_is_redundant_takeaway(text, kept_by_theme.get(theme, "")) for theme in themes):
                continue
            filtered.append(text)
        data["key_takeaways"] = filtered

    return data


def promote_callouts_from_content(article_json: dict[str, Any], *, profile: list[str]) -> dict[str, Any]:
    data = copy.deepcopy(article_json or {})
    callouts = list(data.get("callout_boxes") or [])
    existing_messages = {str(item.get("message") or "").strip().lower() for item in callouts if isinstance(item, dict)}
    existing_titles = {str(item.get("title") or "").strip().lower() for item in callouts if isinstance(item, dict)}

    desired_titles = {
        "key distinction": "key_distinction_callout" in profile,
        "common misconception": False,
        "practical interpretation": "interpretation_callout" in profile or "quick_interpretation_guide" in profile,
    }

    sections = data.get("sections")
    if not isinstance(sections, list):
        return data

    for section in sections:
        if not isinstance(section, dict):
            continue
        updated, extracted = _extract_callout_sentences(
            str(section.get("content_markdown") or ""),
            desired_titles=desired_titles,
            existing_messages=existing_messages,
            existing_titles=existing_titles,
        )
        section["content_markdown"] = updated
        for title, message in extracted:
            callouts.append({"title": title, "message": message})
            existing_messages.add(message.lower())
            existing_titles.add(title.lower())

    data["callout_boxes"] = callouts
    return data


def build_type_structured_elements(
    article_json: dict[str, Any],
    *,
    content_type: str,
    defaults: dict[str, str],
    profile: list[str],
    opportunity_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = copy.deepcopy(article_json or {})
    tables = list(data.get("comparison_tables") or [])
    definitions = list(data.get("definition_boxes") or [])

    if "comparison_matrix" in profile and _table_needs_derivation(tables):
        derived = build_comparison_matrix(data, defaults=defaults, opportunity_context=opportunity_context)
        if derived:
            tables.insert(0, derived)

    if "mechanism_summary_table" in profile and _table_needs_derivation(tables):
        derived = _build_mechanism_summary_table(data)
        if derived:
            tables.insert(0, derived)

    if "relationship_summary_table" in profile and _table_needs_derivation(tables):
        derived = _build_relationship_summary_table(data, defaults=defaults)
        if derived:
            tables.insert(0, derived)

    if ("terminology_summary" in profile or "concept_cheatsheet" in profile) and len(definitions) < 3:
        definitions.extend(_build_definition_cheatsheet(data, defaults=defaults, content_type=content_type))

    data["comparison_tables"] = tables
    data["definition_boxes"] = definitions
    return data


def integrate_product_reference(article_json: dict[str, Any], *, defaults: dict[str, str]) -> dict[str, Any]:
    """Deprecated: product linking is handled by app.internal_links.product_linker."""
    return copy.deepcopy(article_json or {})


def product_reference_integrated(article_json: dict[str, Any], *, product_url: str = "") -> bool:
    url = product_url.strip()
    if not url:
        links = article_json.get("internal_links") or []
        if isinstance(links, list) and links and isinstance(links[0], dict):
            url = str(links[0].get("url") or "").strip()
    if not url:
        return False
    return _product_url_in_sections(article_json, url)


def count_concept_repetitions(article_json: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {theme: 0 for theme, _ in _CONCEPT_THEMES}
    blob = _article_prose_blob(article_json)
    for theme, pattern in _CONCEPT_THEMES:
        counts[theme] = len(pattern.findall(blob))
    return counts


def prose_word_count(article_json: dict[str, Any]) -> int:
    return len(_article_prose_blob(article_json).split())


def _compress_text_block(
    text: str,
    *,
    kept_by_theme: dict[str, str],
    theme_occurrences: dict[str, int],
    theme_sentence_counts: dict[str, int],
    field_priority: int,
    is_summary_section: bool = False,
) -> str:
    if not text.strip():
        return ""
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        kept_sentences: list[str] = []
        for sentence in _split_sentences(paragraph):
            themes = _sentence_themes(sentence)
            if not themes:
                kept_sentences.append(sentence)
                continue

            drop = False
            for theme in themes:
                previous = kept_by_theme.get(theme)
                count = theme_occurrences.get(theme, 0)
                kept_count = theme_sentence_counts.get(theme, 0)
                if kept_count >= _MAX_THEME_SENTENCES and (
                    not _sentence_adds_new_info(previous or "", sentence)
                    or _is_subset_restatement(previous or "", sentence)
                ):
                    drop = True
                    break
                if previous and _is_subset_restatement(previous, sentence):
                    drop = True
                    break
                if count == 0:
                    kept_by_theme[theme] = sentence
                    theme_occurrences[theme] = 1
                    continue

                if previous and _sentence_similarity(previous, sentence) >= 0.25:
                    drop = True
                    break
                if count >= 2 and not _sentence_adds_new_info(previous or "", sentence):
                    drop = True
                    break
                if is_summary_section and count >= 1:
                    drop = True
                    break
                if len(sentence) > len(previous or ""):
                    kept_by_theme[theme] = sentence
                theme_occurrences[theme] = count + 1

            if not drop:
                kept_sentences.append(sentence)
                for theme in themes:
                    theme_sentence_counts[theme] = theme_sentence_counts.get(theme, 0) + 1

        if kept_sentences:
            paragraphs.append(" ".join(kept_sentences).strip())
    return "\n\n".join(paragraphs).strip()


def _is_summary_section(heading: str) -> bool:
    lowered = heading.lower()
    return any(token in lowered for token in ("summary", "takeaway", "bottom line", "quick answer"))


def _extract_callout_sentences(
    text: str,
    *,
    desired_titles: dict[str, bool],
    existing_messages: set[str],
    existing_titles: set[str],
) -> tuple[str, list[tuple[str, str]]]:
    if not text.strip():
        return text, []

    extracted: list[tuple[str, str]] = []
    paragraphs: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        kept: list[str] = []
        for sentence in _split_sentences(paragraph):
            title = _callout_title_for_sentence(sentence, desired_titles=desired_titles)
            if title and title.lower() not in existing_titles and sentence.strip().lower() not in existing_messages:
                extracted.append((title, sentence.strip()))
                existing_titles.add(title.lower())
                existing_messages.add(sentence.strip().lower())
                continue
            kept.append(sentence)
        if kept:
            paragraphs.append(" ".join(kept).strip())
    return "\n\n".join(paragraphs).strip(), extracted


def _callout_title_for_sentence(sentence: str, *, desired_titles: dict[str, bool]) -> str | None:
    for title, pattern in _CALLOUT_PATTERNS:
        if pattern.search(sentence) and desired_titles.get(title.lower(), True):
            return title
    return None


def _build_mechanism_summary_table(article_json: dict[str, Any]) -> dict[str, Any] | None:
    section_texts = _section_texts(article_json)
    rows = []
    for topic, keywords in (
        ("Primary receptor target", ["receptor", "GHRH", "GHSR", "binds"]),
        ("Signaling pathway", ["signaling", "pathway", "cAMP", "calcium", "cascade"]),
        ("Downstream biology", ["secret", "pulse", "pituitary", "growth hormone", "downstream"]),
        ("Experimental models", ["in vitro", "preclinical", "model", "assay"]),
        ("Evidence limits", ["limited", "preclinical", "human", "uncertain", "caution"]),
    ):
        snippet = _snippet_for_keywords(section_texts, keywords)
        if snippet:
            rows.append([topic, snippet])
    if len(rows) < 3:
        return None
    return {"title": "Mechanism Summary Table", "headers": ["Theme", "Summary"], "rows": rows}


def _build_relationship_summary_table(article_json: dict[str, Any], *, defaults: dict[str, str]) -> dict[str, Any] | None:
    section_texts = _section_texts(article_json)
    subjects = _relationship_subjects(str(article_json.get("title") or ""), defaults)
    rows = []
    for topic, keywords in (
        ("Shared research themes", ["shared", "overlap", "both", "together", "paired"]),
        ("Key distinction", ["distinction", "difference", "separate", "unlike", "whereas"]),
        ("When literature pairs them", ["literature", "studied together", "combination", "paired", "stack"]),
        ("Interpretation caution", ["interpret", "caution", "not interchangeable", "model"]),
    ):
        snippet = _snippet_for_keywords(section_texts, keywords)
        if snippet:
            rows.append([topic, snippet])
    if len(rows) < 3:
        return None
    return {
        "title": "Relationship Summary Table",
        "headers": ["Relationship lens", "Summary"],
        "rows": rows,
    }


def _build_definition_cheatsheet(
    article_json: dict[str, Any],
    *,
    defaults: dict[str, str],
    content_type: str,
) -> list[dict[str, str]]:
    title = "Concept Cheat-Sheet" if "mechanism" in content_type else "Terminology Summary"
    terms: list[tuple[str, str]] = []
    seen: set[str] = set()

    for keyword in [str(article_json.get("primary_keyword") or ""), *list(article_json.get("secondary_keywords") or [])]:
        keyword = str(keyword or "").strip()
        if len(keyword) < 4 or keyword.lower() in seen:
            continue
        definition = _definition_from_sections(keyword, _section_texts(article_json))
        if definition:
            terms.append((keyword, definition))
            seen.add(keyword.lower())
        if len(terms) >= 4:
            break

    product_name = str(defaults.get("product_name") or "").strip()
    if product_name and product_name.lower() not in seen:
        definition = _definition_from_sections(product_name, _section_texts(article_json))
        if definition:
            terms.insert(0, (product_name, definition))

    return [{"term": term, "definition": definition} for term, definition in terms[:4]]


def _definition_from_sections(term: str, section_texts: list[str]) -> str:
    term_lower = term.lower()
    for text in section_texts:
        for sentence in _split_sentences(text):
            if term_lower in sentence.lower():
                return _truncate_sentence(sentence, 180)
    return ""


def _relationship_subjects(title: str, defaults: dict[str, str]) -> list[str]:
    cleaned = re.sub(r":.*$", "", title).strip()
    parts = re.split(r"\s+and\s+", cleaned, maxsplit=1, flags=re.I)
    if len(parts) == 2:
        return [_clean_subject(parts[0]), _clean_subject(parts[1])]
    product = str(defaults.get("product_name") or "").strip()
    return [product] if product else []


def _clean_subject(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -:,")


def _table_needs_derivation(tables: list[Any]) -> bool:
    if not tables:
        return True
    for table in tables:
        if isinstance(table, dict) and len(table.get("rows") or []) >= 3 and matrix_cells_are_distinct(table):
            return False
    return True


def _section_texts(article_json: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    research_context = str(article_json.get("research_context") or "").strip()
    if research_context:
        texts.append(research_context)
    sections = article_json.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                content = str(section.get("content_markdown") or "").strip()
                if content:
                    texts.append(content)
    return texts


def _snippet_for_keywords(section_texts: list[str], keywords: list[str], *, require_any: bool = True) -> str:
    for text in section_texts:
        for sentence in _split_sentences(text):
            if any(keyword.lower() in sentence.lower() for keyword in keywords):
                return _truncate_sentence(sentence, 140)
    return "" if require_any else ""


def _product_integration_section_index(sections: list[Any], product_name: str) -> int:
    best_index = 0
    best_score = -1
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "")
        content = str(section.get("content_markdown") or "")
        score = 0
        if _SECTION_INTEGRATION_HINTS.search(heading):
            score += 3
        if _SECTION_INTEGRATION_HINTS.search(content[:300]):
            score += 2
        if product_name.lower() in content.lower():
            score += 4
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _product_url_in_sections(article_json: dict[str, Any], product_url: str) -> bool:
    sections = article_json.get("sections")
    if not isinstance(sections, list):
        return False
    for section in sections:
        if isinstance(section, dict) and product_url in str(section.get("content_markdown") or ""):
            return True
        for subsection in section.get("subsections") or []:
            if isinstance(subsection, dict) and product_url in str(subsection.get("content_markdown") or ""):
                return True
    return False


def _ensure_markdown_product_link(content: str, product_name: str, product_url: str) -> str:
    if product_url in content:
        return content
    if product_name.lower() in content.lower():
        return re.sub(
            re.escape(product_name),
            f"[{product_name}]({product_url})",
            content,
            count=1,
            flags=re.I,
        )
    return content


def _lowercase_first_sentence(text: str) -> str:
    if not text:
        return text
    return text[0].lower() + text[1:] if text[0].isupper() else text


def _sentence_themes(sentence: str) -> set[str]:
    return {theme for theme, pattern in _CONCEPT_THEMES if pattern.search(sentence)}


def _sentence_similarity(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _is_redundant_takeaway(takeaway: str, kept_sentence: str) -> bool:
    if not kept_sentence:
        return False
    return _sentence_similarity(takeaway, kept_sentence) >= 0.5


def _sentence_adds_new_info(anchor: str, candidate: str) -> bool:
    anchor_tokens = _token_set(anchor)
    candidate_tokens = _token_set(candidate)
    new_tokens = candidate_tokens - anchor_tokens
    return len(new_tokens) >= 4


def _is_subset_restatement(previous: str, candidate: str) -> bool:
    previous_tokens = _token_set(previous)
    candidate_tokens = _token_set(candidate)
    if not candidate_tokens:
        return False
    overlap = len(previous_tokens & candidate_tokens) / len(candidate_tokens)
    return overlap >= 0.62 and len(candidate_tokens - previous_tokens) <= 4


def _token_set(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def _split_sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", value.strip())
    return [part.strip() for part in parts if part.strip()]


def _truncate_sentence(value: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _article_prose_blob(article_json: dict[str, Any]) -> str:
    parts = [
        str(article_json.get("excerpt") or ""),
        str(article_json.get("research_context") or ""),
        " ".join(str(item) for item in article_json.get("key_takeaways") or []),
    ]
    for text in _section_texts(article_json):
        parts.append(text)
    return "\n".join(part for part in parts if part.strip())
