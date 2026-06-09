from typing import Any, Literal

from pydantic import BaseModel, Field


class AudienceProfile(BaseModel):
    id: str
    name: str
    description: str = ""
    audience_type: str = "inferred"
    expertise_level: str = "mixed"
    confidence: float = 0.65
    commercial_intent: float = 0.4
    research_intent: float = 0.6
    concerns: list[str] = Field(default_factory=list)
    recurring_questions: list[str] = Field(default_factory=list)
    preferred_content_types: list[str] = Field(default_factory=list)
    authority_topics: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    related_clusters: list[str] = Field(default_factory=list)
    source_signals: dict[str, Any] = Field(default_factory=dict)


class OpportunityCluster(BaseModel):
    id: str
    name: str
    description: str = ""
    parent_cluster_id: str | None = None
    entities: list[str] = Field(default_factory=list)
    source_terms: list[str] = Field(default_factory=list)
    confidence: float = 0.65
    authority_value: float = 0.5
    seo_value: float = 0.5
    editorial_value: float = 0.5
    geo_value: float = 0.5
    opportunity_count: int = 0
    primary_audiences: list[str] = Field(default_factory=list)
    audience_overlap: list[str] = Field(default_factory=list)
    pillar_candidate: bool = False
    semantic_authority_role: str = "support"


class AuthorityGraphNode(BaseModel):
    id: str
    node_type: Literal["cluster", "entity", "audience", "intent", "product", "question", "concept"] = "concept"
    label: str
    description: str = ""
    confidence: float = 0.65
    source_signals: dict[str, Any] = Field(default_factory=dict)


class AuthorityGraphEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_type: str = "relates_to"
    strength: float = 0.5
    rationale: str = ""


class AuthorityGraph(BaseModel):
    nodes: list[AuthorityGraphNode] = Field(default_factory=list)
    edges: list[AuthorityGraphEdge] = Field(default_factory=list)


class OpportunityScore(BaseModel):
    overall: float = 0.5
    audience_fit: float = 0.5
    authority_fit: float = 0.5
    semantic_gap: float = 0.5
    competitor_gap: float = 0.5
    novelty: float = 0.5
    saturation: float = 0.5
    business_value: float = 0.5
    editorial_effort: float = 0.5
    compliance_sensitivity: float = 0.5


class Opportunity(BaseModel):
    id: str
    cluster_id: str | None = None
    title: str
    target_keyword: str
    product_name: str = ""
    product_url: str = ""
    opportunity_type: str = "semantic_support_article"
    search_intent: str = "informational"
    funnel_stage: str = "awareness"
    content_role: str = "supporting_article"
    primary_audience_id: str | None = None
    secondary_audience_ids: list[str] = Field(default_factory=list)
    audience_rationale: str = ""
    expertise_level: str = "mixed"
    confidence: float = 0.65
    scores: OpportunityScore = Field(default_factory=OpportunityScore)
    related_products: list[str] = Field(default_factory=list)
    related_keywords: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    authority_graph_node_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    source_type: Literal["site", "competitor", "web", "academic", "youtube", "reddit", "trend", "inferred"] = "inferred"
    evidence_summary: str = ""
    needs_verification: bool = True
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    competitor_references: list[dict[str, Any]] = Field(default_factory=list)
    suggested_article_length: int = 1800
    suggested_structure: list[str] = Field(default_factory=list)
    suggested_media: list[str] = Field(default_factory=list)
    suggested_internal_links: list[str] = Field(default_factory=list)
    cta_strategy: str = ""
    status: str = "suggested"

    def to_article_command(self) -> dict[str, str]:
        return {
            "title": self.title,
            "target_keyword": self.target_keyword,
            "product_name": self.product_name or self.target_keyword,
            "product_url": self.product_url,
        }


class OpportunityRelationship(BaseModel):
    parent_id: str
    child_id: str
    relationship_type: str = "supports"
    strength: float = 0.5
    rationale: str = ""
    source: str = "opportunity-engine"


class OpportunityDiscoveryResult(BaseModel):
    summary: str = ""
    audiences: list[AudienceProfile] = Field(default_factory=list)
    clusters: list[OpportunityCluster] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    authority_graph: AuthorityGraph = Field(default_factory=AuthorityGraph)
    relationships: list[OpportunityRelationship] = Field(default_factory=list)
    niche_intelligence: dict[str, Any] = Field(default_factory=dict)
    product_intelligence: dict[str, Any] = Field(default_factory=dict)
    competitor_intelligence: dict[str, Any] = Field(default_factory=dict)
    semantic_expansion: dict[str, Any] = Field(default_factory=dict)
    vertical_intelligence: dict[str, Any] = Field(default_factory=dict)
    external_research: dict[str, Any] = Field(default_factory=dict)
    campaign_seed: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
