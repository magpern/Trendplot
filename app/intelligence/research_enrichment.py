from dataclasses import dataclass
from typing import Any

from app.intelligence.providers import (
    AcademicSearchProvider,
    NullIntelligenceProvider,
    RedditSignalProvider,
    TrendSignalProvider,
    WebSearchProvider,
    YouTubeSearchProvider,
)
from app.opportunities.schemas import AudienceProfile, OpportunityCluster


@dataclass(slots=True)
class ResearchEnrichmentConfig:
    enabled: bool = False
    max_queries: int = 20
    max_results_per_query: int = 5
    enable_academic: bool = False
    enable_reddit: bool = False
    enable_trend: bool = False
    enable_youtube: bool = True


class ResearchEnrichmentService:
    def __init__(
        self,
        config: ResearchEnrichmentConfig,
        *,
        web_provider: WebSearchProvider | None = None,
        academic_provider: AcademicSearchProvider | None = None,
        youtube_provider: YouTubeSearchProvider | None = None,
        reddit_provider: RedditSignalProvider | None = None,
        trend_provider: TrendSignalProvider | None = None,
    ) -> None:
        self.config = config
        null_provider = NullIntelligenceProvider()
        self.web_provider = web_provider or null_provider
        self.academic_provider = academic_provider or null_provider
        self.youtube_provider = youtube_provider or null_provider
        self.reddit_provider = reddit_provider or null_provider
        self.trend_provider = trend_provider or null_provider

    async def enrich(
        self,
        *,
        signal_inventory: dict[str, Any],
        audiences: list[AudienceProfile],
        clusters: list[OpportunityCluster],
    ) -> dict[str, Any]:
        queries = generate_research_queries(signal_inventory, audiences, clusters, self.config.max_queries)
        if not self.config.enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "queries": queries,
                "sources_used": [],
                "source_results": {},
                "warnings": ["External research is disabled by configuration."],
                "summary": _empty_summary(),
            }

        source_results: dict[str, list[dict[str, Any]]] = {
            "web": await self._search_many("web", queries["web_search_queries"], self.web_provider.search_web),
            "youtube": await self._search_many("youtube", queries["youtube_queries"], self.youtube_provider.search_youtube)
            if self.config.enable_youtube
            else [],
            "academic": await self._search_many("academic", queries["academic_queries"], self.academic_provider.search_academic)
            if self.config.enable_academic
            else [],
            "reddit": await self._search_many("reddit", queries["reddit_queries"], self.reddit_provider.search_reddit)
            if self.config.enable_reddit
            else [],
            "trend": await self._search_many("trend", queries["trend_queries"], self.trend_provider.search_trends)
            if self.config.enable_trend
            else [],
        }
        summary = summarize_external_signals(source_results, signal_inventory)
        sources_used = [
            source_type
            for source_type, results in source_results.items()
            if any(result.get("status") != "not_configured" for result in results)
        ]
        warnings = []
        if not sources_used:
            warnings.append("External research was enabled, but no configured provider returned usable results.")
        if any(result.get("status") == "not_configured" for results in source_results.values() for result in results):
            warnings.append("One or more external research providers are disabled or not configured.")
        return {
            "enabled": True,
            "status": "completed" if sources_used else "no_provider_results",
            "queries": queries,
            "sources_used": sources_used,
            "source_results": source_results,
            "warnings": warnings,
            "summary": summary,
        }

    async def _search_many(self, source_type: str, queries: list[str], search_func: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for query in queries[: self.config.max_queries]:
            try:
                items = await search_func(query, self.config.max_results_per_query)
            except Exception as exc:  # External research should never break analysis.
                items = [
                    {
                        "source_type": source_type,
                        "query": query,
                        "title": "External research failed",
                        "url": "",
                        "snippet": str(exc),
                        "provider": source_type,
                        "status": "failed",
                        "verified": False,
                    }
                ]
            results.extend(_normalize_results(source_type, query, items))
        return results


def generate_research_queries(
    signal_inventory: dict[str, Any],
    audiences: list[AudienceProfile],
    clusters: list[OpportunityCluster],
    max_queries: int = 20,
) -> dict[str, list[str]]:
    niche = signal_inventory.get("niche_intelligence", {})
    products = signal_inventory.get("product_intelligence", {}).get("extracted_products", [])
    entities = signal_inventory.get("product_intelligence", {}).get("extracted_entities", [])
    mechanisms = signal_inventory.get("product_intelligence", {}).get("extracted_mechanisms", [])
    concepts = signal_inventory.get("semantic_expansion", {}).get("concepts", [])
    cluster_terms = [term for cluster in clusters for term in [cluster.name, *cluster.source_terms[:3], *cluster.entities[:3]]]
    audience_terms = [topic for audience in audiences for topic in [*audience.authority_topics[:3], *audience.recurring_questions[:2]]]
    base_terms = _clean_terms([*products[:8], *entities[:10], *mechanisms[:8], *concepts[:10], *cluster_terms[:10], *audience_terms[:8]])
    primary_niche = str(niche.get("primary_niche") or signal_inventory.get("detected_vertical") or "niche")
    adjacent = _clean_terms(niche.get("adjacent_niches", []))

    web = _limited(
        [
            f"{term} {primary_niche} overview"
            for term in base_terms[:8]
        ]
        + [f"{term} comparison questions" for term in base_terms[:6]]
        + [f"{term} guide" for term in adjacent[:4]],
        max_queries,
    )
    academic = _limited([f"{term} research overview" for term in [*base_terms[:8], *adjacent[:4]]], max_queries)
    youtube = _limited([f"{term} explained" for term in base_terms[:10]] + [f"{primary_niche} questions"], max_queries)
    reddit = _limited([f"{term} common questions" for term in base_terms[:8]] + [f"{primary_niche} discussion"], max_queries)
    trend = _limited([f"{term} trends" for term in [*adjacent[:6], *base_terms[:6]]], max_queries)
    return {
        "web_search_queries": web,
        "academic_queries": academic,
        "youtube_queries": youtube,
        "reddit_queries": reddit,
        "trend_queries": trend,
    }


def summarize_external_signals(
    source_results: dict[str, list[dict[str, Any]]],
    signal_inventory: dict[str, Any],
) -> dict[str, Any]:
    usable_results = [
        result
        for results in source_results.values()
        for result in results
        if result.get("status") not in {"not_configured", "failed"}
    ]
    recurring_topics = _top_phrases(usable_results)
    audience_questions = [
        result.get("query", "")
        for result in usable_results
        if any(starter in str(result.get("query", "")).lower() for starter in ("what", "how", "why", "best", "guide", "questions"))
    ][:30]
    possible_angles = []
    for topic in recurring_topics[:20]:
        source_type = _source_for_topic(topic, usable_results)
        possible_angles.append(
            {
                "title": f"{topic.title()} In The Wider Market Conversation",
                "target_keyword": topic,
                "source_type": source_type,
                "evidence_summary": _evidence_summary(topic, usable_results),
                "needs_verification": True,
            }
        )
    compliance_notes = []
    vertical = signal_inventory.get("detected_vertical")
    if vertical in {"peptides", "supplements"}:
        compliance_notes.append("Treat external research as directional only; avoid medical, dosing, treatment, cure, or human-use claims.")
    return {
        **_empty_summary(),
        "recurring_topics": recurring_topics,
        "rising_themes": recurring_topics[:10],
        "audience_questions": audience_questions,
        "entity_relationships": _entity_relationships(recurring_topics),
        "competitor_independent_opportunities": possible_angles[:15],
        "caution_compliance_notes": compliance_notes,
        "possible_article_angles": possible_angles,
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "recurring_topics": [],
        "rising_themes": [],
        "audience_questions": [],
        "entity_relationships": [],
        "competitor_independent_opportunities": [],
        "caution_compliance_notes": [],
        "possible_article_angles": [],
    }


def _normalize_results(source_type: str, query: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "source_type": item.get("source_type") or source_type,
                "query": item.get("query") or query,
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("snippet") or item.get("description") or "",
                "provider": item.get("provider") or source_type,
                "status": item.get("status") or "ok",
                "verified": bool(item.get("verified", False)),
            }
        )
    return normalized


def _top_phrases(results: list[dict[str, Any]]) -> list[str]:
    phrases: dict[str, int] = {}
    for result in results:
        text = " ".join([str(result.get("query", "")), str(result.get("title", "")), str(result.get("snippet", ""))]).lower()
        for token in _clean_terms(text.replace("-", " ").split()):
            phrases[token] = phrases.get(token, 0) + 1
    return [term for term, _ in sorted(phrases.items(), key=lambda item: item[1], reverse=True)[:40]]


def _source_for_topic(topic: str, results: list[dict[str, Any]]) -> str:
    for result in results:
        if topic.lower() in " ".join([str(result.get("query", "")), str(result.get("title", "")), str(result.get("snippet", ""))]).lower():
            return str(result.get("source_type") or "web")
    return "inferred"


def _evidence_summary(topic: str, results: list[dict[str, Any]]) -> str:
    matches = [
        f"{result.get('source_type')}: {result.get('title') or result.get('query')}"
        for result in results
        if topic.lower() in " ".join([str(result.get("query", "")), str(result.get("title", "")), str(result.get("snippet", ""))]).lower()
    ]
    return "; ".join(matches[:3]) or "External provider returned this as a recurring directional theme."


def _entity_relationships(topics: list[str]) -> list[dict[str, str]]:
    return [
        {"source": first, "target": second, "relationship": "externally_co_occurs"}
        for first, second in zip(topics, topics[1:])
    ][:40]


def _clean_terms(values: list[Any]) -> list[str]:
    stop = {"and", "for", "the", "with", "from", "into", "about", "guide", "overview", "questions"}
    cleaned = []
    for value in values:
        text = " ".join(str(value).split()).strip(" .,;:()[]{}").lower()
        if len(text) < 3 or text in stop:
            continue
        cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def _limited(values: list[str], limit: int) -> list[str]:
    return list(dict.fromkeys(value for value in values if value.strip()))[: max(1, limit)]
