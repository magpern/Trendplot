# AI Recommendation Reviewer

## Purpose

The AI Recommendation Reviewer is a **critical quality gate** that scores whether OI-ranked recommendations make sense for the analyzed website. It runs **after** OI ranking and may adjust final actions. It does **not** generate new topics or rewrite recommendations.

## Separation from strategist

| | Strategist | Reviewer |
|---|---|---|
| Role | Creative idea generation | Critical relevance validation |
| Timing | Before OI | After OI |
| May add candidates | Yes (via OI bridge) | No |
| May change action | No | Yes |
| Prompt | Generate article ideas | Score existing recommendations |

## Position in pipeline

```text
Opportunity Intelligence ranking
  → AI Recommendation Reviewer
  → Final Create / Refresh / Monitor / Ignore queues
```

## Inputs

Rich context via `build_reviewer_context()` (prompt v2):

- **Site:** workspace URL, products, categories, niche, existing articles, coverage, top entities
- **Competitor:** domains and gap topics from snapshots
- **Recommendations:** title, classification, origin bucket, evidence, OI scores

See `docs/recommendations/RECOMMENDATION_REVIEW.md` for full schema.

## Outputs per recommendation

- `site_fit`, `search_value`, `competitor_gap_value`, `duplicate_risk`, `commercial_value`
- `decision`: keep | reject | downrank | flag
- `recommended_action`: create | refresh | monitor | ignore
- `reason`

Legacy fields (`relevance_score`, etc.) remain populated for backward compatibility.

Stored as:

- `metadata_json.oi_action` — original OI action (immutable)
- `metadata_json.ai_review` — full reviewer verdict
- `action` column — final visible action

Audit tables: `ai_recommendation_review_runs`, `ai_recommendation_reviews`.

## Fail-open

When disabled, missing client, timeout, or parse error: `action` stays as OI output; no `ai_review` metadata.

## Configuration

| Variable | Default |
|---|---|
| `AI_RECOMMENDATION_REVIEW_ENABLED` | `true` |
| `AI_RECOMMENDATION_REVIEW_MODEL` | falls back to `OPENAI_LIGHT_MODEL` |
| `AI_RECOMMENDATION_REVIEW_MAX_ITEMS` | `80` |
| `AI_RECOMMENDATION_REVIEW_TIMEOUT_SECONDS` | `90` |
| `AI_RECOMMENDATION_REVIEW_MIN_CREATE_SCORE` | `0.70` |
| `AI_RECOMMENDATION_REVIEW_MIN_MONITOR_SCORE` | `0.40` |
| `RECOMMENDATION_MIN_SITE_FIT` | `0.60` |
| `RECOMMENDATION_MIN_SEARCH_VALUE` | `0.50` |
| `RECOMMENDATION_MAX_DUPLICATE_RISK` | `0.70` |

## Module

`app/ai_recommendation_reviewer/` — context, service, applier, parser.

Prompt: `app/prompts/templates/ai_recommendation_reviewer.yaml`
