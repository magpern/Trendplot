# Draft Publishing Contract

Trendplot pushes generated articles to WordPress **as drafts** unless an explicit, gated live-publish action is taken elsewhere. The plugin owns WordPress/Woo/Elementor internals; Trendplot sends structured payloads.

**Phase:** 2 (depends on Phase 1 inventory for product ID resolution).

---

## Principles

1. **Never auto-publish** via `POST /drafts` or default generation policy (`manual_review`, `auto_draft` only create drafts).
2. **Trendplot-initiated** — Trendplot calls plugin; plugin does not pull drafts from Trendplot.
3. **Idempotent create** — `external_job_id` maps 1:1 to a WordPress post for retries after 429/timeouts.
4. **Required Trendplot metadata** — every draft must carry lifecycle fields for duplicate detection and auditing.

---

## Required Trendplot post meta

Stored as post meta (prefix `_trendplot_`) or a single JSON blob `_trendplot_meta`:

| Field | Required | Purpose |
|-------|----------|---------|
| `content_hash` | **yes** | SHA-256 of normalized article body (markdown or HTML stripped). Future duplicate detection: skip regenerate if hash exists for workspace. |
| `generated_at` | **yes** | ISO8601 UTC when Trendplot finished generation |
| `recommendation_id` | **yes** | Source recommendation / content-plan item / ideation row id |
| `opportunity_id` | conditional | AI ideation opportunity id when `source=ai_opportunity_ideation` |
| `source` | **yes** | e.g. `ai_opportunity_ideation`, `content_plan_item`, `operator_recommendation` |
| `trendplot_generated` | **yes** | `true` on all Trendplot-originated posts |
| `related_products` | **yes** | Array of product slugs or Woo IDs (prefer IDs after Phase 1 inventory sync) |
| `last_ai_refresh` | optional | Set on PATCH/regeneration — see [CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md) |
| `search_intent` | **yes** | From ideation metadata |
| `content_type` | recommended | `guide`, `comparison`, `faq`, etc. |
| `target_audience` | optional | From ideation |
| `safety_notes` | optional | RUO / compliance notes array |
| `external_job_id` | **yes** | Trendplot `jobs.id` |
| `workspace_id` | **yes** | Autopilot workspace |

### content_hash algorithm (normative)

```text
sha256( normalize_whitespace( article_markdown_or_html ) )
```

- Strip trailing whitespace per line
- Single newline between blocks
- Exclude volatile fields (dates in footer, random ids)

Trendplot computes before `POST /drafts`; plugin stores verbatim. Future `GET /content/search` may index by hash.

### Lifecycle use cases

| Use case | Fields used |
|----------|-------------|
| Duplicate detection | `content_hash`, `recommendation_id`, title search via `/content/search` |
| Refresh recommendation | Same `recommendation_id`, newer `generated_at` |
| Audit trail | `external_job_id`, `workspace_id`, `source` |
| Product linkage | `related_products` → `POST /relationships` |

---

## POST /drafts — create

### Request body

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `external_job_id` | string | yes | Idempotency key |
| `title` | string | yes | Post title |
| `slug` | string | no | Auto from title if omitted |
| `excerpt` | string | no | Meta description candidate |
| `content_html` | string | yes | Sanitized HTML from Trendplot renderer |
| `status_policy` | string | yes | Must be `draft` |
| `categories` | int[] | no | Category term IDs |
| `tags` | string[] or int[] | no | Tag names or IDs |
| `featured_media_id` | int | no | After `POST /media` |
| `template` | object | no | Elementor template key |
| `seo` | object | no | title, description, canonical (Phase 3 Rank Math) |
| `trendplot_meta` | object | yes | Required fields table above |
| `related_product_ids` | int[] | no | Woo IDs; triggers relationship write if present |

### Response `data`

```json
{
  "post_id": 12345,
  "status": "draft",
  "url": "https://example.com/?p=12345",
  "edit_url": "https://example.com/wp-admin/post.php?post=12345&action=edit",
  "content_hash": "abc..."
}
```

### Errors

| Code | When |
|------|------|
| `validation_failed` | Missing `trendplot_meta.content_hash` or `external_job_id` |
| `live_publish_disabled` | Attempt to publish via draft endpoint |

---

## PATCH /drafts/{id}

Update after humanization rerun, sanity rewrite, or operator edit in Trendplot.

| Field | Notes |
|-------|-------|
| `content_html` | Full replace |
| `trendplot_meta.content_hash` | Must update when body changes |
| `trendplot_meta.generated_at` | Update on regeneration |
| Partial SEO / categories | Supported |

---

## Media flow

1. Trendplot `POST /media` or `/media/from-url` with featured image
2. `POST /drafts` or `PATCH` with `featured_media_id`
3. Inline images: embed URLs in HTML or attach via media IDs in content

---

## Related products (core)

After draft create, Trendplot calls `POST /relationships` with:

- `post_id` from draft response
- `product_ids` from inventory-resolved `related_products`
- `primary_product_id` when single product article

See [PRODUCT_ARTICLE_RELATIONSHIPS.md](./PRODUCT_ARTICLE_RELATIONSHIPS.md).

---

## Mapping from Trendplot today

| Today | Target |
|-------|--------|
| [`ConnectorDraftPostRequest`](../../app/connectors/wordpress_schemas.py) | Extend with `trendplot_meta` object |
| [`JobService._publish_to_wordpress`](../../app/services/jobs.py) | Populate meta from job + `opportunity_context` |
| `wordpress_presentation_metadata` artifact | Maps to `seo` + categories/tags |
| Publish policies in config | Gate live publish only on explicit endpoint |

---

## Live publish (out of scope for draft contract)

Live publish requires:

- `ALLOW_LIVE_PUBLISH=true`
- Separate gated action (operator confirm)
- Not part of default analyze → draft pipeline
