from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

POWER_WORDS = ("Key", "Important", "Essential", "Practical", "Clear", "Research")
_SLUG_FILLER = frozenset({"the", "a", "an", "for", "and", "or", "to", "of", "in", "on", "with"})
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize_keyword(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def keyword_in_text(text: str, keyword: str) -> bool:
    keyword = normalize_keyword(keyword)
    if not keyword or not text:
        return False
    pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
    if pattern.search(text):
        return True
    compact = keyword.replace(" vs ", " ").replace(" vs. ", " ")
    if compact != keyword:
        pattern = re.compile(rf"(?<!\w){re.escape(compact)}(?!\w)", re.IGNORECASE)
        if pattern.search(text):
            return True
    return False


def count_keyword_occurrences(text: str, keyword: str) -> int:
    keyword = normalize_keyword(keyword)
    if not keyword or not text:
        return 0
    pattern = re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)
    return len(pattern.findall(text))


def tokenize_phrase(text: str) -> list[str]:
    normalized = re.sub(r"\s+vs\.?\s+", " ", str(text or ""), flags=re.IGNORECASE)
    return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(normalized)]


def collect_body_markdown(article: dict[str, Any]) -> str:
    parts: list[str] = []
    excerpt = str(article.get("excerpt") or "").strip()
    if excerpt:
        parts.append(excerpt)
    for section in article.get("sections") or []:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        if heading:
            parts.append(heading)
        content = str(section.get("content_markdown") or "").strip()
        if content:
            parts.append(content)
        for subsection in section.get("subsections") or []:
            if not isinstance(subsection, dict):
                continue
            sub_heading = str(subsection.get("heading") or "").strip()
            if sub_heading:
                parts.append(sub_heading)
            sub_content = str(subsection.get("content_markdown") or "").strip()
            if sub_content:
                parts.append(sub_content)
    for item in article.get("faq") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("question") or ""))
            parts.append(str(item.get("answer") or ""))
    return "\n\n".join(part for part in parts if part.strip())


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def target_keyword_range(body_words: int) -> tuple[int, int]:
    if body_words > 2000:
        return 3, 5
    if body_words > 800:
        return 3, 3
    return 2, 2


def has_power_word(title: str) -> bool:
    lowered = str(title or "").lower()
    return any(word.lower() in lowered for word in POWER_WORDS)


def improve_seo_title(title: str, keyword: str) -> tuple[str, bool]:
    updated = normalize_keyword(title)
    changed = False
    if not updated and keyword:
        updated = keyword
        changed = True
    if keyword and not keyword_in_text(updated, keyword):
        if len(updated) <= 42:
            updated = f"{keyword}: {updated}"
        else:
            updated = f"{updated} | {keyword}"
        changed = True
    if not has_power_word(updated):
        suffix = "Key Research Differences" if " vs " in keyword.lower() else "Key Research Overview"
        candidate = f"{updated}: {suffix}"
        if len(candidate) <= 70:
            updated = candidate
        elif len(updated) <= 58:
            updated = f"{updated}: Key Research"
        changed = True
    if len(updated) > 70:
        updated = updated[:67].rstrip(" -:|") + "..."
        changed = True
    return updated, changed


def improve_meta_description(description: str, keyword: str) -> tuple[str, bool]:
    updated = normalize_keyword(description)
    changed = False
    if not updated:
        updated = (
            f"A clear research overview of {keyword} for laboratory contexts. "
            "For research use only (RUO); not for human or veterinary use."
        )
        return updated[:160].rstrip(), True
    if keyword and not keyword_in_text(updated, keyword):
        updated = f"{keyword}. {updated}"
        changed = True
    if len(updated) < 130:
        extra = " For research use only (RUO) contexts."
        if extra.strip() not in updated:
            updated = updated.rstrip(".") + "." + extra
            changed = True
    if len(updated) > 160:
        updated = updated[:157].rstrip(" ,.;") + "..."
        changed = True
    return updated, changed


def resolve_site_base_url(
    *,
    site_base_url: str = "",
    wordpress_public_url: str = "",
    existing_canonical: str = "",
) -> str:
    for candidate in (site_base_url, wordpress_public_url, existing_canonical):
        text = str(candidate or "").strip()
        if not text.startswith(("http://", "https://")):
            continue
        parsed = urlparse(text)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return ""


def recommend_canonical_url(
    slug: str,
    *,
    existing_canonical: str = "",
    wordpress_public_url: str = "",
    site_base_url: str = "",
    max_path_chars: int = 55,
) -> str | None:
    normalized_slug = str(slug or "").strip().strip("/")
    if not normalized_slug:
        return None

    base = resolve_site_base_url(
        site_base_url=site_base_url,
        wordpress_public_url=wordpress_public_url,
        existing_canonical=existing_canonical,
    )
    if not base:
        return None

    recommended = f"{base}/{normalized_slug}/"
    existing = str(existing_canonical or "").strip()
    if not existing:
        return recommended

    existing_path = urlparse(existing).path.strip("/")
    if not existing_path:
        return recommended
    if len(existing_path) <= max(len(normalized_slug), max_path_chars) and normalized_slug in existing_path.lower():
        return None
    if len(existing_path) > max_path_chars or len(existing) > len(recommended) + 5:
        return recommended
    return None


def recommend_slug(keyword: str, title: str) -> str:
    source = normalize_keyword(keyword) or normalize_keyword(title)
    lowered = source.lower()
    lowered = re.sub(r"[^\w\s-]", "", lowered)
    lowered = re.sub(r"\s+", "-", lowered.strip())
    parts = [part for part in lowered.split("-") if part and part not in _SLUG_FILLER]
    if not parts:
        parts = [re.sub(r"[^\w]+", "", token) for token in tokenize_phrase(source) if token]
    slug = "-".join(parts[:8])
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")
    return slug


def suggest_image_alts(keyword: str, title: str) -> dict[str, str]:
    focus = normalize_keyword(keyword) or normalize_keyword(title) or "research article"
    return {
        "suggested_featured_image_alt": f"{focus} research comparison diagram",
        "suggested_inline_image_alt": f"{focus} illustration for research context",
    }


def insert_keyword_in_text(text: str, keyword: str, *, max_additions: int = 1) -> tuple[str, int]:
    if not text.strip() or not keyword.strip():
        return text, 0
    if keyword_in_text(text, keyword):
        return text, 0
    additions = 0
    sentences = _SENTENCE_SPLIT.split(text.strip())
    if not sentences:
        return text, 0
    first = sentences[0].rstrip()
    if not keyword_in_text(first, keyword):
        connector = "" if first.endswith((":", ";")) else "."
        sentences[0] = f"{first}{connector} This overview centers on {keyword} in research discussions."
        additions += 1
    if additions >= max_additions:
        return " ".join(sentences), additions
    for index in range(1, len(sentences)):
        if additions >= max_additions:
            break
        if keyword_in_text(sentences[index], keyword):
            continue
        sentence = sentences[index].rstrip()
        if len(sentence.split()) < 6:
            continue
        sentences[index] = f"{sentence} Researchers also reference {keyword} when comparing related compounds."
        additions += 1
        break
    return " ".join(sentences), additions


def split_long_paragraphs(text: str, *, max_words: int = 140) -> tuple[str, int]:
    if not text.strip():
        return text, 0
    blocks = text.split("\n\n")
    rebuilt: list[str] = []
    splits = 0
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            rebuilt.append(block)
            continue
        if stripped.startswith(("#", "|", "-", "*", ">")) or "RUO" in stripped or "research use only" in stripped.lower():
            rebuilt.append(block)
            continue
        words = stripped.split()
        if len(words) <= max_words:
            rebuilt.append(block)
            continue
        sentences = _SENTENCE_SPLIT.split(stripped)
        if len(sentences) < 2:
            rebuilt.append(block)
            continue
        current: list[str] = []
        current_words = 0
        chunk_parts: list[str] = []
        for sentence in sentences:
            sentence_words = len(sentence.split())
            if current and current_words + sentence_words > max_words:
                chunk_parts.append(" ".join(current))
                current = [sentence]
                current_words = sentence_words
                splits += 1
            else:
                current.append(sentence)
                current_words += sentence_words
        if current:
            chunk_parts.append(" ".join(current))
        rebuilt.append("\n\n".join(chunk_parts))
    return "\n\n".join(rebuilt), splits
