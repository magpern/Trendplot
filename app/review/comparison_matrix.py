from __future__ import annotations

import re
from typing import Any

_MAX_CELL_WORDS = 18

_COMPARISON_ROWS: tuple[tuple[str, str], ...] = (
    ("exposure_profile", "Exposure profile"),
    ("receptor_themes", "Receptor themes"),
    ("sampling_focus", "Sampling focus"),
    ("interpretation_focus", "Interpretation focus"),
)

_ROW_SIGNALS: dict[str, dict[str, tuple[str, ...]]] = {
    "exposure_profile": {
        "left": (
            "short-acting",
            "shorter",
            "no-dac",
            "no dac",
            "pulse",
            "pulsatile",
            "timing",
            "transient",
        ),
        "right": (
            "dac",
            "long-acting",
            "prolonged",
            "sustained",
            "extended",
            "albumin",
            "persistent",
        ),
    },
    "receptor_themes": {
        "left": (
            "ghrh",
            "ghsr",
            "ghrelin",
            "ipamorelin",
            "dual",
            "paired",
            "two receptor",
            "two axis",
            "secretagogue pair",
        ),
        "right": (
            "ghrh analog",
            "ghrh receptor",
            "single",
            "one axis",
            "one receptor",
            "ghrh-side",
            "ghrh pathway",
        ),
    },
    "sampling_focus": {
        "left": (
            "pulse-sensitive",
            "time-resolved",
            "early peak",
            "timing resolution",
            "serial sampling",
            "pulse detection",
        ),
        "right": (
            "time-course",
            "broader window",
            "sustained exposure",
            "longer window",
            "prolonged signal",
        ),
    },
    "interpretation_focus": {
        "left": (
            "coordination",
            "coordinated",
            "interaction",
            "paired",
            "dual-pathway",
            "network",
            "signal complement",
        ),
        "right": (
            "persistence",
            "sustained",
            "exposure support",
            "single-agent",
            "prolonged",
            "kinetic support",
        ),
    },
}

_ROW_FALLBACKS: dict[str, tuple[str, str]] = {
    "exposure_profile": ("Shorter pulse-oriented exposure", "Extended exposure profile"),
    "receptor_themes": ("GHRH + ghrelin-axis context", "Primarily GHRH analog context"),
    "sampling_focus": ("Early pulse-sensitive windows", "Broader time-course windows"),
    "interpretation_focus": ("Signal coordination", "Exposure persistence"),
}

_METABOLIC_SIGNALS: dict[str, dict[str, tuple[str, ...]]] = {
    "exposure_profile": {
        "left": ("tri-agonist", "multi-receptor", "broader receptor", "glucagon arm"),
        "right": ("dual incretin", "dual agonist", "glp-1 centered", "incretin synergy"),
    },
    "receptor_themes": {
        "left": ("glucagon", "tri-agonist", "triple agonist", "glp-1", "gip", "glucagon receptor"),
        "right": ("dual agonist", "glp-1", "gip", "incretin", "twincretin"),
    },
    "sampling_focus": {
        "left": ("energy expenditure", "hepatic", "substrate", "glucagon receptor"),
        "right": ("glycemic", "weight", "appetite", "incretin"),
    },
    "interpretation_focus": {
        "left": ("pathway balance", "multi-receptor balance", "glucagon receptor activity"),
        "right": ("incretin synergy", "dual incretin", "glp-1 centered profile"),
    },
}

_METABOLIC_FALLBACKS: dict[str, tuple[str, str]] = {
    "exposure_profile": ("Broader multi-receptor metabolic window", "Dual incretin-centered window"),
    "receptor_themes": ("GLP-1 + GIP + glucagon tri-agonist", "Dual GLP-1/GIP agonist"),
    "sampling_focus": ("Hepatic and energy-balance endpoints", "Glycemic and weight endpoints"),
    "interpretation_focus": ("Pathway balance across three receptors", "Incretin synergy framing"),
}

_CONTRAST_SPLIT_RE = re.compile(
    r"(?P<a>.+?)\s*,?\s+while\s+(?P<b>.+?)$|"
    r"(?P<c>.+?)\s+whereas\s+(?P<d>.+?)$|"
    r"(?P<e>.+?)\s+compared\s+to\s+(?P<f>.+?)$",
    re.I,
)


def build_comparison_matrix(
    article_json: dict[str, Any],
    *,
    defaults: dict[str, str],
    opportunity_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    title = str(article_json.get("title") or defaults.get("title") or "")
    subjects = comparison_subjects(title, defaults, opportunity_context)
    if len(subjects) < 2:
        return None

    left_subject, right_subject = subjects[0], subjects[1]
    left_aliases = _subject_aliases(left_subject)
    right_aliases = _subject_aliases(right_subject)
    sources = _comparison_sources(article_json, opportunity_context)
    domain = _comparison_domain(article_json, opportunity_context)
    row_signals = _signals_for_domain(domain)
    row_fallbacks = _fallbacks_for_domain(domain)
    used_cells: set[str] = set()

    rows: list[list[str]] = []
    for row_key, row_label in _COMPARISON_ROWS:
        left_cell, right_cell = _derive_row_cells(
            row_key=row_key,
            sources=sources,
            left_subject=left_subject,
            right_subject=right_subject,
            left_aliases=left_aliases,
            right_aliases=right_aliases,
            row_signals=row_signals,
        )
        left_cell = _normalize_cell(left_cell)
        right_cell = _normalize_cell(right_cell)
        if not _cell_is_usable(left_cell, row_signals[row_key]["left"]):
            left_cell = row_fallbacks[row_key][0]
        if not _cell_is_usable(right_cell, row_signals[row_key]["right"]):
            right_cell = row_fallbacks[row_key][1]
        if left_cell.lower() in used_cells:
            left_cell = row_fallbacks[row_key][0]
        if right_cell.lower() in used_cells:
            right_cell = row_fallbacks[row_key][1]
        if left_cell.lower() == right_cell.lower():
            left_cell, right_cell = row_fallbacks[row_key]
        used_cells.add(left_cell.lower())
        used_cells.add(right_cell.lower())
        rows.append([row_label, left_cell, right_cell])

    if len(rows) < 3:
        return None
    return {
        "title": "Comparison Matrix",
        "headers": ["Topic", left_subject, right_subject],
        "rows": rows,
    }


def comparison_subjects(
    title: str,
    defaults: dict[str, str],
    opportunity_context: dict[str, Any] | None = None,
) -> list[str]:
    context = opportunity_context or {}
    related = [str(item).strip() for item in context.get("related_products") or [] if str(item).strip()]
    if len(related) >= 2:
        return [_clean_subject(related[0]), _clean_subject(related[1])]

    cleaned = re.sub(r":.*$", "", title).strip()
    for pattern in (r"\s+vs\.?\s+", r"\s+versus\s+"):
        parts = re.split(pattern, cleaned, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return [_clean_subject(parts[0]), _clean_subject(parts[1])]

    product = str(defaults.get("product_name") or "").strip()
    if product and product.lower() in cleaned.lower():
        other = cleaned.replace(product, "", 1).strip(" -:,")
        if other:
            return [_clean_subject(product), _clean_subject(other)]
    if product:
        return [product, "Comparator"]
    return []


def matrix_cells_are_distinct(matrix: dict[str, Any]) -> bool:
    for row in matrix.get("rows") or []:
        if len(row) < 3:
            continue
        if str(row[1]).strip().lower() == str(row[2]).strip().lower():
            return False
    return True


def matrix_cell_word_limit(matrix: dict[str, Any], *, max_words: int = _MAX_CELL_WORDS) -> bool:
    for row in matrix.get("rows") or []:
        for cell in row[1:3]:
            if len(str(cell).split()) > max_words:
                return False
    return True


def _signals_for_domain(domain: str) -> dict[str, dict[str, tuple[str, ...]]]:
    if domain == "metabolic":
        merged: dict[str, dict[str, tuple[str, ...]]] = {}
        for row_key in _ROW_SIGNALS:
            merged[row_key] = {
                "left": _ROW_SIGNALS[row_key]["left"] + _METABOLIC_SIGNALS[row_key]["left"],
                "right": _ROW_SIGNALS[row_key]["right"] + _METABOLIC_SIGNALS[row_key]["right"],
            }
        return merged
    return _ROW_SIGNALS


def _fallbacks_for_domain(domain: str) -> dict[str, tuple[str, str]]:
    if domain == "metabolic":
        return _METABOLIC_FALLBACKS
    return _ROW_FALLBACKS


def _comparison_domain(article_json: dict[str, Any], opportunity_context: dict[str, Any] | None) -> str:
    parts = [
        str(article_json.get("title") or ""),
        str(article_json.get("excerpt") or ""),
        " ".join(str(item) for item in article_json.get("key_takeaways") or []),
        " ".join(str(item) for item in article_json.get("secondary_keywords") or []),
    ]
    context = opportunity_context or {}
    parts.extend(str(context.get(key) or "") for key in ("headline", "abstract"))
    blob = " ".join(parts).lower()
    if any(token in blob for token in ("glp-1", "gip", "glucagon", "retatrutide", "tirzepatide", "incretin", "metabolic")):
        return "metabolic"
    if any(token in blob for token in ("ghrh", "ghsr", "cjc", "ipamorelin", "secretagogue", "peptide")):
        return "peptide_endocrine"
    return "generic"


def _derive_row_cells(
    *,
    row_key: str,
    sources: list[str],
    left_subject: str,
    right_subject: str,
    left_aliases: list[str],
    right_aliases: list[str],
    row_signals: dict[str, dict[str, tuple[str, ...]]],
) -> tuple[str, str]:
    left_cell = ""
    right_cell = ""
    signals = row_signals[row_key]

    for source in sources:
        for sentence in _split_sentences(source):
            contrast_left, contrast_right = _split_contrast_sentence(sentence)
            if contrast_left and contrast_right:
                left_side = _sentence_side(contrast_left, left_aliases, right_aliases)
                right_side = _sentence_side(contrast_right, left_aliases, right_aliases)
                if left_side in {"left", "both"} and not left_cell:
                    left_cell = _phrase_for_side(contrast_left, signals["left"], left_aliases)
                if right_side in {"right", "both"} and not right_cell:
                    right_cell = _phrase_for_side(contrast_right, signals["right"], right_aliases)
                if left_side == "right" and not right_cell:
                    right_cell = _phrase_for_side(contrast_left, signals["right"], right_aliases)
                if right_side == "left" and not left_cell:
                    left_cell = _phrase_for_side(contrast_right, signals["left"], left_aliases)

            side = _sentence_side(sentence, left_aliases, right_aliases)
            if side == "left" and not left_cell:
                phrase = _phrase_for_side(sentence, signals["left"], left_aliases)
                if phrase:
                    left_cell = phrase
            elif side == "right" and not right_cell:
                phrase = _phrase_for_side(sentence, signals["right"], right_aliases)
                if phrase:
                    right_cell = phrase
            elif side == "both":
                if not left_cell:
                    left_cell = _phrase_for_side(sentence, signals["left"], left_aliases)
                if not right_cell:
                    right_cell = _phrase_for_side(sentence, signals["right"], right_aliases)

        if left_cell and right_cell:
            break

    if left_cell and not _cell_matches_signals(left_cell, signals["left"]):
        left_cell = ""
    if right_cell and not _cell_matches_signals(right_cell, signals["right"]):
        right_cell = ""

    return left_cell, right_cell


def _cell_matches_signals(cell: str, signals: tuple[str, ...]) -> bool:
    lowered = cell.lower()
    return any(signal in lowered for signal in signals)


def _cell_is_usable(cell: str, signals: tuple[str, ...]) -> bool:
    if not cell or len(cell.split()) < 3:
        return False
    if not _cell_matches_signals(cell, signals):
        return False
    if re.match(r"^(to|as a|and|or)\b", cell, re.I):
        return False
    if re.search(r"\b(are typically framed around|unless authors define|alone to)\b", cell, re.I):
        return False
    return True


def _comparison_sources(article_json: dict[str, Any], opportunity_context: dict[str, Any] | None) -> list[str]:
    sources: list[str] = []
    context = opportunity_context or {}

    for takeaway in article_json.get("key_takeaways") or []:
        text = str(takeaway or "").strip()
        if text:
            sources.append(text)

    for box in article_json.get("definition_boxes") or []:
        if isinstance(box, dict):
            term = str(box.get("term") or "").strip()
            definition = str(box.get("definition") or "").strip()
            if term and definition:
                sources.append(f"{term}: {definition}")

    for key in ("abstract", "headline"):
        text = str(context.get(key) or "").strip()
        if text:
            sources.append(text)

    for target_key in ("major_pathways", "recurring_literature_themes", "evidence_strengths", "evidence_limitations"):
        depth = context.get("science_depth_targets") or {}
        if isinstance(depth, dict):
            for item in depth.get(target_key) or []:
                text = str(item or "").strip()
                if text:
                    sources.append(text)

    excerpt = str(article_json.get("excerpt") or "").strip()
    if excerpt:
        sources.append(excerpt)

    research_context = str(article_json.get("research_context") or "").strip()
    if research_context:
        sources.append(research_context)

    for section in article_json.get("sections") or []:
        if isinstance(section, dict):
            heading = str(section.get("heading") or "").strip()
            content = str(section.get("content_markdown") or "").strip()
            if heading and content:
                sources.append(f"{heading}: {content}")

    return sources


def _split_contrast_sentence(sentence: str) -> tuple[str, str]:
    match = _CONTRAST_SPLIT_RE.search(sentence.strip())
    if not match:
        return "", ""
    groups = match.groupdict()
    left = groups.get("a") or groups.get("c") or groups.get("e") or ""
    right = groups.get("b") or groups.get("d") or groups.get("f") or ""
    return left.strip(" ,;."), right.strip(" ,;.")


def _phrase_for_side(sentence: str, signals: tuple[str, ...], aliases: list[str]) -> str:
    for signal in signals:
        pattern = re.compile(
            rf"((?:[\w-]+\s+){{0,2}}[\w-]*{re.escape(signal)}[\w-]*(?:\s+[\w-]+){{0,5}})",
            re.I,
        )
        for match in pattern.finditer(sentence):
            phrase = match.group(1).strip(" ,;:-")
            if len(phrase.split()) >= 2:
                return _normalize_cell(phrase)

    cleaned = _strip_subject_prefix(sentence, aliases)
    clause = _clause_after_subject(cleaned, aliases)
    if clause and len(clause.split()) >= 2:
        return _normalize_cell(clause)
    return ""


def _strip_subject_prefix(sentence: str, aliases: list[str]) -> str:
    text = sentence
    for alias in sorted(aliases, key=len, reverse=True):
        text = re.sub(re.escape(alias), "", text, flags=re.I)
    text = re.sub(r"\b(is|are|was|were|means|refers to|typically|usually|often|framed as)\b", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" ,;:-")


def _clause_after_subject(sentence: str, aliases: list[str]) -> str:
    lowered = sentence.lower()
    for alias in sorted(aliases, key=len, reverse=True):
        idx = lowered.find(alias.lower())
        if idx >= 0:
            fragment = sentence[idx + len(alias) :]
            fragment = re.sub(r"^\s*(is|are|was|were|means|refers to|typically|usually|often|framed as)\s+", "", fragment, flags=re.I)
            fragment = fragment.strip(" ,;:-")
            if fragment:
                return fragment
    return sentence


def _sentence_side(sentence: str, left_aliases: list[str], right_aliases: list[str]) -> str:
    lowered = sentence.lower()
    left_hits = sum(1 for alias in left_aliases if alias in lowered)
    right_hits = sum(1 for alias in right_aliases if alias in lowered)
    if left_hits > right_hits:
        return "left"
    if right_hits > left_hits:
        return "right"
    if left_hits and right_hits:
        return "both"
    return "neutral"


def _subject_aliases(subject: str) -> list[str]:
    lowered = subject.lower()
    aliases = [lowered, subject]
    if "no dac" in lowered or "no-dac" in lowered:
        aliases.extend(["no dac", "no-dac", "ipa", "ipamorelin", "paired", "dual", "combination", "mod grf"])
    if "cjc" in lowered and "no dac" not in lowered and "no-dac" not in lowered:
        aliases.extend(["dac", "dac-modified", "dac-containing", "long-acting", "albumin-binding"])
    if "retatrutide" in lowered:
        aliases.extend(["glp-1", "gip", "glucagon", "triple agonist"])
    if "tirzepatide" in lowered:
        aliases.extend(["glp-1", "gip", "dual agonist", "twincretin"])
    return list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))


def _normalize_cell(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\s+unless\b.*$", "", text, flags=re.I)
    text = re.sub(
        r"^(as a|to the|usually points to the|typically framed as|often studied for|is typically framed as)\s+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    words = text.split()
    if len(words) > _MAX_CELL_WORDS:
        text = " ".join(words[:_MAX_CELL_WORDS])
    return text.strip(" ,;:-")


def _clean_subject(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -:,")


def _split_sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", value.strip())
    return [part.strip() for part in parts if part.strip()]
