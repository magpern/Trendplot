import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from app.article_schema import ArticleSchema, normalize_article
from app.rules.compliance_rules import DEFAULT_COMPLIANCE_RULES, SAFE_STORAGE_HANDLING_FALLBACK


@dataclass(slots=True)
class SanityFinding:
    code: str
    severity: str
    message: str
    matched_text: str
    location: str
    suggested_replacement: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "matched_text": self.matched_text,
            "location": self.location,
            "suggested_replacement": self.suggested_replacement,
        }


@dataclass(slots=True)
class SanityCheckReport:
    passed: bool
    blocking_errors: list[SanityFinding] = field(default_factory=list)
    warnings: list[SanityFinding] = field(default_factory=list)
    suggested_replacements: list[dict[str, str]] = field(default_factory=list)
    rules_summary: list[str] = field(default_factory=list)
    status: str = "passed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blocking_errors": [finding.as_dict() for finding in self.blocking_errors],
            "warnings": [finding.as_dict() for finding in self.warnings],
            "suggested_replacements": self.suggested_replacements,
            "rules_summary": self.rules_summary,
            "status": self.status,
        }


STORAGE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "unsupported_storage_temperature",
        re.compile(
            "\\b(?:store|stored|keep|kept|storage)\\b[^.\\n]{0,80}?"
            "(?:-|minus\\s*)?\\d{1,3}\\s*(?:\\u00b0|deg|degrees?)?\\s*c\\b",
            re.I,
        ),
        "Specific storage temperatures should be framed as source-dependent handling information.",
    ),
    (
        "unsupported_reconstitution",
        re.compile(r"\breconstitut(?:e|ed|ion)\b[^.\n]{0,80}\b(?:with|using|in|store|stored|keep|kept)\b", re.I),
        "Reconstitution instructions should be framed as source-dependent handling information.",
    ),
    (
        "unsupported_aliquot_freezing",
        re.compile(
            r"\b(?:aliquot(?:s|ed|ing)?\s+(?:should|must|can|may)|freeze(?:r|s|ing)?\s+at|frozen\s+at|kept\s+at\s+-?\d)",
            re.I,
        ),
        "Aliquoting and freezing instructions should be framed as source-dependent handling information.",
    ),
    (
        "unsupported_degradation_claim",
        re.compile(r"\b(?:prevent|avoid|stop)\s+degradation\b|\bdegrade(?:s|d)?\s+(?:at|when stored)\b", re.I),
        "Degradation claims should be framed as source-dependent handling information.",
    ),
    (
        "unsafe_mixing_temperature",
        re.compile(
            r"\b(?:mix|dissolve|reconstitut(?:e|ed|ion))\b[^.\n]{0,100}(?:-?80\s*(?:°|deg|degrees?)?\s*c|water)[^.\n]{0,100}(?:water|-?80\s*(?:°|deg|degrees?)?\s*c)",
            re.I,
        ),
        "Operationally impossible or unsafe mixing instructions should be removed.",
    ),
)

DOSING_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "human_dosing_guidance",
        re.compile(
            r"\b(?:recommended dose|dosage|human dosing|administer|administration|inject(?:ed|ion|ing)?|take\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ug|g|ml))\b",
            re.I,
        ),
        "Human dosing or administration instructions are not appropriate for research-use-only informational content.",
    ),
    (
        "patient_or_clinical_instruction",
        re.compile(r"\b(?:for patients|in patients|clinical use|human use|human consumption|safe for human use)\b", re.I),
        "Patient, clinical-use, or human-use instructions are not appropriate for research-use-only informational content.",
    ),
)

THERAPEUTIC_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "therapeutic_claim",
        re.compile(
            r"\b(?:treats|cures|cure|heals|prevents disease|is a treatment for|used to treat|for treating)\b",
            re.I,
        ),
        "Therapeutic claims must not be presented as established product uses.",
    ),
)

WARNING_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = ()

SAFE_NEGATION_PREFIXES = (
    "not intended for ",
    "not for ",
    "not approved for ",
    "do not ",
    "must not ",
    "should not ",
    "without ",
    "avoid ",
    "avoids ",
    "no ",
    "non-",
    "does not provide ",
    "not provide ",
)


class ArticleSanityChecker:
    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or DEFAULT_COMPLIANCE_RULES
        self.safe_storage_fallback = str(
            self.rules.get("safe_storage_handling_fallback") or SAFE_STORAGE_HANDLING_FALLBACK
        )

    def check(
        self,
        article: ArticleSchema | dict[str, Any],
        rendered_html: str = "",
        product_data: dict[str, Any] | None = None,
    ) -> SanityCheckReport:
        article_dict = article.model_dump() if hasattr(article, "model_dump") else dict(article or {})
        product_data = product_data or {}
        approved_storage_claims = self._approved_claims(product_data, "storage")
        approved_handling_claims = self._approved_claims(product_data, "handling")
        text_locations = self._article_text_locations(article_dict)
        if rendered_html and not any(text.strip() for _, text in text_locations):
            text_locations.append(("rendered_html", html_to_text(rendered_html)))

        blocking_errors: list[SanityFinding] = []
        warnings: list[SanityFinding] = []
        suggested_replacements: list[dict[str, str]] = []

        for location, text in text_locations:
            if not text.strip():
                continue

            for code, pattern, message in STORAGE_PATTERNS:
                for match in pattern.finditer(text):
                    matched = match.group(0)
                    if self._has_cautious_storage_context(text, match.start()):
                        continue
                    if self._is_approved_claim(matched, approved_storage_claims + approved_handling_claims):
                        continue
                    if self._is_approved_claim(
                        self._sentence_around(text, match.start()),
                        approved_storage_claims + approved_handling_claims,
                    ):
                        continue
                    finding = SanityFinding(
                        code=code,
                        severity="blocking",
                        message=message,
                        matched_text=matched,
                        location=location,
                        suggested_replacement=self.safe_storage_fallback,
                    )
                    blocking_errors.append(finding)
                    suggested_replacements.append(
                        {
                            "location": location,
                            "matched_text": matched,
                            "replacement": self.safe_storage_fallback,
                        }
                    )

            for code, pattern, message in DOSING_PATTERNS:
                for match in pattern.finditer(text):
                    matched = match.group(0)
                    if self._has_safe_negation(text, match.start()) or self._is_question_context(text, match.start()):
                        continue
                    blocking_errors.append(
                        SanityFinding(
                            code=code,
                            severity="blocking",
                            message=message,
                            matched_text=matched,
                            location=location,
                            suggested_replacement="Remove dosing, administration, patient, or clinical-use guidance.",
                        )
                    )

            for code, pattern, message in THERAPEUTIC_PATTERNS:
                for match in pattern.finditer(text):
                    matched = match.group(0)
                    if self._has_safe_negation(text, match.start()):
                        continue
                    blocking_errors.append(
                        SanityFinding(
                            code=code,
                            severity="blocking",
                            message=message,
                            matched_text=matched,
                            location=location,
                            suggested_replacement="Use research-context language without therapeutic or human-use claims.",
                        )
                    )

            for code, pattern, message in WARNING_PATTERNS:
                for match in pattern.finditer(text):
                    if self._has_cautious_storage_context(text, match.start()):
                        continue
                    warnings.append(
                        SanityFinding(
                            code=code,
                            severity="warning",
                            message=message,
                            matched_text=match.group(0),
                            location=location,
                            suggested_replacement=None,
                        )
                    )

            if "storage" in text.lower() or "handling" in text.lower():
                if not approved_storage_claims and not approved_handling_claims and self.safe_storage_fallback not in text:
                    warnings.append(
                        SanityFinding(
                            code="storage_handling_needs_source",
                            severity="warning",
                            message="Storage or handling guidance should be framed as source-dependent and verified against supplier documentation.",
                            matched_text="storage/handling",
                            location=location,
                            suggested_replacement=self.safe_storage_fallback,
                        )
                    )

        blocking_errors = _dedupe_findings(blocking_errors)
        warnings = _dedupe_findings(warnings)
        return SanityCheckReport(
            passed=not blocking_errors,
            blocking_errors=blocking_errors,
            warnings=warnings,
            suggested_replacements=_dedupe_replacements(suggested_replacements),
            rules_summary=list(self.rules.get("rules", [])),
            status="passed" if not blocking_errors else "failed_sanity",
        )

    def rewrite_blocking_claims(
        self,
        article: ArticleSchema,
        report: SanityCheckReport,
        defaults: dict[str, str],
    ) -> tuple[ArticleSchema, dict[str, Any]]:
        if not report.blocking_errors:
            return article, {"attempted": False, "changed_locations": [], "reason": "No blocking sanity findings found."}

        data = article.model_dump()
        changed_locations: list[str] = []

        if self._location_has_blocking_error(report, "title"):
            data["title"] = self._rewrite_sanity_text(str(data.get("title") or ""), "title")
            changed_locations.append("title")

        for section in data.get("sections", []):
            location = f"section:{section.get('heading') or 'Untitled'}"
            if self._location_has_blocking_error(report, location):
                section["content_markdown"] = self._rewrite_sanity_text(str(section.get("content_markdown") or ""), location)
                changed_locations.append(location)

        if self._location_has_blocking_error(report, "limitations_and_safety"):
            data["limitations_and_safety"] = self._rewrite_sanity_text(
                str(data.get("limitations_and_safety") or ""),
                "limitations_and_safety",
            )
            changed_locations.append("limitations_and_safety")

        if self._location_has_blocking_error(report, "research_context"):
            data["research_context"] = self._rewrite_sanity_text(
                str(data.get("research_context") or ""),
                "research_context",
            )
            changed_locations.append("research_context")

        if self._location_has_blocking_error(report, "excerpt"):
            data["excerpt"] = self._rewrite_sanity_text(str(data.get("excerpt") or ""), "excerpt")
            changed_locations.append("excerpt")

        if self._location_has_blocking_error(report, "key_takeaways"):
            updated_takeaways = []
            for item in data.get("key_takeaways") or []:
                text = str(item)
                if self._has_blocking_sanity_text(text):
                    updated_takeaways.append(self._safe_research_fallback("key_takeaways"))
                else:
                    updated_takeaways.append(item)
            data["key_takeaways"] = updated_takeaways
            changed_locations.append("key_takeaways")

        if self._location_has_blocking_error(report, "faq"):
            for item in data.get("faq") or []:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question") or "")
                answer = str(item.get("answer") or "")
                if self._has_blocking_sanity_text(f"{question} {answer}"):
                    if self._has_blocking_sanity_text(question):
                        item["question"] = "How should this information be interpreted?"
                    item["answer"] = self._rewrite_sanity_text(answer, "faq")
                    changed_locations.append("faq")

        rewritten = normalize_article(data, defaults=defaults)
        attempted = bool(changed_locations)
        return rewritten, {
            "attempted": attempted,
            "changed_locations": changed_locations,
            "safe_fallback": self.safe_storage_fallback,
            "reason": (
                "Blocking sanity findings were rewritten with research-context-safe wording."
                if attempted
                else "Rewrite was attempted, but no directly editable blocking sanity locations were found."
            ),
        }

    def rewrite_unsupported_storage_claims(
        self,
        article: ArticleSchema,
        report: SanityCheckReport,
        defaults: dict[str, str],
    ) -> tuple[ArticleSchema, dict[str, Any]]:
        return self.rewrite_blocking_claims(article=article, report=report, defaults=defaults)

    def remove_blocking_claims(
        self,
        article: ArticleSchema,
        report: SanityCheckReport,
        defaults: dict[str, str],
    ) -> tuple[ArticleSchema, dict[str, Any]]:
        if not report.blocking_errors:
            return article, {"attempted": False, "changed_locations": [], "reason": "No blocking sanity findings found."}

        data = article.model_dump()
        changed_locations: list[str] = []

        if self._location_has_blocking_error(report, "title"):
            data["title"] = defaults.get("title") or "Research-context overview"
            changed_locations.append("title")

        for section in data.get("sections", []):
            location = f"section:{section.get('heading') or 'Untitled'}"
            if self._location_has_blocking_error(report, location):
                section["content_markdown"] = self._remove_blocking_sentences(
                    str(section.get("content_markdown") or ""),
                    location,
                )
                changed_locations.append(location)

        for field_name in ("excerpt", "research_context", "limitations_and_safety"):
            if self._location_has_blocking_error(report, field_name):
                data[field_name] = self._remove_blocking_sentences(str(data.get(field_name) or ""), field_name)
                changed_locations.append(field_name)

        if self._location_has_blocking_error(report, "key_takeaways"):
            data["key_takeaways"] = [
                item
                for item in data.get("key_takeaways") or []
                if not self._has_blocking_sanity_text(str(item))
            ] or [self._safe_research_fallback("key_takeaways")]
            changed_locations.append("key_takeaways")

        if self._location_has_blocking_error(report, "faq"):
            for item in data.get("faq") or []:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question") or "")
                answer = str(item.get("answer") or "")
                if self._has_blocking_sanity_text(f"{question} {answer}"):
                    item["question"] = "How should this information be interpreted?"
                    item["answer"] = self._safe_research_fallback("faq")
                    changed_locations.append("faq")

        rewritten = normalize_article(data, defaults=defaults)
        return rewritten, {
            "attempted": bool(changed_locations),
            "changed_locations": changed_locations,
            "reason": (
                "Remaining blocking sanity findings were removed with neutral research-context wording."
                if changed_locations
                else "No directly editable blocking sanity locations were found."
            ),
        }

    def _article_text_locations(self, article: dict[str, Any]) -> list[tuple[str, str]]:
        locations = [
            ("title", str(article.get("title") or "")),
            ("excerpt", str(article.get("excerpt") or "")),
            ("research_context", str(article.get("research_context") or "")),
            ("limitations_and_safety", str(article.get("limitations_and_safety") or "")),
        ]
        for section in article.get("sections") or []:
            if hasattr(section, "model_dump"):
                section = section.model_dump()
            if isinstance(section, dict):
                heading = str(section.get("heading") or "Untitled")
                locations.append((f"section:{heading}", str(section.get("content_markdown") or "")))
        for item in article.get("key_takeaways") or []:
            locations.append(("key_takeaways", str(item)))
        for item in article.get("faq") or []:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if isinstance(item, dict):
                locations.append(("faq", f"{item.get('question') or ''} {item.get('answer') or ''}"))
        return locations

    def _approved_claims(self, product_data: dict[str, Any], claim_type: str) -> list[str]:
        product_claims = product_data.get(f"approved_{claim_type}_claims")
        if isinstance(product_claims, list):
            return [str(claim) for claim in product_claims if str(claim).strip()]
        rules_claims = self.rules.get(f"approved_{claim_type}_claims")
        if isinstance(rules_claims, list):
            return [str(claim) for claim in rules_claims if str(claim).strip()]
        return []

    def _is_approved_claim(self, matched_text: str, approved_claims: list[str]) -> bool:
        normalized_match = _normalize(matched_text)
        return any(normalized_match in _normalize(claim) or _normalize(claim) in normalized_match for claim in approved_claims)

    def _has_safe_negation(self, text: str, match_start: int) -> bool:
        prefix = text[max(0, match_start - 120) : match_start].lower()
        return any(negation in prefix for negation in SAFE_NEGATION_PREFIXES)

    def _is_question_context(self, text: str, match_start: int) -> bool:
        sentence = self._sentence_around(text, match_start)
        return sentence.strip().endswith("?")

    def _has_cautious_storage_context(self, text: str, match_start: int) -> bool:
        sentence = self._sentence_around(text, match_start).lower()
        cautious_markers = (
            "commonly described",
            "reported",
            "may vary",
            "supplier",
            "certificate of analysis",
            "coa",
            "label",
            "documentation",
            "verify",
            "source-dependent",
            "can vary",
        )
        return any(marker in sentence for marker in cautious_markers)

    def _sentence_around(self, text: str, match_start: int) -> str:
        start_candidates = [text.rfind(separator, 0, match_start) for separator in ".!?\n"]
        start = max(start_candidates) + 1
        end_candidates = [index for index in (text.find(separator, match_start) for separator in ".!?\n") if index != -1]
        end = min(end_candidates) + 1 if end_candidates else len(text)
        return text[start:end].strip()

    def _location_has_storage_error(self, report: SanityCheckReport, location: str) -> bool:
        return any(
            finding.location == location and finding.code.startswith("unsupported_")
            for finding in report.blocking_errors
        )

    def _location_has_blocking_error(self, report: SanityCheckReport, location: str) -> bool:
        return any(finding.location == location for finding in report.blocking_errors)

    def _location_has_rewritable_storage_error(self, report: SanityCheckReport, location: str) -> bool:
        return any(
            finding.location == location
            and finding.code
            in {
                "unsupported_storage_temperature",
                "unsupported_reconstitution",
                "unsupported_aliquot_freezing",
            }
            for finding in report.blocking_errors
        )

    def _rewrite_sanity_text(self, value: str, location: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        rewritten: list[str] = []
        for sentence in sentences:
            if not sentence.strip():
                continue
            if not self._has_blocking_sanity_text(sentence):
                rewritten.append(sentence.strip())
                continue

            fallback = (
                self.safe_storage_fallback
                if self._has_unsupported_storage_text(sentence)
                else self._safe_research_fallback(location)
            )
            if fallback not in rewritten:
                rewritten.append(fallback)

        if rewritten:
            return " ".join(rewritten).strip()
        return self._safe_research_fallback(location)

    def _safe_research_fallback(self, location: str) -> str:
        if location == "title":
            return "Research-context overview"
        return "This content is informational and limited to research context."

    def _remove_blocking_sentences(self, value: str, location: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        safe_sentences = [
            sentence.strip()
            for sentence in sentences
            if sentence.strip() and not self._has_blocking_sanity_text(sentence)
        ]
        if safe_sentences:
            return " ".join(safe_sentences).strip()
        return self._safe_research_fallback(location)

    def _replace_or_append_fallback(self, value: str) -> str:
        cleaned = self._remove_risky_sentences(value)
        if self.safe_storage_fallback in cleaned:
            return cleaned
        return f"{cleaned}\n\n{self.safe_storage_fallback}".strip()

    def _remove_risky_sentences(self, value: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", value)
        safe_sentences = []
        for sentence in sentences:
            if self._has_unsupported_storage_text(sentence):
                continue
            safe_sentences.append(sentence)
        return " ".join(sentence for sentence in safe_sentences if sentence.strip()).strip()

    def _has_unsupported_storage_text(self, value: str) -> bool:
        approved = self._instance_approved_claims()
        for code, pattern, _ in STORAGE_PATTERNS:
            for match in pattern.finditer(value):
                if self._has_cautious_storage_context(value, match.start()):
                    continue
                if self._is_approved_claim(self._sentence_around(value, match.start()), approved):
                    continue
                return True
        return False

    def _instance_approved_claims(self) -> list[str]:
        storage = self.rules.get("approved_storage_claims")
        handling = self.rules.get("approved_handling_claims")
        claims: list[str] = []
        if isinstance(storage, list):
            claims.extend(str(item) for item in storage if str(item).strip())
        if isinstance(handling, list):
            claims.extend(str(item) for item in handling if str(item).strip())
        return claims

    def _has_blocking_sanity_text(self, value: str) -> bool:
        approved = self._instance_approved_claims()
        for code, pattern, _ in STORAGE_PATTERNS:
            for match in pattern.finditer(value):
                if self._has_cautious_storage_context(value, match.start()):
                    continue
                if self._is_approved_claim(self._sentence_around(value, match.start()), approved):
                    continue
                return True

        for _, pattern, _ in DOSING_PATTERNS:
            for match in pattern.finditer(value):
                if self._has_safe_negation(value, match.start()) or self._is_question_context(value, match.start()):
                    continue
                return True

        for _, pattern, _ in THERAPEUTIC_PATTERNS:
            for match in pattern.finditer(value):
                if self._has_safe_negation(value, match.start()):
                    continue
                return True

        return False


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return " ".join(parser.parts)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _dedupe_findings(findings: list[SanityFinding]) -> list[SanityFinding]:
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for finding in findings:
        key = (finding.code, finding.location, _normalize(finding.matched_text))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def _dedupe_replacements(replacements: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped = []
    for replacement in replacements:
        key = (replacement.get("location", ""), _normalize(replacement.get("matched_text", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(replacement)
    return deduped
