from time import perf_counter
from typing import Any

from app.opportunities.audiences import infer_audiences
from app.opportunities.authority_graph import build_authority_graph, build_opportunity_relationships
from app.opportunities.clustering import build_clusters
from app.opportunities.ecosystem import summarize_editorial_ecosystem
from app.opportunities.gaps import summarize_competitor_gaps
from app.opportunities.generator import generate_opportunities
from app.opportunities.schemas import OpportunityDiscoveryResult
from app.opportunities.signals import build_signal_inventory


class OpportunityDiscoveryEngine:
    def discover(
        self,
        *,
        website: dict[str, Any],
        competitors: list[dict[str, Any]],
        ai_payload: dict[str, Any],
        vertical: str = "auto",
    ) -> OpportunityDiscoveryResult:
        started = perf_counter()
        signals = build_signal_inventory(website, competitors, vertical=vertical)
        audiences = infer_audiences(signals, ai_payload.get("audiences") or ai_payload.get("audience_profiles"))
        clusters = build_clusters(signals, ai_payload.get("clusters") or ai_payload.get("opportunity_clusters"))
        return self._build_result(
            started=started,
            website=website,
            signals=signals,
            audiences=audiences,
            clusters=clusters,
            ai_payload=ai_payload,
        )

    async def discover_async(
        self,
        *,
        website: dict[str, Any],
        competitors: list[dict[str, Any]],
        ai_payload: dict[str, Any],
        vertical: str = "auto",
        research_enrichment: Any = None,
    ) -> OpportunityDiscoveryResult:
        started = perf_counter()
        signals = build_signal_inventory(website, competitors, vertical=vertical)
        audiences = infer_audiences(signals, ai_payload.get("audiences") or ai_payload.get("audience_profiles"))
        clusters = build_clusters(signals, ai_payload.get("clusters") or ai_payload.get("opportunity_clusters"))
        if research_enrichment is not None:
            external_research = await research_enrichment.enrich(
                signal_inventory=signals,
                audiences=audiences,
                clusters=clusters,
            )
            _apply_external_research(signals, external_research)
        return self._build_result(
            started=started,
            website=website,
            signals=signals,
            audiences=audiences,
            clusters=clusters,
            ai_payload=ai_payload,
        )

    def _build_result(
        self,
        *,
        started: float,
        website: dict[str, Any],
        signals: dict[str, Any],
        audiences: list[Any],
        clusters: list[Any],
        ai_payload: dict[str, Any],
    ) -> OpportunityDiscoveryResult:
        opportunities = generate_opportunities(
            signal_inventory=signals,
            audiences=audiences,
            clusters=clusters,
            ai_opportunities=ai_payload.get("opportunities") or ai_payload.get("suggestions"),
            fallback_url=website.get("url", ""),
        )
        cluster_counts = {cluster.id: 0 for cluster in clusters}
        for opportunity in opportunities:
            if opportunity.cluster_id in cluster_counts:
                cluster_counts[opportunity.cluster_id] += 1
        for cluster in clusters:
            cluster.opportunity_count = cluster_counts.get(cluster.id, 0)

        authority_graph = build_authority_graph(
            clusters,
            audiences,
            signals,
            ai_payload.get("authority_graph"),
        )
        relationships = build_opportunity_relationships(opportunities)
        ecosystem = summarize_editorial_ecosystem(signals, audiences, clusters)
        gaps = summarize_competitor_gaps(signals)

        return OpportunityDiscoveryResult(
            summary=str(ai_payload.get("summary") or self._fallback_summary(website, opportunities)),
            audiences=audiences,
            clusters=clusters,
            opportunities=opportunities,
            authority_graph=authority_graph,
            relationships=relationships,
            niche_intelligence=signals.get("niche_intelligence", {}),
            product_intelligence=signals.get("product_intelligence", {}),
            competitor_intelligence=signals.get("competitor_intelligence", {}),
            semantic_expansion=signals.get("semantic_expansion", {}),
            vertical_intelligence=signals.get("vertical_intelligence", {}),
            external_research=signals.get("external_research", {}),
            campaign_seed={
                "status": "scaffold",
                "recommended_sequence": [
                    {"opportunity_id": item.id, "role": item.content_role}
                    for item in opportunities[:12]
                ],
            },
            metrics={
                "runtime_seconds": round(perf_counter() - started, 3),
                "signal_terms": len(signals.get("terms", [])),
                "questions": len(signals.get("questions", [])),
                "audiences": len(audiences),
                "clusters": len(clusters),
                "opportunities": len(opportunities),
                "authority_graph_nodes": len(authority_graph.nodes),
                "authority_graph_edges": len(authority_graph.edges),
                "competitor_gap_terms": gaps["gap_count"],
                "pillar_candidates": len(ecosystem["pillar_candidates"]),
                "products_extracted": len(signals.get("product_intelligence", {}).get("extracted_products", [])),
                "semantic_concepts": len(signals.get("semantic_expansion", {}).get("concepts", [])),
                "detected_vertical": signals.get("detected_vertical", "generic"),
                "detected_vertical_confidence": signals.get("detected_vertical_confidence", 0),
                "external_research_status": signals.get("external_research", {}).get("status", "not_run"),
                "external_research_sources": signals.get("external_research", {}).get("sources_used", []),
            },
        )

    def _fallback_summary(self, website: dict[str, Any], opportunities: list[Any]) -> str:
        domain = website.get("domain") or website.get("url") or "website"
        return f"Discovered {len(opportunities)} topical article opportunities for {domain}."


def _apply_external_research(signals: dict[str, Any], external_research: dict[str, Any]) -> None:
    signals["external_research"] = external_research
    summary = external_research.get("summary", {})
    external_topics = summary.get("recurring_topics", []) + summary.get("rising_themes", [])
    external_questions = summary.get("audience_questions", [])
    if external_topics:
        semantic = signals.setdefault("semantic_expansion", {})
        semantic["concepts"] = list(dict.fromkeys([*semantic.get("concepts", []), *external_topics]))[:180]
        semantic["entity_relationships"] = [
            *semantic.get("entity_relationships", []),
            *summary.get("entity_relationships", []),
        ][:180]
        competitor = signals.setdefault("competitor_intelligence", {})
        competitor["missing_topics"] = list(dict.fromkeys([*competitor.get("missing_topics", []), *external_topics]))[:120]
        competitor["external_research_topics"] = external_topics[:80]
    if external_questions:
        signals["questions"] = list(dict.fromkeys([*signals.get("questions", []), *external_questions]))[:100]
