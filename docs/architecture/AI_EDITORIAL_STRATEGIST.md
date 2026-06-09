# AI Editorial Strategist

## Purpose

The AI Editorial Strategist generates **site-specific article ideas** (not articles) from products, categories, content inventory, coverage gaps, and summarized competitor SEO patterns. It runs **before** Opportunity Intelligence (OI) ranking and feeds OI as `source_type=ai_editorial_strategist`.

## Position in pipeline

```text
Site analysis → niche + inventory → deterministic sources + EOG
  → AI Editorial Strategist
  → Opportunity Intelligence ranking
  → AI Recommendation Reviewer (separate module)
  → Final queues
```

## Inputs

| Input | Source |
|---|---|
| Site profile | `autopilot_workspaces`, `site_understanding` |
| Niche profile | `workspace_niche_profiles` |
| Products / categories | `known_products`, `known_categories`, content inventory |
| Existing content | `workspace_content_inventory`, `published_content` |
| Coverage gaps | `content_coverage` |
| Competitor SEO patterns | `build_competitor_seo_intelligence` (gaps/patterns only) |
| EOG titles (dedup) | `editorial_opportunity_concepts` finalists |

## Outputs

- Persisted rows in `ai_editorial_strategist_runs` / `ai_editorial_strategist_ideas`
- OI candidates via bridge with `source_type=ai_editorial_strategist`
- UI explainability: source label + rationale (no prompts)

## Fail-open

When disabled, missing OpenAI client, timeout, or parse error: returns empty ideas; OI behavior unchanged.

## Configuration

| Variable | Default |
|---|---|
| `AI_EDITORIAL_STRATEGIST_ENABLED` | `true` |
| `AI_EDITORIAL_STRATEGIST_MODEL` | falls back to `OPENAI_LIGHT_MODEL` |
| `AI_EDITORIAL_STRATEGIST_MAX_IDEAS` | `40` |
| `AI_EDITORIAL_STRATEGIST_TIMEOUT_SECONDS` | `90` |

## Module

`app/ai_editorial_strategist/` — context builder, service, bridge, parser.

Prompt: `app/prompts/templates/ai_editorial_strategist.yaml`
