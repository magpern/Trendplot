# Trendplot Connector — API Contract (v1)

**Namespace:** `/wp-json/trendplot/v1`  
**Direction:** Trendplot initiates requests; plugin responds. No V1 dependency on webhooks or event buses.  
**Envelope:** All responses use `ConnectorEnvelope` shape (see [existing schemas](../../app/connectors/wordpress_schemas.py)).

### V1 call sequence (reference)

```text
GET  /inventory | /products | /posts | /pages | /content/search
POST /drafts → PATCH /drafts/{id} → POST /media → POST /relationships
GET  /internal-link-candidates   (Phase 3)
```

See [CONNECTOR_ARCHITECTURE.md](./CONNECTOR_ARCHITECTURE.md) and [CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md).

```json
{
  "ok": true,
  "api_version": "v1",
  "plugin_version": "1.0.0",
  "site_id": "site_abc",
  "data": {},
  "warnings": [],
  "request_id": "req_123"
}
```

**Auth (Phase 1+):** HMAC headers on every request:

- `Authorization: Bearer {token}`
- `X-Trendplot-Site-ID`
- `X-Trendplot-Timestamp`
- `X-Trendplot-Signature`

**Stable error codes:** `unauthorized`, `forbidden`, `validation_failed`, `post_not_found`, `rate_limited`, `capability_not_supported`, `internal_error` (full list in schemas).

---

## Phase availability

| Endpoint | Phase |
|----------|-------|
| health, site-info, inventory, posts, pages, products, content/search | 1 |
| drafts, media, relationships | 2 |
| internal-link-candidates, rankmath/meta | 3 |
| (Trendplot license/heartbeat ingest — not plugin REST) | 4 |

---

## GET /health

| | |
|--|--|
| **Purpose** | Liveness and version probe |
| **Auth** | Optional unsigned ping; signed recommended |
| **Capability** | None |

**Response `data`:**

```json
{
  "status": "ok",
  "wordpress_version": "6.7",
  "woocommerce_active": true,
  "rankmath_active": false
}
```

---

## GET /site-info

| | |
|--|--|
| **Purpose** | Site binding verification and capability discovery |
| **Auth** | Required |
| **Capability** | `read` |

**Response `data`:** Site name, `home_url`, timezone, locale, `capabilities` map, supported API version.

**Legacy alias:** `GET /site-summary` (Trendplot client today) — implement as alias in Phase 1.

---

## GET /inventory

| | |
|--|--|
| **Purpose** | Full inventory snapshot for analyze, ideation, scheduling |
| **Auth** | Required |
| **Capability** | `read` + `read_products` if WooCommerce |

**Query:** `updated_after` (ISO8601), `limit`, `cursor`, `include` (`posts,pages,products,taxonomies`)

**Response `data`:** See [CONNECTOR_INVENTORY_SCHEMA.md](./CONNECTOR_INVENTORY_SCHEMA.md).

**Pagination:** Cursor-based; default `limit=100`, max `500`.

**Idempotency:** Read-only.

---

## GET /posts

| | |
|--|--|
| **Purpose** | Paginated blog posts |
| **Auth** | Required |
| **Capability** | `read` |

**Query:** `status`, `updated_after`, `limit`, `cursor`, `search`

**Response `data.items[]`:** Post objects per inventory schema.

---

## GET /pages

| | |
|--|--|
| **Purpose** | Paginated pages |
| **Auth** | Required |
| **Capability** | `read` |

Same query/response shape as `/posts` with `type: page`.

---

## GET /products

| | |
|--|--|
| **Purpose** | Paginated WooCommerce products |
| **Auth** | Required |
| **Capability** | `read_products` |

**Query:** `status`, `updated_after`, `limit`, `cursor`, `search`, `category`

**Response `data.items[]`:** Product objects per inventory schema.

**Legacy alias:** `GET /inventory/products`.

---

## GET /content/search

| | |
|--|--|
| **Purpose** | Determine whether content already exists **before** generating new recommendations or articles |
| **Auth** | Required (HMAC — same as all Phase 1 reads) |
| **Capability** | `read` (+ `read_products` when `content_types` includes `product`) |
| **Phase** | **1** — required for ideation quality, not deferred |

**Why Phase 1:** Duplicate prevention and clustering run **before** draft generation. Without `/content/search`, ideation relies on crawl guesses and produces redundant recommendations.

### Request

Query parameters or JSON body (GET with query preferred):

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search text (title, slug, focus keyword, headline) |
| `content_types` | string[] | no | `post`, `page`, `product`. Default: `["post","page"]`. Repeat param or comma-separated accepted. |
| `limit` | int | no | Default `20`, max `50` |
| `modified_after` | string | no | ISO8601 — only return items modified after this time (refresh / incremental clustering) |
| `cursor` | string | no | Pagination cursor |
| `status` | string | no | Filter: `publish`, `draft`, `any` (default `publish,draft`) |

**Example:**

```http
GET /wp-json/trendplot/v1/content/search?query=BPC-157+storage&content_types[]=post&content_types[]=page&limit=10
```

### Response `data`

| Field | Type | Description |
|-------|------|-------------|
| `items` | array | Result rows (see below) |
| `next_cursor` | string | null if no more pages |
| `has_more` | boolean | |

Each **item**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int/string | WordPress post ID or product ID |
| `title` | string | Display title |
| `slug` | string | |
| `url` | string | Canonical public URL |
| `type` | string | `post`, `page`, `product` |
| `status` | string | `publish`, `draft`, etc. |
| `modified_at` | string | ISO8601 last modified |
| `word_count` | int | optional; estimated body length |
| `trendplot_generated` | boolean | true if `_trendplot_content_source` or Trendplot meta present |
| `related_products` | array | Product IDs or `{ id, name, slug }[]` linked to this content |

Optional: `content_hash`, `generated_at`, `recommendation_id`, `match_score` (0–1), `focus_keyword` (Rank Math).

### Primary use cases

| Use case | How Trendplot uses this endpoint |
|----------|----------------------------------|
| **Duplicate prevention** | Before approving ideation or starting generation, search `query=headline` or focus keyword; block or merge if strong match |
| **Refresh recommendations** | `modified_after` + age rules; flag stale posts for update — [CONTENT_LIFECYCLE.md](./CONTENT_LIFECYCLE.md) |
| **Follow-up article generation** | Search product/topic cluster; create sibling only when slot empty |
| **Article expansion** | Find thin (`word_count`) or outdated coverage on same `related_products` |
| **Content clustering** | Group by `related_products` + title similarity for calendar and reassessment |

### Response limits

| Limit | Value |
|-------|--------|
| Default `limit` | 20 items per request |
| Maximum `limit` | 50 items per request |
| Maximum pages per search session | Trendplot should cap at 5 cursors (250 items) unless operator overrides |
| `query` min length | 2 characters |
| `query` max length | 500 characters |

Plugin may return `warnings` in envelope when results are truncated.

### Pagination

- Cursor-based; stable ordering by `modified_at` desc then `id`
- Empty `items` is valid (no match — safe to create new content)
- Trendplot should paginate until `has_more` is false when building cluster views

### Auth and capability requirements

| Requirement | Detail |
|-------------|--------|
| Authentication | HMAC headers identical to `GET /inventory` |
| Unsigned / invalid signature | `401 unauthorized` |
| Missing `read` | `403 forbidden` |
| `content_types` includes `product` | Requires `read_products` capability |
| Rate limiting | `429 rate_limited` — Trendplot backs off and caches last result set |

### Errors

| Code | When |
|------|------|
| `validation_failed` | Missing `query` or invalid `content_types` |
| `rate_limited` | Too many searches per minute |

---

## POST /drafts

| | |
|--|--|
| **Purpose** | Create WordPress **draft** only |
| **Auth** | Required |
| **Capability** | `edit_posts` |
| **Phase** | 2 |

**Body:** See [DRAFT_PUBLISHING_CONTRACT.md](./DRAFT_PUBLISHING_CONTRACT.md).

**Idempotency:** `external_job_id` — if draft exists for same key, return existing `post_id` (200) instead of duplicate.

**Must not** set `status=publish` on this endpoint.

---

## PATCH /drafts/{id}

| | |
|--|--|
| **Purpose** | Update existing draft |
| **Auth** | Required |
| **Capability** | `edit_posts` |
| **Phase** | 2 |

**Body:** Partial fields (title, slug, excerpt, content_html, categories, tags, featured_media_id, `trendplot_meta`).

**Idempotency:** Safe to retry; last write wins with same payload hash.

---

## POST /media

| | |
|--|--|
| **Purpose** | Upload media file |
| **Auth** | Required |
| **Capability** | `upload_files` |
| **Phase** | 2 |

**Body:** multipart `file`, optional `alt_text`, `caption`, `usage`.

**Response:** `media_id`, `url`.

---

## POST /media/from-url

| | |
|--|--|
| **Purpose** | Sideload image from URL |
| **Phase** | 2 |

**Legacy alias:** existing Trendplot client path.

---

## POST /relationships

| | |
|--|--|
| **Purpose** | **Core feature** — link articles and products bidirectionally |
| **Auth** | Required |
| **Capability** | `edit_posts` + `edit_products` |
| **Phase** | 2 |

See [PRODUCT_ARTICLE_RELATIONSHIPS.md](./PRODUCT_ARTICLE_RELATIONSHIPS.md).

**Idempotency:** Same `(post_id, product_id, relation_type)` → no duplicate meta.

---

## GET /internal-link-candidates

| | |
|--|--|
| **Purpose** | Ranked link targets for generation pipeline |
| **Auth** | Required |
| **Capability** | `read` |
| **Phase** | 3 |

**Query/body:** `topic`, `products[]`, `entities[]`, `title`, `content_type`, `limit`

**Response:** `candidates[]` with `url`, `title`, `anchor_text_suggestions[]`, `reason`, `confidence`.

See [INTERNAL_LINKING.md](./INTERNAL_LINKING.md).

---

## GET /rankmath/meta

| | |
|--|--|
| **Purpose** | Read Rank Math SEO fields |
| **Phase** | 3 |
| **Graceful failure** | `capability_not_supported` if Rank Math inactive |

---

## POST /rankmath/meta

| | |
|--|--|
| **Purpose** | Write Rank Math SEO fields on post/product |
| **Phase** | 3 |
| **Constraint** | Only for Trendplot-managed drafts unless explicit override |

See [RANKMATH_INTEGRATION_PLAN.md](./RANKMATH_INTEGRATION_PLAN.md).

---

## Deferred to Phase 4 (plugin → Trendplot, minimal)

Not required for Phases 1–3:

| Mechanism | Role |
|-----------|------|
| Heartbeat `POST` → Trendplot | License + connection health |
| Webhooks / change feed | Optional inventory freshness |
| License revoke callback | Disconnect site |

Trendplot **must not** depend on these for analyze, ideation, or draft push.

---

## Appendix: Implemented in Trendplot backend today

| Contract endpoint | Current client method / path |
|-------------------|------------------------------|
| `/health` | `TrendplotWordPressConnectorClient.health()` |
| `/site-info` | `site_summary()` → `/site-summary` |
| `/inventory` | `content_inventory()` + `product_inventory()` |
| `/drafts` | `publish_post()` → `/posts/draft` |
| `/media` | `upload_featured_image_from_path()` |
| `/content/search` | **Not implemented** |
| `/relationships` | **Not implemented** |
| `/internal-link-candidates` | **Not implemented** |

Contract discovery: `GET /connectors/wordpress/contract` in Trendplot API.
