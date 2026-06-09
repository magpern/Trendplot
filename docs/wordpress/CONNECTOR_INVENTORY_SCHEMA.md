# Inventory Schema

Inventory is the **primary Phase 1 deliverable**. Accurate payloads improve website understanding, AI ideation, duplicate avoidance (`GET /content/search`), scheduling, and (later) internal linking.

**Source:** Plugin `GET /inventory`, `/posts`, `/pages`, `/products` (Trendplot pulls).  
**Target store:** Trendplot `workspace_content_inventory` (merged; crawl fallback).

---

## Envelope item — common fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | WordPress post ID |
| `type` | string | `post`, `page`, `product` |
| `title` | string | |
| `slug` | string | |
| `url` | string | Canonical public URL |
| `status` | string | `publish`, `draft`, `private` |
| `author_id` | int | |
| `published_at` | string | ISO8601 or null |
| `modified_at` | string | ISO8601 |
| `excerpt` | string | |
| `primary_category` | object | `{ id, name, slug }` |
| `tags` | array | `{ id, name, slug }[]` |
| `canonical_url` | string | |
| `featured_image` | object | `{ id, url, alt }` |
| `rankmath` | object | null if inactive — see below |

---

## Rank Math block (optional)

```json
"rankmath": {
  "title": "",
  "description": "",
  "focus_keyword": "",
  "schema_type": "",
  "canonical": "",
  "robots": ""
}
```

If Rank Math inactive: `"rankmath": null`, no error.

---

## Post / page object

Extends common fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `content_type` | string | no | Editorial classification: `article`, `faq`, `landing` |
| `word_count` | int | **optional** | Estimated body word count; supports thin-content / expansion detection |
| `generated_by_trendplot` | boolean | **optional** | `true` when Trendplot meta or `_trendplot_content_source` present |
| `generated_at` | string | optional | ISO8601 — from `_trendplot` meta |
| `content_hash` | string | optional | SHA-256 of normalized body — duplicate detection |
| `related_products` | array | optional | Linked product IDs or `{ id, name, slug }[]` |
| `primary_product` | object | optional | `{ id, name, slug }` — main commercial focus |
| `last_ai_refresh` | string | optional | ISO8601 last Trendplot refresh/regeneration |
| `related_product_ids` | int[] | optional | Legacy alias of `related_products` as IDs only |

### How lifecycle fields support Trendplot

| Field | Enables |
|-------|---------|
| `word_count` | **Expansion candidates** — flag articles under target depth vs topic |
| `generated_by_trendplot` | **Lifecycle** — distinguish Trendplot vs legacy editorial |
| `generated_at` / `last_ai_refresh` | **Refresh recommendations** and **stale content detection** vs workspace age policy |
| `content_hash` | **Duplicate avoidance** — skip regenerate if hash unchanged |
| `related_products` / `primary_product` | **Product-linked content**, clustering, ideation validation |
| `modified_at` (common field) | **Stale content detection** with `generated_at` / `last_ai_refresh` |
| Combined with `GET /content/search` | **Follow-up**, **refresh**, and **clustering** without crawl |

### Stale content detection (normative)

A post is a **stale candidate** when:

- `status=publish`, and
- `now - coalesce(last_ai_refresh, generated_at, modified_at) > workspace.stale_months` (default 12), and
- not in retirement/archival set

Trendplot surfaces these in reassessment and schedule tabs; plugin supplies dates, Trendplot applies policy.

See [CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md).

---

## WooCommerce product object

| Field | Type | Notes |
|-------|------|-------|
| `sku` | string | |
| `name` | string | |
| `short_description` | string | HTML stripped |
| `description` | string | optional; may truncate |
| `product_type` | string | `simple`, `variable` |
| `categories` | array | |
| `tags` | array | |
| `attributes` | array | `{ name, values[] }` |
| `price` | object | **Optional** — see visibility policy |
| `related_article_ids` | int[] | reverse relationships |
| `stock_status` | string | if safe to expose |

### Price visibility policy

- Include list/catalog price only when store policy allows (no hidden B2B pricing leaks)
- Omit `price` entirely for logged-in-only catalogs → Trendplot uses `price_visible: false`

---

## Taxonomies (in `/inventory` aggregate)

```json
"categories": [{ "id", "name", "slug", "parent_id", "count" }],
"tags": [{ "id", "name", "slug", "count" }]
```

Improves ideation category awareness vs crawl guesses.

---

## Mapping to Trendplot `workspace_content_inventory`

| Plugin field | Trendplot field |
|--------------|-----------------|
| `url` | `url`, `canonical_url` |
| `title` | `title` |
| `slug` | `slug` |
| `type` | `content_type` (`product` → `product`) |
| `modified_at` | `last_seen_at` |
| `id` | `wordpress_post_id` |
| — | `source`: `wordpress_plugin` |
| `rankmath.focus_keyword` | `metadata.focus_keyword` |

---

## Mapping to ideation inputs

| Inventory | Ideation use |
|-----------|--------------|
| Product names + SKUs | Validate `related_products` |
| Existing post titles | Reduce duplicate headlines via `/content/search` |
| Categories/tags | Calendar and content_type suggestions |
| `modified_at` | Refresh recommendations |

---

## Pagination

- `cursor` opaque string
- `has_more` boolean
- `limit` default 100, max 500

---

## Sync strategy (Trendplot)

1. Initial full `GET /inventory` on connect
2. Incremental `updated_after={last_sync}` on schedule (Trendplot cron)
3. On-demand before analyze run
4. Phase 4 webhooks optional trigger for (2)

**No** plugin-push inventory sync required in Phases 1–3.

---

## Quality metrics (Phase 1 acceptance)

| Metric | Target |
|--------|--------|
| Product count vs Woo admin | 100% match |
| Published posts indexed | ≥ crawl coverage |
| SKU present | >95% for simple products |
| Rank Math fields | Present when plugin active |
