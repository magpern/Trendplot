from typing import Any
from uuid import uuid4

from app.opportunities.schemas import (
    AudienceProfile,
    AuthorityGraph,
    AuthorityGraphEdge,
    AuthorityGraphNode,
    Opportunity,
    OpportunityCluster,
    OpportunityRelationship,
)


def build_authority_graph(
    clusters: list[OpportunityCluster],
    audiences: list[AudienceProfile],
    signal_inventory: dict[str, Any],
    ai_graph: Any = None,
) -> AuthorityGraph:
    graph = _normalize_ai_graph(ai_graph)
    if graph.nodes:
        return graph

    nodes: list[AuthorityGraphNode] = []
    edges: list[AuthorityGraphEdge] = []
    for cluster in clusters:
        nodes.append(
            AuthorityGraphNode(
                id=f"cluster:{cluster.id}",
                node_type="cluster",
                label=cluster.name,
                description=cluster.description,
                confidence=cluster.confidence,
                source_signals={"terms": cluster.source_terms[:10]},
            )
        )
        for entity in cluster.entities[:8]:
            entity_id = f"entity:{_slug(entity)}"
            nodes.append(
                AuthorityGraphNode(
                    id=entity_id,
                    node_type="entity",
                    label=entity,
                    confidence=0.62,
                )
            )
            edges.append(
                AuthorityGraphEdge(
                    source_node_id=f"cluster:{cluster.id}",
                    target_node_id=entity_id,
                    relationship_type="covers_entity",
                    strength=0.65,
                )
            )

    for audience in audiences:
        nodes.append(
            AuthorityGraphNode(
                id=f"audience:{audience.id}",
                node_type="audience",
                label=audience.name,
                description=audience.description,
                confidence=audience.confidence,
            )
        )
        for cluster in clusters[:5]:
            edges.append(
                AuthorityGraphEdge(
                    source_node_id=f"audience:{audience.id}",
                    target_node_id=f"cluster:{cluster.id}",
                    relationship_type="needs_topic",
                    strength=0.55,
                    rationale="Audience and cluster share crawl-derived terms.",
                )
            )

    for product in signal_inventory.get("product_candidates", [])[:10]:
        product_id = f"product:{_slug(product.get('name', 'product'))}"
        nodes.append(
            AuthorityGraphNode(
                id=product_id,
                node_type="product",
                label=str(product.get("name") or "Product"),
                source_signals={"url": product.get("url")},
            )
        )

    return AuthorityGraph(nodes=_dedupe_nodes(nodes), edges=_dedupe_edges(edges))


def build_opportunity_relationships(opportunities: list[Opportunity]) -> list[OpportunityRelationship]:
    relationships: list[OpportunityRelationship] = []
    by_cluster: dict[str, list[Opportunity]] = {}
    for opportunity in opportunities:
        if opportunity.cluster_id:
            by_cluster.setdefault(opportunity.cluster_id, []).append(opportunity)

    for cluster_opportunities in by_cluster.values():
        pillars = [item for item in cluster_opportunities if "pillar" in item.content_role]
        support = [item for item in cluster_opportunities if item not in pillars]
        if not pillars and cluster_opportunities:
            pillars = [max(cluster_opportunities, key=lambda item: item.scores.overall)]
            support = [item for item in cluster_opportunities if item.id != pillars[0].id]
        for pillar in pillars[:1]:
            for child in support[:12]:
                relationships.append(
                    OpportunityRelationship(
                        parent_id=pillar.id,
                        child_id=child.id,
                        relationship_type="pillar_support",
                        strength=0.68,
                        rationale="Support article reinforces the same topical authority cluster.",
                    )
                )
    return relationships


def _normalize_ai_graph(value: Any) -> AuthorityGraph:
    if not isinstance(value, dict):
        return AuthorityGraph()
    nodes = []
    for item in value.get("nodes", []):
        if not isinstance(item, dict) or not item.get("label"):
            continue
        nodes.append(
            AuthorityGraphNode(
                id=str(item.get("id") or uuid4()),
                node_type=_node_type(item.get("node_type") or item.get("type")),
                label=str(item.get("label")),
                description=str(item.get("description") or ""),
                confidence=_score(item.get("confidence"), 0.65),
                source_signals=item.get("source_signals") if isinstance(item.get("source_signals"), dict) else {},
            )
        )
    edges = []
    for item in value.get("edges", []):
        if not isinstance(item, dict) or not item.get("source_node_id") or not item.get("target_node_id"):
            continue
        edges.append(
            AuthorityGraphEdge(
                source_node_id=str(item.get("source_node_id")),
                target_node_id=str(item.get("target_node_id")),
                relationship_type=str(item.get("relationship_type") or "relates_to"),
                strength=_score(item.get("strength"), 0.5),
                rationale=str(item.get("rationale") or ""),
            )
        )
    return AuthorityGraph(nodes=nodes, edges=edges)


def _dedupe_nodes(nodes: list[AuthorityGraphNode]) -> list[AuthorityGraphNode]:
    unique = {}
    for node in nodes:
        unique.setdefault(node.id, node)
    return list(unique.values())[:240]


def _dedupe_edges(edges: list[AuthorityGraphEdge]) -> list[AuthorityGraphEdge]:
    unique = {}
    for edge in edges:
        unique.setdefault((edge.source_node_id, edge.target_node_id, edge.relationship_type), edge)
    return list(unique.values())[:400]


def _score(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    if numeric > 1:
        numeric = numeric / 100
    return max(0, min(1, numeric))


def _node_type(value: Any) -> str:
    allowed = {"cluster", "entity", "audience", "intent", "product", "question", "concept"}
    node_type = str(value or "concept")
    return node_type if node_type in allowed else "concept"


def _slug(value: str) -> str:
    return "-".join(value.lower().split())[:80] or str(uuid4())
