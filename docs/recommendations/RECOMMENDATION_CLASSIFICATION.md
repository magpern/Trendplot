# Recommendation classification and sources

## Recommendation sources (origin buckets)

Every recommendation is tagged with a **source bucket** for diagnostics. Raw `source_type` values from OI discovery are mapped as follows:

| OI `source_type` | Bucket | Label |
|------------------|--------|-------|
| `niche_profile` | entity | Entity |
| `existing_opportunity` | entity | Entity |
| `ai_editorial_strategist` | entity | Entity |
| `editorial_opportunity` | research | Research |
| `market_intelligence` | research | Research |
| `coverage` | coverage | Coverage Gap |
| `published_content` | coverage | Coverage Gap |
| `competitor` | competitor | Competitor Gap |
| `demand_observation` | demand | Demand Intent |
| `demand_intent` | demand | Demand Intent |
| `trend_signal` | trend | Trend Signal |

Diagnostics example (OI summary):

```json
{
  "recommendation_sources": {
    "entity": 62,
    "coverage": 18,
    "competitor": 8,
    "demand": 3,
    "trend": 0,
    "research": 9
  }
}
```

Implementation: `app/recommendations/source_audit.py`.

## Demand-intent generation

Deterministic patterns expand catalog products/categories into search-intent opportunities (no niche-specific hardcoding):

| Intent type | Example pattern |
|-------------|-----------------|
| `comparison` | `{A} vs {B}` |
| `faq` | `{product} FAQ` |
| `how_to` | `How to Reconstitute {product}`, `How to Store {product}` |
| `storage` | `{product} Storage Guide` |
| `handling` | `{product} Handling Guide` |
| `troubleshooting` | `{product} Troubleshooting Guide` |
| `calculator` | `{product} Dosage Calculator Guide` |
| `how_to` (category) | `{category} Buyer's Guide` |

Source type: `demand_intent`. Implementation: `app/recommendations/demand_intent.py`, wired in `OpportunityCandidateDiscovery.discover()`.

## Classification types

Each recommendation receives `metadata.recommendation_classification`:

| Classification | Typical signals |
|----------------|-----------------|
| `glossary` | "What is", "Introduction to", product_education |
| `faq` | FAQ in title, demand_intent faq |
| `comparison` | "vs", "compared", product pairs |
| `how_to` | How-to, reconstitute, store, handling |
| `calculator` | calculator, estimator |
| `commercial` | buyer's guide, pricing |
| `authority` | ultimate guide, complete guide |
| `research` | research overview, EOG/market sources |
| `refresh` | OI action refresh |
| `expand` | OI action expand |
| `follow_up` | default when no stronger match |

Classification uses title/topic regex and metadata (`demand_intent_type`, `content_type`). Implementation: `app/recommendations/classification.py`.

## Metadata fields

Stored on each recommendation row (`metadata` JSON):

| Field | Description |
|-------|-------------|
| `recommendation_classification` | Classification type |
| `recommendation_source_bucket` | Origin bucket |
| `recommendation_origin` | Raw OI source_type |
| `demand_intent_type` | For demand_intent candidates |
| `ai_review` | Reviewer scores and decision |

## Reviewer use of classification

The AI reviewer prompt instructs the model to treat **glossary** and entity-derived definitions as lower `search_value` unless tied to core catalog products, while **comparison**, **how_to**, and **competitor** origins typically score higher.

See [RECOMMENDATION_REVIEW.md](./RECOMMENDATION_REVIEW.md) for reviewer I/O and gates.
