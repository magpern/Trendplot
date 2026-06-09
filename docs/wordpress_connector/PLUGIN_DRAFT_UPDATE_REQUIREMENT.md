# Plugin requirement: update existing Trendplot draft

**Status:** Implemented in Trendplot Connector (staging verified 2026-06-08). Trendplot app update flow is live.

**Verified:** Staging site (`staging.example.com`) returns plugin JSON `not_found` for unknown post IDs on `PATCH /wp-json/trendplot/v1/drafts/{id}` (route registered).

---

## Endpoint

```
PATCH /wp-json/trendplot/v1/drafts/{id}
```

- `{id}` — WordPress post ID (integer)
- Auth — same HMAC headers as `POST /drafts`
- Content-Type — `application/json`
- Body — exact JSON string used for HMAC signature

---

## Expected behavior

### Allowed updates

Update **only** when all of the following are true:

1. Post exists.
2. Post was created by Trendplot (`_trendplot_article_id` meta is set).
3. `_trendplot_article_id` in the request body **matches** the post’s stored meta (ownership).
4. Post status is one of: `draft`, `pending`, `future`.

### Rejected updates

| Condition | HTTP | Suggested `code` | Trendplot maps to |
|-----------|------|------------------|-------------------|
| Post not found | 404 | `post_not_found` | `missing_draft` |
| Post exists but no Trendplot meta | 403 | `not_trendplot_draft` | `not_trendplot_draft` |
| `trendplot_article_id` mismatch | 403 | `forbidden` | `not_trendplot_draft` |
| Post status is `publish` (or other live status) | 409 | `published_post_rejected` | `published_post_rejected` |
| Invalid body | 400 | `validation_failed` | `validation_error` |
| HMAC failure | 401 | `unauthorized` | `auth_failed` |
| Other server errors | 5xx | `internal_error` | `connector_error` |

**Must not** change post status (no publish, no pending→publish, no trash).

---

## Request body

Same shape as `POST /drafts` (full replace of editable fields):

```json
{
  "title": "Updated title",
  "content": "<p>Updated publishable HTML</p>",
  "excerpt": "Updated excerpt",
  "categories": [],
  "tags": [],
  "trendplot_article_id": "job-uuid-from-trendplot",
  "trendplot_source": "trendplot",
  "trendplot_generated": "2026-06-08T12:00:00Z",
  "related_products": [101, 102],
  "related_articles": []
}
```

Plugin should:

- Update `post_title`, `post_content`, `post_excerpt`
- Update taxonomies when arrays provided
- Update `_trendplot_*` meta (`_trendplot_generated`, `_trendplot_source`, `_trendplot_related_products`, `_trendplot_related_articles`, `_trendplot_last_sync`)
- Preserve WordPress post ID

---

## Response (200 OK)

```json
{
  "id": 4608,
  "title": "Updated title",
  "slug": "updated-slug",
  "status": "draft",
  "url": "https://example.com/?p=4608",
  "edit_url": "https://example.com/wp-admin/post.php?post=4608&action=edit",
  "modified_at": "2026-06-08T12:05:00+00:00",
  "trendplot_article_id": "job-uuid-from-trendplot"
}
```

Trendplot will store `edit_url`, `url`, `status`, and set local `wordpress_draft_updated_at` / `last_wordpress_sync_at`.

---

## Relationship to existing endpoints

| Endpoint | Use |
|----------|-----|
| `POST /drafts` | First-time create; 409 when `trendplot_article_id` exists |
| **`PATCH /drafts/{id}`** | **Regeneration / repair sync to same post** |
| `PATCH /posts/{id}/meta` | Meta-only tagging of existing content (not sufficient for content refresh) |

After `PATCH /drafts/{id}` exists, `POST /drafts` 409 responses should continue to return `existing_id` so Trendplot can link and offer **Update existing WordPress draft**.

---

## Claude / plugin implementation prompt

Implement `PATCH /wp-json/trendplot/v1/drafts/{id}` in the Trendplot Connector WordPress plugin:

1. Register REST route with `edit_posts` capability check and existing HMAC middleware.
2. Load post by ID; 404 if missing.
3. Require `_trendplot_article_id` post meta; 403 if absent.
4. Require body `trendplot_article_id` equals stored meta; 403 on mismatch.
5. Reject if `post_status` not in `draft`, `pending`, `future` with code `published_post_rejected`.
6. Update title, content, excerpt, **slug** (`post_name` when `slug` is sent), categories, tags from body (mirror `POST /drafts` sanitization). See [PLUGIN_SLUG_REQUIREMENT.md](./PLUGIN_SLUG_REQUIREMENT.md).
7. Update Trendplot meta whitelist keys; set `_trendplot_last_sync` to now.
8. Do **not** change `post_status`.
9. Return JSON with `id`, `edit_url`, `url`, `status`, `modified_at`, `trendplot_article_id`.
10. Add plugin tests: happy path, wrong owner, published post rejected, missing post.

Reference: Trendplot app trace in `DRAFT_UPDATE_TRACE.md`; API contract draft in `docs/wordpress/CONNECTOR_API_CONTRACT.md` and `DRAFT_PUBLISHING_CONTRACT.md`.
