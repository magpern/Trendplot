import re
from dataclasses import dataclass

from app.catalog.products import is_product_page_url
from app.providers.base import GeneratedContent


def _resolve_disclaimer(required_disclaimer: str | None) -> str:
    if required_disclaimer and str(required_disclaimer).strip():
        return str(required_disclaimer).strip()
    from app.config import Settings

    return Settings().biomedical_ruo_disclaimer


@dataclass(slots=True)
class InternalLinkResult:
    markdown: str
    links: list[dict[str, str]]
    plan: dict[str, object] | None = None


class InternalLinkService:
    provider_name = "internal-linker"

    async def enrich_markdown(
        self,
        markdown: str,
        product_name: str,
        product_url: str,
        target_keyword: str,
        suggested_links: list[dict[str, str]] | None = None,
        disclaimer_url: str | None = None,
        required_disclaimer: str | None = None,
    ) -> GeneratedContent:
        candidates = self._anchor_candidates(product_name, target_keyword, suggested_links)
        result = InternalLinkResult(markdown=markdown, links=[])
        result = self._upgrade_product_link_targets(
            result,
            product_url=product_url,
            suggested_links=suggested_links or [],
        )
        if disclaimer_url:
            result = self._append_disclaimer_link(result, disclaimer_url, required_disclaimer=required_disclaimer)
        plan = {
            "product_url": product_url,
            "disclaimer_url": disclaimer_url,
            "candidate_anchors": candidates,
            "selected_links": result.links,
            "rules": [
                "Use product URL naturally.",
                "Avoid exact-match anchor stuffing.",
                "Do not invent related URLs when no provider is available.",
                "Limit repeated URL usage.",
            ],
        }
        return GeneratedContent(
            content_text=result.markdown,
            content_json={"links": result.links, "plan": plan},
            provider=self.provider_name,
        )

    def _anchor_candidates(
        self,
        product_name: str,
        target_keyword: str,
        suggested_links: list[dict[str, str]] | None,
    ) -> list[str]:
        candidates = []
        for link in suggested_links or []:
            anchor = link.get("anchor_text", "")
            if anchor:
                candidates.append(anchor)
        candidates.extend(
            [
                product_name,
                f"{product_name} research material",
                target_keyword.replace("buy ", "").replace("best ", ""),
            ]
        )
        return list(dict.fromkeys(candidate for candidate in candidates if candidate.strip()))

    def _upgrade_product_link_targets(
        self,
        result: InternalLinkResult,
        *,
        product_url: str,
        suggested_links: list[dict[str, str]],
    ) -> InternalLinkResult:
        if not is_product_page_url(product_url):
            return result

        markdown = result.markdown
        links = list(result.links)
        stale_urls = {str(link.get("url") or "").strip() for link in suggested_links if link.get("url")}
        stale_urls.discard(product_url)

        for stale_url in stale_urls:
            if stale_url and stale_url in markdown:
                markdown = markdown.replace(f"]({stale_url})", f"]({product_url})")

        upgraded_links: list[dict[str, str]] = []
        for link in links:
            stale_url = str(link.get("url") or "").strip()
            if stale_url and stale_url != product_url and not is_product_page_url(stale_url):
                upgraded_links.append({**link, "url": product_url})
            else:
                upgraded_links.append(link)

        return InternalLinkResult(markdown=markdown, links=upgraded_links, plan=result.plan)

    def _append_disclaimer_link(
        self,
        result: InternalLinkResult,
        disclaimer_url: str,
        *,
        required_disclaimer: str | None = None,
    ) -> InternalLinkResult:
        if disclaimer_url in result.markdown:
            return result

        marker = _resolve_disclaimer(required_disclaimer)
        if marker not in result.markdown:
            return result

        linked = (
            f"{marker} "
            f"[Review research-use terms]({disclaimer_url})."
        )
        markdown = result.markdown.replace(marker, linked, 1)
        return InternalLinkResult(
            markdown=markdown,
            links=[
                *result.links,
                {
                    "anchor_text": "Review research-use terms",
                    "url": disclaimer_url,
                    "reason": "Research-use disclaimer support link.",
                },
            ],
        )
