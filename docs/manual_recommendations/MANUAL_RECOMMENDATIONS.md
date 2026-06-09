# Manual Recommendations

## Purpose

Manual recommendations let operators add article ideas when automatic AI ideation misses an important topic. A short operator idea is enriched with AI into the same structured recommendation shape used by ideation, then flows through the existing recommendation queue and article generation pipeline.

Example input:

```text
BPC-157 and TB-500 are often discussed together. Why?
```

## User flow

```text
Manual idea
  ↓
AI enhancement
  ↓
structured recommendation
  ↓
recommendation queue
  ↓
generate article
```

### Input modes

1. **Quick idea** — headline only
2. **Guided idea** — headline, notes, optional products and content type
3. **Full custom brief** — headline, notes, products, content type, and target audience

### UI

On the Analyze Website **Recommendations** tab:

- Click **+ Manual idea**
- Enter headline and optional notes/products/type
- Click **Improve with AI**
- Review enriched preview (headline, abstract, content type, products, safety notes)
- **Add to recommendations**, **Edit**, or **Generate article**

Queued manual recommendations are labeled **Manual** and **AI-enhanced** in the recommendation list.

If a similar recommendation or article already exists, the UI shows:

```text
A similar recommendation or article may already exist.
```

The operator can continue anyway.

## API endpoints

Base path (no `/api` prefix in this app):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workspaces/{workspace_id}/manual-recommendations` | Create draft manual idea |
| `POST` | `/workspaces/{workspace_id}/manual-recommendations/create-and-enrich` | Create and enrich in one step |
| `GET` | `/workspaces/{workspace_id}/manual-recommendations` | List manual recommendations |
| `POST` | `/workspaces/{workspace_id}/manual-recommendations/{id}/enrich` | Enrich existing draft |
| `POST` | `/workspaces/{workspace_id}/manual-recommendations/{id}/queue` | Convert to `opportunity_recommendations` row |
| `POST` | `/workspaces/{workspace_id}/manual-recommendations/{id}/archive` | Archive manual + linked recommendation |

### Example payloads

Quick idea:

```json
{
  "raw_headline": "BPC-157 and TB-500",
  "raw_notes": ""
}
```

Guided idea:

```json
{
  "raw_headline": "BPC-157 and TB-500 are often discussed together",
  "raw_notes": "Explain why researchers compare them. Focus on literature themes and differences. Avoid combined-use advice.",
  "content_type": "relationship",
  "selected_products": ["BPC-157", "TB-500"]
}
```

Queue with duplicate override:

```json
{
  "allow_duplicates": true
}
```

## Data model

Table: `manual_recommendations` (migration `0017_manual_recommendations`)

| Field | Description |
|-------|-------------|
| `id` | Primary key |
| `workspace_id` | Workspace FK |
| `source` | Always `manual` |
| `status` | `draft`, `enriched`, `queued`, `article_generated`, `archived`, `failed` |
| `raw_headline` | Operator headline/idea |
| `raw_notes` | Operator notes |
| `enhanced_headline` | AI-improved headline |
| `abstract` | Short abstract |
| `search_intent` | Inferred search intent |
| `content_type` | Inferred content type |
| `recommendation_type` | Usually `create` |
| `related_products_json` | Catalog-linked products |
| `related_topics_json` | Related research topics |
| `target_audience` | Audience label |
| `priority_reason` | Why this idea matters |
| `safety_notes_json` | Compliance notes |
| `recommendation_id` | Linked `opportunity_recommendations` row when queued |
| `ai_enriched_at` | Enrichment timestamp |
| `created_by` | Optional operator id |

Queued items are bridged into `opportunity_recommendations` with `source_type = manual_recommendation`. Manual rows are preserved when AI ideation reruns and replaces non-manual recommendations.

## Prompt behavior

Template: `app/prompts/templates/manual_recommendation_enrichment.yaml`

Inputs:

- workspace brief (catalog, vertical context)
- `raw_headline`, `raw_notes`
- optional selected products
- optional content type and target audience hints

Output JSON:

```json
{
  "headline": "...",
  "abstract": "...",
  "search_intent": "...",
  "content_type": "...",
  "recommendation_type": "create",
  "related_products": [],
  "related_topics": [],
  "target_audience": "...",
  "priority_reason": "...",
  "safety_notes": []
}
```

The prompt improves headlines, infers article type and catalog products, and maintains research-use-only framing.

## Safety behavior

Post-enrichment validation (`app/manual_recommendations/safety.py`) blocks:

- dosing / dosage language
- treatment or therapeutic claims
- human-use guidance
- combined-use or stacking recommendations

Relationship articles may discuss that products are often compared in literature, but must not recommend combined use.

## Integration with article generation

Manual recommendations use the same article generation pipeline as ideation recommendations:

1. `manual_recommendation_to_row()` builds an `opportunity_recommendations` row
2. `metadata.article_brief` is produced via `enrich_article_opportunity_context()`
3. Article generation uses `enhanced_headline`, abstract, `raw_notes`, and `related_products`
4. `opportunity_context.source = manual_recommendation` is preserved in job request input
5. `origin_type = manual_recommendation` is set when generating from the UI

No separate article generator is used.

## Duplicate prevention

Before queueing, deterministic Jaccard similarity compares the enriched headline against existing recommendations (and optionally articles). Similar matches return `requires_confirmation: true` unless `allow_duplicates: true`.

## Key files

- `app/manual_recommendations/service.py` — `ManualRecommendationService`
- `app/manual_recommendations/mapper.py` — bridge to recommendation rows
- `app/manual_recommendations/safety.py` — compliance guard
- `app/manual_recommendations/duplicates.py` — similarity check
- `app/api/routes.py` — HTTP routes
- `app/analyze_ui.py` — Recommendations UI modal
- `tests/test_manual_recommendations.py` — unit tests

## Example enrichment output

Input:

```text
BPC-157 and TB-500 are often discussed together. Why?
```

Expected enrichment (representative):

```json
{
  "headline": "Why BPC-157 and TB-500 Are Often Discussed Together in Research Literature",
  "abstract": "A research-focused relationship article explaining overlapping themes, differences, and evidence boundaries.",
  "search_intent": "product_relationship",
  "content_type": "relationship",
  "recommendation_type": "create",
  "related_products": ["BPC-157", "TB-500"],
  "related_topics": ["tissue repair research", "peptide comparison", "preclinical literature"],
  "target_audience": "Research readers comparing related peptide topics",
  "priority_reason": "Captures a common cross-product question not always discovered automatically.",
  "safety_notes": ["Research-use-only framing; no combined-use recommendations; no dosing or treatment guidance."]
}
```
