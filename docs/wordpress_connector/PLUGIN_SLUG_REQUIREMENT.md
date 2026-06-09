# Plugin requirement: apply `slug` on draft create/update

**Status:** Not implemented in deployed Trendplot Connector (verified against `magpern/TrendplotConnector` `main`, `DraftManager.php`).

Trendplot sends `"slug": "tb-500-vs-bpc-157"` in `POST /drafts` and `PATCH /drafts/{id}` when `recommended_slug` is set on the job. The plugin currently **ignores** this field and WordPress auto-generates `post_name` from the long post title.

**Symptom:** Rank Math URL-length warnings persist after **Run SEO Optimization** + **Update WordPress draft** / re-upload, even though Trendplot shows `recommended_slug: tb-500-vs-bpc-157`.

Trendplot detects this and returns `slug_sync_warning` when the connector response slug does not match the slug sent in the request.

---

## Required plugin change (`src/Publishing/DraftManager.php`)

### Create (`create` method)

Before `wp_insert_post`, parse optional slug:

```php
$post_name = '';
if (!empty($data['slug']) && is_string($data['slug'])) {
    $post_name = sanitize_title($data['slug']);
}

$post_id = wp_insert_post([
    'post_title'   => $title,
    'post_content' => $content,
    'post_excerpt' => $excerpt,
    'post_status'  => 'draft',
    'post_type'    => 'post',
    'post_name'    => $post_name, // empty string = WP auto-slug from title (current behavior)
], true);
```

### Update (`update` method)

When `slug` is present in the request body, include it in `$update_args`:

```php
if (isset($data['slug']) && is_string($data['slug']) && $data['slug'] !== '') {
    $update_args['post_name'] = sanitize_title($data['slug']);
}
```

Also treat `slug` as an updateable field in the validation block (`$has_post_fields`).

### Uniqueness

WordPress may append `-2` if the slug collides. Return the final `post_name` in the response `slug` field (already done).

---

## Deploy checklist

1. Patch `DraftManager.php` as above.
2. Deploy plugin to `staging.example.com` (and production when ready).
3. In Trendplot: **Run SEO Optimization** → **Update WordPress draft** (or re-upload draft).
4. Confirm WordPress permalink matches `recommended_slug` and `slug_sync_warning` is absent.

---

## What Trendplot does without this plugin fix

| Action | Effect on permalink |
|--------|---------------------|
| Run SEO Optimization | Sets `recommended_slug` locally only |
| Sync SEO to WordPress | Updates Rank Math canonical URL (metadata), **not** `post_name` |
| Update WordPress draft / re-upload | Sends `slug` in JSON; **no effect until plugin applies it** |

Until the plugin is patched, shorten the slug manually in the WordPress post editor (Permalink box).
