from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.catalog.products import catalog_dedupe_key, is_product_page_url, resolve_product_page_url

MAX_LINKS_PER_PRODUCT = 2
_HEADING_LINE = re.compile(r"^\s*#+\s")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}")


@dataclass(slots=True)
class LinkPlacement:
    product_name: str
    url: str
    field: str
    section_key: str
    anchor_text: str


@dataclass(slots=True)
class ProductLinkState:
    product_name: str
    url: str
    link_count: int = 0
    linked_sections: set[str] = field(default_factory=set)
    first_section_order: int | None = None
    placements: list[LinkPlacement] = field(default_factory=list)


@dataclass(slots=True)
class LinkReport:
    products: dict[str, dict[str, Any]] = field(default_factory=dict)
    total_links: int = 0
    placements: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_links": self.total_links,
            "products": self.products,
            "placements": self.placements,
            "rules": {
                "max_links_per_product": MAX_LINKS_PER_PRODUCT,
                "max_links_per_section": 1,
            },
        }


@dataclass(slots=True)
class _LinkTarget:
    field_type: str
    section_key: str
    order: int
    getter: Callable[[], str]
    setter: Callable[[str], None]


def build_article_product_url_map(
    *,
    product_name: str,
    product_url: str,
    related_products: list[str] | None,
    catalog_urls: list[str] | None,
) -> dict[str, str]:
    """Build product display name -> resolved product-page URL for article-scoped products."""
    candidates: list[str] = []
    if product_name.strip():
        candidates.append(product_name.strip())
    for item in related_products or []:
        text = str(item or "").strip()
        if text:
            candidates.append(text)

    url_map: dict[str, str] = {}
    seen_keys: set[str] = set()
    primary_key = catalog_dedupe_key(product_name)

    for name in candidates:
        key = catalog_dedupe_key(name)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        if key == primary_key:
            resolved = resolve_product_page_url(
                product_name=name,
                product_url=product_url,
                catalog_urls=catalog_urls or [],
            )
        else:
            resolved = resolve_product_page_url(
                product_name=name,
                product_url="",
                catalog_urls=catalog_urls or [],
            )
        if is_product_page_url(resolved):
            url_map[name] = resolved

    return url_map


def link_first_unlinked_mention(text: str, product_name: str, url: str) -> tuple[str, bool]:
    """Link at most one unlinked contextual mention in prose lines."""
    if not text.strip() or not product_name.strip() or not url.strip():
        return text, False

    lines = text.splitlines(keepends=True)
    changed = False
    rebuilt: list[str] = []

    for index, line in enumerate(lines):
        if changed:
            rebuilt.append(line)
            continue
        if _should_skip_line(line, lines, index):
            rebuilt.append(line)
            continue
        updated, linked = _link_first_in_line(line, product_name, url)
        rebuilt.append(updated)
        if linked:
            changed = True

    if not changed:
        updated, linked = _link_first_in_line(text, product_name, url)
        return (updated, linked) if linked else (text, False)

    return "".join(rebuilt), True


def link_products_in_article(article_json: dict[str, Any], url_map: dict[str, str]) -> tuple[dict[str, Any], LinkReport]:
    data = copy.deepcopy(article_json or {})
    report = LinkReport()
    if not url_map:
        return data, report

    products_sorted = sorted(url_map.items(), key=lambda item: len(item[0]), reverse=True)
    states = {name: ProductLinkState(product_name=name, url=url) for name, url in products_sorted}
    _count_existing_links(data, states)

    for state in states.values():
        _place_links_for_product(data, state, report)

    report.total_links = sum(state.link_count for state in states.values())
    for state in states.values():
        report.products[state.product_name] = {
            "url": state.url,
            "link_count": state.link_count,
            "sections": sorted(state.linked_sections),
        }
        for placement in state.placements:
            report.placements.append(
                {
                    "product_name": placement.product_name,
                    "url": placement.url,
                    "field": placement.field,
                    "section_key": placement.section_key,
                    "anchor_text": placement.anchor_text,
                }
            )

    return data, report


def _place_links_for_product(data: dict[str, Any], state: ProductLinkState, report: LinkReport) -> None:
    targets = _collect_targets(data)

    body_targets = [target for target in targets if target.field_type in {"section", "subsection"}]
    _place_first_link(state, body_targets, report)
    _place_second_link(state, body_targets, report)

    if state.link_count == 0:
        fallback_targets = [target for target in targets if target.field_type in {"faq_answer", "excerpt"}]
        _place_first_link(state, fallback_targets, report)

    if state.link_count == 1:
        fallback_targets = [target for target in targets if target.field_type in {"faq_answer", "excerpt"}]
        _place_second_link(state, fallback_targets, report, allow_same_order=True)

    if state.link_count == 0:
        takeaway_targets = [target for target in targets if target.field_type == "takeaway"]
        _place_first_link(state, takeaway_targets, report)


def _place_first_link(
    state: ProductLinkState,
    targets: list[_LinkTarget],
    report: LinkReport,
) -> None:
    if state.link_count >= 1:
        return
    for target in targets:
        if state.link_count >= 1:
            break
        _try_link_in_target(state, target, report)


def _place_second_link(
    state: ProductLinkState,
    targets: list[_LinkTarget],
    report: LinkReport,
    *,
    allow_same_order: bool = False,
) -> None:
    if state.link_count >= MAX_LINKS_PER_PRODUCT:
        return
    if state.link_count == 0:
        return

    first_order = state.first_section_order if state.first_section_order is not None else -1
    later_targets = [target for target in targets if target.order > first_order]
    ordered = later_targets if later_targets else (targets if allow_same_order else [])

    for target in ordered:
        if state.link_count >= MAX_LINKS_PER_PRODUCT:
            break
        if target.section_key in state.linked_sections:
            continue
        _try_link_in_target(state, target, report)


def _try_link_in_target(state: ProductLinkState, target: _LinkTarget, report: LinkReport) -> bool:
    if state.link_count >= MAX_LINKS_PER_PRODUCT:
        return False
    if target.section_key in state.linked_sections:
        return False

    current = target.getter()
    updated, linked = link_first_unlinked_mention(current, state.product_name, state.url)
    if not linked:
        return False

    target.setter(updated)
    anchor = _extract_anchor_text(updated, state.product_name, state.url) or state.product_name
    state.link_count += 1
    state.linked_sections.add(target.section_key)
    if state.first_section_order is None:
        state.first_section_order = target.order
    placement = LinkPlacement(
        product_name=state.product_name,
        url=state.url,
        field=target.field_type,
        section_key=target.section_key,
        anchor_text=anchor,
    )
    state.placements.append(placement)
    return True


def _collect_targets(data: dict[str, Any]) -> list[_LinkTarget]:
    targets: list[_LinkTarget] = []
    sections = data.get("sections")
    if isinstance(sections, list):
        for section_index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            section_key = f"section:{section_index}"
            order = section_index * 100

            def _section_getter(section_ref: dict[str, Any] = section) -> str:
                return str(section_ref.get("content_markdown") or "")

            def _section_setter(value: str, section_ref: dict[str, Any] = section) -> None:
                section_ref["content_markdown"] = value

            targets.append(
                _LinkTarget(
                    field_type="section",
                    section_key=section_key,
                    order=order,
                    getter=_section_getter,
                    setter=_section_setter,
                )
            )

            for sub_index, subsection in enumerate(section.get("subsections") or []):
                if not isinstance(subsection, dict):
                    continue
                sub_key = f"section:{section_index}:subsection:{sub_index}"
                sub_order = order + sub_index + 1

                def _sub_getter(sub_ref: dict[str, Any] = subsection) -> str:
                    return str(sub_ref.get("content_markdown") or "")

                def _sub_setter(value: str, sub_ref: dict[str, Any] = subsection) -> None:
                    sub_ref["content_markdown"] = value

                targets.append(
                    _LinkTarget(
                        field_type="subsection",
                        section_key=sub_key,
                        order=sub_order,
                        getter=_sub_getter,
                        setter=_sub_setter,
                    )
                )

    faq = data.get("faq")
    if isinstance(faq, list):
        for faq_index, item in enumerate(faq):
            if not isinstance(item, dict):
                continue
            faq_key = f"faq:{faq_index}"

            def _faq_getter(faq_ref: dict[str, Any] = item) -> str:
                return str(faq_ref.get("answer") or "")

            def _faq_setter(value: str, faq_ref: dict[str, Any] = item) -> None:
                faq_ref["answer"] = value

            targets.append(
                _LinkTarget(
                    field_type="faq_answer",
                    section_key=faq_key,
                    order=1000 + faq_index,
                    getter=_faq_getter,
                    setter=_faq_setter,
                )
            )

    excerpt = str(data.get("excerpt") or "")

    def _excerpt_getter() -> str:
        return str(data.get("excerpt") or "")

    def _excerpt_setter(value: str) -> None:
        data["excerpt"] = value

    if excerpt.strip():
        targets.append(
            _LinkTarget(
                field_type="excerpt",
                section_key="excerpt",
                order=2000,
                getter=_excerpt_getter,
                setter=_excerpt_setter,
            )
        )

    takeaways = data.get("key_takeaways")
    if isinstance(takeaways, list):
        for index, item in enumerate(takeaways):
            text = str(item or "").strip()
            if not text:
                continue
            takeaway_key = f"takeaway:{index}"

            def _takeaway_getter(i: int = index) -> str:
                values = data.get("key_takeaways")
                if not isinstance(values, list) or i >= len(values):
                    return ""
                return str(values[i] or "")

            def _takeaway_setter(value: str, i: int = index) -> None:
                values = data.get("key_takeaways")
                if isinstance(values, list) and i < len(values):
                    values[i] = value

            targets.append(
                _LinkTarget(
                    field_type="takeaway",
                    section_key=takeaway_key,
                    order=3000 + index,
                    getter=_takeaway_getter,
                    setter=_takeaway_setter,
                )
            )

    return targets


def _count_existing_links(data: dict[str, Any], states: dict[str, ProductLinkState]) -> None:
    targets = _collect_targets(data)
    pattern_by_url = {
        state.url: re.compile(rf"\[[^\]]+\]\({re.escape(state.url)}\)", re.IGNORECASE)
        for state in states.values()
    }
    for state in states.values():
        pattern = pattern_by_url[state.url]
        for target in targets:
            text = target.getter()
            matches = pattern.findall(text)
            if not matches:
                continue
            state.linked_sections.add(target.section_key)
            if state.first_section_order is None:
                state.first_section_order = target.order
            state.link_count = min(state.link_count + len(matches), MAX_LINKS_PER_PRODUCT)


def _should_skip_line(line: str, lines: list[str], index: int) -> bool:
    if _HEADING_LINE.match(line):
        return True
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("|") and index + 1 < len(lines) and _TABLE_SEPARATOR.match(lines[index + 1]):
        return True
    return False


def _link_first_in_line(line: str, product_name: str, url: str) -> tuple[str, bool]:
    match = _find_first_unlinked_match(line, product_name)
    if match is None:
        return line, False
    anchor = match.group(1)
    linked = f"[{anchor}]({url})"
    updated = f"{line[: match.start()]}{linked}{line[match.end():]}"
    return updated, True


def _find_first_unlinked_match(text: str, product_name: str) -> re.Match[str] | None:
    pattern = re.compile(rf"(?<!\[)\b({re.escape(product_name)})\b(?![\]\)])", re.IGNORECASE)
    for match in pattern.finditer(text):
        if _is_inside_markdown_link(text, match.start()):
            continue
        return match
    return None


def _is_inside_markdown_link(text: str, index: int) -> bool:
    before = text[:index]
    last_open = before.rfind("[")
    last_close = before.rfind("]")
    if last_open <= last_close:
        return False
    segment = text[last_open:index]
    return "](" not in segment and last_open >= 0


def _extract_anchor_text(text: str, product_name: str, url: str) -> str | None:
    pattern = re.compile(rf"\[([^\]]+)\]\({re.escape(url)}\)", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1)
    return product_name
