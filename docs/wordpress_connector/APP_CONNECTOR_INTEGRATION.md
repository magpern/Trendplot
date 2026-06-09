# Trendplot App ↔ WordPress Connector (Phase 1)

Integration with the [Trendplot Connector](https://github.com/magpern/TrendplotConnector) plugin Phase 1 write API.

Plugin reference commit: `7fa45f6b5bbfb9660113f0bc01129c0dd442b57e`.

## Endpoints used

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/wp-json/trendplot/v1/health` | Connection test |
| `GET` | `/wp-json/trendplot/v1/site-info` | Site/plugin metadata |
| `POST` | `/wp-json/trendplot/v1/drafts` | Create WordPress draft from generated article |
| `PATCH` | `/wp-json/trendplot/v1/drafts/{id}` | Update existing Trendplot-linked WordPress draft |
| `GET` | `/wp-json/trendplot/v1/drafts/{id}` | Pull current WordPress post status for a linked draft/post |
| `PATCH` | `/wp-json/trendplot/v1/posts/{id}/seo` | Push Rank Math SEO metadata |
| `GET` | `/wp-json/trendplot/v1/posts/{id}/seo` | Pull Rank Math SEO metadata |

Other Phase 2 endpoints (`/inventory`, live publish) are **not** used.

## HMAC signing contract

Headers:

- `X-Trendplot-Site-Id`
- `X-Trendplot-Timestamp`
- `X-Trendplot-Signature`

Signature string:

```text
METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + BODY
```

- `METHOD` — uppercase (`GET`, `POST`, …)
- `PATH` — exact request path including `/wp-json/trendplot/v1/...`
- `BODY` — exact JSON string sent on the wire; empty string for `GET`
- `HMAC-SHA256(signature_string, shared_secret)` as lowercase hex

Implementation: `app/connectors/hmac_signing.py`, `app/connectors/phase1_client.py`.

## Workspace settings

Stored in `workspace_wordpress_connector` (per workspace):

| Field | Notes |
|-------|--------|
| `connector_enabled` | Master switch |
| `wordpress_base_url` | Site origin, e.g. `https://test.example.com` |
| `trendplot_site_id` | Must match plugin Site ID |
| `trendplot_shared_secret` | Stored server-side only; never returned to UI after save |
| `last_connection_status` | `connected` / `failed` |
| `last_connection_checked_at` | ISO timestamp |
| `connector_plugin_version` | From `/health` or `/site-info` |
| `connector_api_version` | From plugin |

API:

- `GET /workspaces/{workspace_id}/wordpress-connector`
- `PUT /workspaces/{workspace_id}/wordpress-connector`
- `POST /workspaces/{workspace_id}/wordpress-connector/test`

Connector credentials are configured in the Analyze UI and stored per workspace. They are **not** read from `.env` at runtime.

## Publish draft flow

```text
Completed article job
  → load publishable_html artifact
  → POST /wp-json/trendplot/v1/drafts
  → store wordpress_post_id, edit_url, public_url on jobs row
  → UI shows Open in WordPress
```

API:

- `POST /jobs/{job_id}/wordpress-connector/draft` — create
- `POST /jobs/{job_id}/wordpress-connector/draft/update` — update linked draft

Request body fields:

- `title`, `content` (publishable HTML), `excerpt`
- `categories`, `tags` (empty arrays in Phase 1)
- `trendplot_article_id` — Trendplot job ID
- `trendplot_source`, `trendplot_generated`
- `related_products` — WordPress product IDs only when known in inventory
- `related_articles` — empty in Phase 1
- `slug` — optional; Trendplot sends `recommended_slug` when set. **Requires plugin support** — see [PLUGIN_SLUG_REQUIREMENT.md](./PLUGIN_SLUG_REQUIREMENT.md). Without it, WordPress auto-slugs from the title.

Job columns updated: `wordpress_post_id`, `wordpress_edit_url`, `wordpress_public_url`, `wordpress_status`, `wordpress_draft_created_at`, `wordpress_connector_site_url`, `wordpress_publish_error`, `wordpress_publish_attempted_at`.

## Send draft flow

```text
Completed article job (no wordpress_post_id)
  → user clicks Send to WordPress as draft
  → POST /jobs/{job_id}/wordpress-connector/draft
  → POST /wp-json/trendplot/v1/drafts
  → store wordpress_post_id, edit_url, public_url
  → UI: Open in WordPress
```

## Update draft flow

```text
Article already linked (wordpress_post_id set, status draft/pending/future)
  → article regenerated/repaired in Trendplot
  → user clicks Update WordPress draft
  → POST /jobs/{job_id}/wordpress-connector/draft/update
  → PATCH /wp-json/trendplot/v1/drafts/{wordpress_post_id}
  → store wordpress_draft_updated_at, last_wordpress_sync_at, clear publish error
```

Published WordPress posts (`publish`, `published`, `private`) are not updated from Trendplot for **body content**.

See [DRAFT_UPDATE_TRACE.md](./DRAFT_UPDATE_TRACE.md).

## Status refresh flow

Trendplot pulls status from WordPress; the plugin does **not** push webhooks to Trendplot.

```text
Article linked (wordpress_post_id set)
  → user clicks Refresh WordPress status
    OR selected article auto-refreshes on Draft tab if last sync > 5 minutes
  → POST /jobs/{job_id}/wordpress-connector/status/refresh
  → GET /wp-json/trendplot/v1/drafts/{wordpress_post_id}
  → store wordpress_status, edit_url, public_url, last_wordpress_sync_at
```

**Publish detection:** if WordPress returns `status: publish`, UI shows **Published in WordPress** and hides **Update WordPress draft**.

**Missing post (404):** clears local `wordpress_post_id`; UI shows **WordPress post missing** and offers **Send to WordPress as draft**.

**Not managed (403):** keeps post ID/URLs; UI shows **WordPress post no longer managed by Trendplot**.

API: `POST /jobs/{job_id}/wordpress-connector/status/refresh`

**Limitation:** no automatic plugin webhooks — status is pull-only via refresh (manual or 5-minute auto-refresh for the selected article on Draft tab open).

## SEO package generation

Trendplot generates a Rank Math SEO package independently of article generation. The user reviews and edits fields before syncing.

```text
Completed article job
  → user clicks Generate SEO
  → POST /jobs/{job_id}/seo/generate
      (alias: POST /jobs/{job_id}/seo/package)
  → LLM builds SEO package from article title, publishable content, keyword, product context
  → store seo_* fields on jobs row + seo_generated_at
  → no automatic WordPress sync
```

**Package shape (LLM output):**

```json
{
  "title": "...",
  "description": "...",
  "focus_keyword": "...",
  "canonical_url": "",
  "robots": [],
  "schema_type": "Article"
}
```

**Rules:**

- One concise focus keyword phrase
- SEO title includes focus keyword where natural (~60 chars when practical)
- Meta description includes focus keyword where natural (~160 chars when practical)
- No keyword stuffing
- `robots` defaults to `[]` (index/follow). Rank Math only stores negative directives (`noindex`, `nofollow`, …)
- `canonical_url` blank unless confidently known
- Prefer `schema_type: "Article"`

**Job SEO columns:** `seo_title`, `seo_description`, `seo_focus_keyword`, `seo_canonical_url`, `seo_robots`, `seo_schema_type`, `seo_generated_at`, `seo_synced_at`, `seo_last_error`, `rank_math_score` (nullable).

API:

- `POST /jobs/{job_id}/seo/generate` — generate package
- `PUT /jobs/{job_id}/seo` — save edited fields
- `POST /jobs/{job_id}/seo/sync` — push to WordPress
- `POST /jobs/{job_id}/seo/refresh` — pull from WordPress

## Rank Math sync

```text
Article linked (wordpress_post_id set)
  → user reviews SEO fields
  → POST /jobs/{job_id}/seo/sync
  → PATCH /wp-json/trendplot/v1/posts/{wordpress_post_id}/seo
      body: { "seo": { title, description, focus_keyword, canonical_url, robots, schema_type } }
  → store seo_synced_at, clear seo_last_error
```

**Published posts:** SEO sync is allowed for draft **and** published Trendplot-managed posts.

**Failures:** `seo_last_error` is stored on the job; UI shows the last sync error.

## Refresh SEO from WordPress

```text
Article linked (wordpress_post_id set)
  → user clicks Refresh SEO from WordPress
  → POST /jobs/{job_id}/seo/refresh
  → GET /wp-json/trendplot/v1/posts/{wordpress_post_id}/seo
  → update local seo_* fields (+ rank_math_score when exposed)
```

Useful when SEO was edited manually in the WordPress Rank Math panel.

## Rank Math score limitations

- `rank_math_score` is optional and only populated when the connector/plugin exposes it in the SEO GET response.
- Trendplot does not compute Rank Math scores locally.
- If the plugin omits the score, the UI hides the score line.

## SEO Optimization Pass (deterministic)

Trendplot runs a **deterministic SEO Optimization Pass** after article generation and SEO package generation, and before WordPress draft upload/update and SEO sync. This is **not** an LLM rewrite pass.

```text
Article + SEO package available
  → run_seo_optimization_pass (no OpenAI call)
  → update structured article JSON + publishable HTML
  → update seo_* fields / recommended_slug / alt suggestions
  → store seo_optimization_report artifact
```

API:

- `POST /jobs/{job_id}/seo/optimize` — explicit **Run SEO Optimization** (overwrites manually edited SEO fields)

Automatic runs use `respect_manual_seo=True` and preserve fields when `seo_manually_edited=true` (set by **Save SEO**). Explicit optimization resets SEO field improvements.

**What it improves (Rank Math checklist oriented):**

| Area | Behavior |
|------|----------|
| Focus keyword | Title, meta description, intro (first ~10%), one H2/H3, body density (3–5 for long articles) without stuffing |
| SEO title | Adds keyword and safe power words (`Key`, `Research`, …) — no clickbait or therapeutic claims |
| Meta description | Keyword when natural, ~140–160 chars, RUO-safe wording |
| Slug | `recommended_slug` — short, lowercase, hyphenated; sent on draft create/update when post is not published |
| Internal links | **Article-to-article** links from workspace jobs/inventory with public post URLs (1–3 relevant links) |
| Paragraphs | Splits paragraphs over ~140 words at sentence boundaries (no LLM) |
| Images | `suggested_featured_image_alt` / `suggested_inline_image_alt` only — does not generate images |

**Job columns:** `recommended_slug`, `seo_manually_edited`, `suggested_featured_image_alt`, `suggested_inline_image_alt`, `seo_optimized_at`.

### SEO metadata sync vs article-body optimization

| | SEO sync (`/seo/sync`) | SEO Optimization Pass |
|--|------------------------|------------------------|
| Target | Rank Math title, description, focus keyword, robots, schema | Article body + local SEO fields + slug recommendation |
| WordPress API | `PATCH /posts/{id}/seo` | Draft body via `POST/PATCH /drafts` |
| LLM | No (push only) | No |

### Rank Math limitations

- WooCommerce **product** links may **not** satisfy Rank Math’s internal-link check. The optimization pass adds **article/post** links from other Trendplot jobs with `wordpress_public_url`.
- Product links still come from the editorial product linker; they are complementary, not interchangeable.
- `rank_math_score` is only shown when the plugin returns it from `GET /posts/{id}/seo`.

### Recommended slug behavior

- Stored as `recommended_slug` on the job and shown read-only in the SEO panel.
- Included in draft create/update JSON as `slug` for **unsent / draft** posts only.
- Trendplot does **not** change an already-published WordPress permalink without explicit user action in WordPress.
- When the canonical URL path is too long, the optimization pass also sets a shorter `seo_canonical_url` based on `recommended_slug` (synced via **Sync SEO to WordPress**; does not change the live permalink on published posts).

### UI workflow notes

- **Run SEO Optimization** — local article + SEO field improvements in Trendplot.
- **Sync SEO to WordPress** — Rank Math metadata only (`title`, `description`, `focus_keyword`, `canonical_url`, `robots`, `schema_type`).
- **Update WordPress draft** — publishable HTML + `slug` for linked **draft** posts only.
- **Published posts** — body/slug optimizations remain in Trendplot until edited in WordPress; the UI shows a published-post notice.

### Image alt suggestions

Alt text suggestions are stored on the job for review. Featured image upload + alt sync requires future connector/plugin support; the optimization pass does not block on images.

### Article generation prompt alignment

`article_generation.yaml` still encourages Rank Math-friendly structure during generation. The optimization pass is a second deterministic safety net before WordPress sync.

## Duplicate handling

If the plugin returns `409 Conflict` for an existing `trendplot_article_id`:

- Trendplot stores the existing post ID and edit URL when provided
- UI shows **WordPress draft already exists**
- No second draft is created
- Trendplot stores the existing post ID and shows **Update WordPress draft** (no second draft created)

## Product relationships

`related_products` is populated only from `workspace_content_inventory` rows that already have `wordpress_post_id` and matching product `title`. Names are **not** guessed into IDs.

> **Phase 2 TODO:** Map product URLs/names to WordPress IDs via connector inventory or explicit relationship setup.

## Current limitations

- No live publish (draft only for body content)
- No connector inventory sync
- Draft body update requires connector plugin with `PATCH /drafts/{id}` deployed on the target WordPress site.
- Published WordPress post **bodies** cannot be updated from Trendplot.
- Rank Math score depends on plugin support in `GET /posts/{id}/seo`.
- All WordPress draft create/update/status sync goes through the connector (`POST /jobs/{id}/wordpress-connector/draft`, `POST /jobs/{id}/wordpress-connector/draft/update`, `POST /jobs/{id}/wordpress-connector/status/refresh`)
- No plugin push/webhooks to Trendplot

## UI

Analyze Website → **Draft** tab → **WordPress** panel:

- Connector status, plugin/API version, last checked
- Collapsible settings + **Test WordPress Connection**
- **Send to WordPress as draft** on article cards
- **Open in WordPress** / **Send to WordPress again** after draft exists
- **Update WordPress draft** when a linked draft is editable
- **Published in WordPress** label when `wordpress_status` is live (no update button)
- **Refresh WordPress status** on linked posts (auto-refresh for selected article if last sync > 5 min)

Selected article card → **SEO (Rank Math)** section:

- Editable SEO fields
- **Generate SEO**, **Run SEO Optimization**, **Save SEO**, **Sync SEO to WordPress**, **Refresh SEO from WordPress**
- Shows `seo_generated_at`, `seo_synced_at`, `seo_optimized_at`, `seo_last_error`, optional `rank_math_score`, compact optimization report

## Tests

- `tests/test_wordpress_connector_phase1.py` — HMAC signing, connection test, draft create, 409 duplicate, config/publishable guards, secret redaction, UI markers.
- `tests/test_job_seo_workflow.py` — SEO package generation, sync payload, refresh, validation, published post SEO sync, optional Rank Math score, UI markers.
- `tests/test_seo_optimization_pass.py` — deterministic keyword/title/meta/slug/link/paragraph/manual-edit guards.
