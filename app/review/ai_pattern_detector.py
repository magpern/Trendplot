import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import pstdev
from typing import Any

from app.article_schema import ArticleSchema


AI_AUTHORITY_PHRASES = (
    "rapidly evolving field",
    "pivotal area",
    "delves into",
    "fascinating",
    "unlocking potential",
    "game-changer",
    "exciting prospects",
    "in today's",
    "it is important to note",
    "as discussed above",
    "plays a crucial role",
    "shed light on",
    "robust",
    "meticulous",
    "central to",
    "critical for",
    "underscores",
    "highlights",
    "leverages",
    "provides insights",
)

FORMULAIC_TRANSITIONS = (
    "in addition",
    "furthermore",
    "moreover",
    "therefore",
    "as a result",
    "on the other hand",
    "in conclusion",
    "overall",
    "this section",
    "this article",
    "researchers should",
    "it is important",
    "reliable experiments",
)

DISCLAIMER_HINTS = (
    "for research use only",
    "not intended for human consumption",
    "therapeutic, or diagnostic use",
)

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "when",
    "where",
    "which",
    "their",
    "there",
    "should",
    "could",
    "would",
}


@dataclass(slots=True)
class AIPatternReport:
    score: int
    severity: str
    repeated_sentence_openings: list[dict[str, Any]] = field(default_factory=list)
    repetitive_transitions: list[dict[str, Any]] = field(default_factory=list)
    repeated_phrases: list[dict[str, Any]] = field(default_factory=list)
    ai_authority_phrases: list[dict[str, Any]] = field(default_factory=list)
    disclaimer_repetition: dict[str, Any] = field(default_factory=dict)
    robotic_cadence: dict[str, Any] = field(default_factory=dict)
    identical_paragraph_lengths: list[dict[str, Any]] = field(default_factory=list)
    repeated_section_structures: list[dict[str, Any]] = field(default_factory=list)
    section_scores: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "severity": self.severity,
            "repeated_sentence_openings": self.repeated_sentence_openings,
            "repetitive_transitions": self.repetitive_transitions,
            "repeated_phrases": self.repeated_phrases,
            "ai_authority_phrases": self.ai_authority_phrases,
            "disclaimer_repetition": self.disclaimer_repetition,
            "robotic_cadence": self.robotic_cadence,
            "identical_paragraph_lengths": self.identical_paragraph_lengths,
            "repeated_section_structures": self.repeated_section_structures,
            "section_scores": self.section_scores,
            "warnings": self.warnings,
        }


class AIPatternDetector:
    def analyze(
        self,
        article: ArticleSchema,
        *,
        required_disclaimer: str = "",
    ) -> AIPatternReport:
        text_locations = _section_locations(article)
        markdown = _style_text("\n\n".join(location["text"] for location in text_locations))
        sentences = _sentences(markdown)
        paragraphs = _paragraphs(markdown)
        repeated_openings = _repeated_sentence_openings(sentences)
        transitions = _phrase_counts(markdown, FORMULAIC_TRANSITIONS, threshold=2)
        authority = _phrase_counts(markdown, AI_AUTHORITY_PHRASES, threshold=1)
        repeated_phrases = _repeated_phrases(markdown)
        disclaimer = _disclaimer_repetition(markdown, required_disclaimer)
        cadence = _cadence_report(sentences)
        paragraph_lengths = _identical_paragraph_lengths(paragraphs)
        structures = _repeated_section_structures(article)
        section_scores = [_section_score(item) for item in text_locations]

        raw_score = (
            min(24, len(repeated_openings) * 5)
            + min(18, sum(item["count"] for item in transitions) * 2)
            + min(18, sum(item["count"] for item in authority) * 2)
            + min(18, len(repeated_phrases) * 4)
            + int(cadence.get("score", 0))
            + min(10, len(paragraph_lengths) * 3)
            + min(12, len(structures) * 4)
            + int(disclaimer.get("score", 0))
        )
        score = min(100, raw_score)
        warnings = []
        if score >= 70:
            warnings.append("High AI-pattern score; use deep editorial rewrite for the worst sections.")
        elif score >= 40:
            warnings.append("Moderate AI-pattern score; section-level editorial rewrite is recommended.")
        if disclaimer.get("count", 0) > 2:
            warnings.append("Disclaimer language appears repeatedly and should be consolidated.")

        return AIPatternReport(
            score=score,
            severity=_severity(score),
            repeated_sentence_openings=repeated_openings,
            repetitive_transitions=transitions,
            repeated_phrases=repeated_phrases,
            ai_authority_phrases=authority,
            disclaimer_repetition=disclaimer,
            robotic_cadence=cadence,
            identical_paragraph_lengths=paragraph_lengths,
            repeated_section_structures=structures,
            section_scores=section_scores,
            warnings=warnings,
        )


def _section_locations(article: ArticleSchema) -> list[dict[str, str]]:
    locations: list[dict[str, str]] = []
    if article.excerpt:
        locations.append({"section_id": "intro", "heading": "Intro", "text": article.excerpt})
    if article.research_context:
        locations.append({"section_id": "research_context", "heading": "Research Context", "text": article.research_context})
    for index, section in enumerate(article.sections):
        if section.content_markdown:
            locations.append({"section_id": f"section:{index}", "heading": section.heading, "text": section.content_markdown})
        for sub_index, subsection in enumerate(section.subsections):
            if subsection.content_markdown:
                locations.append(
                    {
                        "section_id": f"subsection:{index}:{sub_index}",
                        "heading": subsection.heading,
                        "text": subsection.content_markdown,
                    }
                )
    for index, item in enumerate(article.faq):
        if item.answer:
            locations.append({"section_id": f"faq:{index}", "heading": item.question, "text": item.answer})
    for index, item in enumerate(article.callout_boxes):
        if item.message:
            locations.append({"section_id": f"callout:{index}", "heading": item.title, "text": item.message})
    for index, item in enumerate(article.caution_boxes):
        if item.message:
            locations.append({"section_id": f"caution:{index}", "heading": item.title, "text": item.message})
    for index, item in enumerate(article.research_insights):
        if item.insight:
            locations.append({"section_id": f"research_insight:{index}:insight", "heading": item.title, "text": item.insight})
        if item.limitation:
            locations.append(
                {"section_id": f"research_insight:{index}:limitation", "heading": item.title, "text": item.limitation}
            )
    for index, item in enumerate(article.study_cards):
        if item.observed_finding:
            locations.append({"section_id": f"study_card:{index}:observed_finding", "heading": item.title, "text": item.observed_finding})
        if item.limitation:
            locations.append({"section_id": f"study_card:{index}:limitation", "heading": item.title, "text": item.limitation})
        if item.verification_needed:
            locations.append(
                {"section_id": f"study_card:{index}:verification_needed", "heading": item.title, "text": item.verification_needed}
            )
    for index, item in enumerate(article.definition_boxes):
        if item.definition:
            locations.append({"section_id": f"definition:{index}", "heading": item.term, "text": item.definition})
    for index, item in enumerate(article.related_topics):
        if item.angle:
            locations.append({"section_id": f"related_topic:{index}", "heading": item.title, "text": item.angle})
    if article.limitations_and_safety:
        locations.append(
            {
                "section_id": "limitations_and_safety",
                "heading": "Limitations and Safety Notes",
                "text": article.limitations_and_safety,
            }
        )
    return locations


def _section_score(location: dict[str, str]) -> dict[str, Any]:
    text = _style_text(location["text"])
    sentences = _sentences(text)
    signals: list[str] = []
    score = 0
    if _repeated_sentence_openings(sentences):
        score += 25
        signals.append("repeated_sentence_openings")
    if _phrase_counts(text, FORMULAIC_TRANSITIONS, threshold=1):
        score += 20
        signals.append("formulaic_transitions")
    if _phrase_counts(text, AI_AUTHORITY_PHRASES, threshold=1):
        score += 20
        signals.append("ai_authority_phrases")
    if len(_repeated_phrases(text)) >= 2:
        score += 20
        signals.append("repeated_phrases")
    cadence = _cadence_report(sentences)
    if cadence.get("score", 0) >= 8:
        score += 15
        signals.append("robotic_cadence")
    return {
        "section_id": location["section_id"],
        "heading": location["heading"],
        "score": min(100, score),
        "signals": signals,
    }


def _sentences(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", value) if item.strip()]


def _style_text(value: str) -> str:
    without_link_targets = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    without_urls = re.sub(r"https?://\S+", " ", without_link_targets)
    return re.sub(r"\s+", " ", without_urls).strip()


def _paragraphs(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n{2,}", value) if len(item.split()) >= 8]


def _repeated_sentence_openings(sentences: list[str]) -> list[dict[str, Any]]:
    openings = []
    for sentence in sentences:
        words = re.findall(r"\b[a-z][a-z'-]*\b", sentence.lower())[:4]
        if len(words) >= 2:
            openings.append(" ".join(words[: min(3, len(words))]))
    counts = Counter(openings)
    return [{"opening": opening, "count": count} for opening, count in counts.most_common(12) if count > 1]


def _phrase_counts(value: str, phrases: tuple[str, ...], threshold: int) -> list[dict[str, Any]]:
    lower = value.lower()
    found = []
    for phrase in phrases:
        count = len(re.findall(re.escape(phrase), lower, flags=re.IGNORECASE))
        if count >= threshold:
            found.append({"phrase": phrase, "count": count})
    return sorted(found, key=lambda item: item["count"], reverse=True)


def _repeated_phrases(value: str) -> list[dict[str, Any]]:
    tokens = [token.lower() for token in re.findall(r"\b[a-z][a-z0-9'-]+\b", value)]
    ngrams = []
    for size in (3, 4, 5):
        for index in range(0, max(0, len(tokens) - size + 1)):
            chunk = tokens[index : index + size]
            if any(token in STOPWORDS for token in chunk[:1]) and any(token in STOPWORDS for token in chunk[-1:]):
                continue
            phrase = " ".join(chunk)
            if len(set(chunk)) <= 1:
                continue
            ngrams.append(phrase)
    counts = Counter(ngrams)
    return [
        {"phrase": phrase, "count": count}
        for phrase, count in counts.most_common(15)
        if count >= 3 and not all(token in STOPWORDS for token in phrase.split())
    ]


def _disclaimer_repetition(value: str, required_disclaimer: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", value).strip().lower()
    required = re.sub(r"\s+", " ", required_disclaimer).strip().lower()
    if required:
        count = normalized.count(required)
    else:
        count = max(normalized.count(hint) for hint in DISCLAIMER_HINTS)
    return {"count": count, "score": min(12, max(0, count - 1) * 4)}


def _cadence_report(sentences: list[str]) -> dict[str, Any]:
    lengths = [len(re.findall(r"\b[\w'-]+\b", sentence)) for sentence in sentences if sentence]
    if len(lengths) < 4:
        return {"score": 0, "sentence_count": len(lengths), "average_sentence_words": 0, "length_stdev": 0}
    average = sum(lengths) / len(lengths)
    deviation = pstdev(lengths)
    score = 0
    if 14 <= average <= 25 and deviation <= 5:
        score += 10
    if len(set(lengths)) <= max(3, len(lengths) // 4):
        score += 6
    return {
        "score": score,
        "sentence_count": len(lengths),
        "average_sentence_words": round(average, 1),
        "length_stdev": round(deviation, 1),
    }


def _identical_paragraph_lengths(paragraphs: list[str]) -> list[dict[str, Any]]:
    lengths = [len(re.findall(r"\b[\w'-]+\b", paragraph)) for paragraph in paragraphs]
    rounded = Counter((length // 10) * 10 for length in lengths)
    return [{"word_count_bucket": bucket, "count": count} for bucket, count in rounded.items() if count >= 3]


def _repeated_section_structures(article: ArticleSchema) -> list[dict[str, Any]]:
    patterns = []
    for section in article.sections:
        sentences = _sentences(section.content_markdown)
        if not sentences:
            continue
        first = re.sub(r"[^a-z ]+", "", sentences[0].lower())
        opener = " ".join(first.split()[:4])
        paragraph_count = len(_paragraphs(section.content_markdown))
        patterns.append((opener, paragraph_count, section.heading))
    counts = Counter((opener, paragraph_count) for opener, paragraph_count, _ in patterns if opener)
    repeated = []
    for (opener, paragraph_count), count in counts.items():
        if count <= 1:
            continue
        headings = [heading for pattern, paragraphs, heading in patterns if pattern == opener and paragraphs == paragraph_count]
        repeated.append(
            {
                "opening_pattern": opener,
                "paragraph_count": paragraph_count,
                "count": count,
                "headings": headings,
            }
        )
    return repeated


def _severity(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "minimal"
