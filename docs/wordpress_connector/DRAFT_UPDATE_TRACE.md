# Draft update — current app trace

Trace of how Trendplot sends articles to WordPress today, and where an **update existing draft** flow would plug in.

## Job fields (WordPress publish state)

Stored on the `jobs` table (`app/models.py`, updated via `JobRepository.update_wordpress_publish_state`):

| Column | Purpose |
|--------|---------|
| `wordpress_post_id` | WordPress post ID returned by connector |
| `wordpress_edit_url` | Admin edit link |
| `wordpress_public_url` | Front-end preview URL |
| `wordpress_status` | WordPress post status (`draft`, etc.) |
| `wordpress_draft_created_at` | ISO timestamp when draft was first created |
| `wordpress_connector_site_url` | Base URL of the connector site used for send |
| `wordpress_publish_error` | Last connector/publish error message |
| `wordpress_publish_attempted_at` | ISO timestamp of last send attempt |

| `wordpress_draft_updated_at` | ISO timestamp when draft content was last updated via connector |
| `last_wordpress_sync_at` | ISO timestamp of last successful create/update sync |

Exposed to UI via:

- `GET /jobs/{job_id}/generation-result` → `JobService.get_generation_result()` (`app/services/jobs.py`)
- `GET /jobs/recent` → `JobSummary` (`app/api/routes.py`)

## Connector HTTP call (create only)

| Layer | File | Function |
|-------|------|----------|
| Client | `app/connectors/phase1_client.py` | `TrendplotPhase1ConnectorClient.create_draft()` → `POST /drafts` |
| Service | `app/wordpress_connector/service.py` | `WordPressConnectorService.create_wordpress_draft()` |
| API | `app/api/routes.py` | `POST /jobs/{job_id}/wordpress-connector/draft` |
| Signing | `app/connectors/hmac_signing.py` | HMAC over `METHOD\nPATH\nTIMESTAMP\nBODY` |

Request body fields built in `create_wordpress_draft()`:

- `title`, `content` (publishable HTML), `excerpt`
- `categories`, `tags` (empty arrays in Phase 1)
- `trendplot_article_id` (Trendplot job ID)
- `trendplot_source`, `trendplot_generated`
- `related_products`, `related_articles`

Publishable HTML source: `JobService._resolve_publishable_html(job_id)`.

## Current create flow

```text
User clicks "Send to WordPress as draft" (Analyze UI)
  → POST /jobs/{job_id}/wordpress-connector/draft
  → WordPressConnectorService.create_wordpress_draft()
      → if wordpress_post_id set and not force: return status "existing" (no HTTP call)
      → if force: clear local wordpress_* fields, then create
      → POST /wp-json/trendplot/v1/drafts
      → on 201: store wordpress_post_id, edit_url, public_url, status=published_draft
      → on 409: store existing post ID + error "WordPress draft already exists"
      → on other errors: wordpress_publish_error + status failed_publish
```

## UI entry points

| UI | File | Control |
|----|------|---------|
| Analyze → Draft tab | `app/analyze_ui.py` | `renderSendToWordPressButton()` |
| Send | `data-send-wordpress` | `sendArticleToWordPress()` → `createConnectorDraft()` |
| Resend after delete | `data-resend-wordpress` | `sendArticleToWordPress(jobId, { force: true })` |
| Retry after error | "Try WordPress send again" | same as send |

When `wordpress_post_id` is set, UI shows **Open in WordPress** and **Send to WordPress again** (force new draft). There is **no Update WordPress draft** action.

## Duplicate / regeneration gap

1. Article sent → `wordpress_post_id` stored.
2. Article regenerated/repaired in Trendplot → publishable HTML changes locally.
3. User cannot push changes to the same WordPress post:
   - **Send** is blocked (`status: existing` or disabled when post ID exists).
   - **Send again (force)** clears local ID and creates a **new** draft (or hits 409 if plugin still maps `trendplot_article_id`).
4. Plugin `POST /drafts` returns **409** when `trendplot_article_id` already exists (idempotency).

Desired flow requires **`PATCH /wp-json/trendplot/v1/drafts/{id}`** on the plugin (not available yet — see `PLUGIN_DRAFT_UPDATE_REQUIREMENT.md`).

## Update flow (implemented)

```text
User clicks "Update WordPress draft"
  → POST /jobs/{job_id}/wordpress-connector/draft/update
  → WordPressConnectorService.update_wordpress_draft()
  → PATCH /wp-json/trendplot/v1/drafts/{wordpress_post_id}
  → store wordpress_draft_updated_at, last_wordpress_sync_at, clear publish error
```

| Layer | Implementation |
|-------|----------------|
| `phase1_client.py` | `update_draft(post_id, body_json)` |
| `service.py` | `update_wordpress_draft(job_id)` |
| `routes.py` | `POST /jobs/{id}/wordpress-connector/draft/update` |
| `analyze_ui.py` | **Update WordPress draft** / **Published in WordPress** UI states |
| Migration `0020` | `wordpress_draft_updated_at`, `last_wordpress_sync_at` on `jobs` |

## Status refresh (implemented)

```text
Refresh WordPress status (manual or auto if last sync > 5 min on Draft tab)
  → POST /jobs/{job_id}/wordpress-connector/status/refresh
  → GET /wp-json/trendplot/v1/drafts/{wordpress_post_id}
  → update wordpress_status, URLs, last_wordpress_sync_at
  → publish: UI shows Published in WordPress (no Update button)
  → 404: clear wordpress_post_id, show WordPress post missing
  → 403: keep link, show not managed by Trendplot
```

No plugin webhooks — pull-only.
