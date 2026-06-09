# Trendplot

Trendplot is an autonomous publishing intelligence platform built on the existing content generation engine. It can understand a website, infer publishing opportunities, build a content calendar, generate drafts, publish through WordPress safety gates, and reassess strategy over time.

## MVP Features

- `POST /generate-article`
- `POST /analyze-website`
- `GET /app` for the simplified Trendplot Workspace
- `GET /developer` for the advanced developer/admin dashboard
- `POST /autopilot/workspaces` for workspace onboarding
- `POST /autopilot/workspaces/{id}/analyze` for Website Intelligence
- `POST /autopilot/workspaces/{id}/generate-plan` for 30-day publishing plans
- `POST /autopilot/calendar-items/{id}/generate` for plan-driven content generation
- Lightweight website and competitor analysis for article suggestions
- Autopilot workspace state, site understanding snapshots, trend signals, content plans, reassessment reports, provider status, and approval events
- OpenAI article generation as structured JSON with canonical Markdown content
- SEO metadata generation
- Quality gate before any WordPress publishing
- Domain sanity gate for unsupported storage, handling, dosing, human-use, and therapeutic claims
- Elementor-friendly WordPress HTML renderer
- Placeholder image provider that does not insert placeholder images by default
- YouTube Data API candidate lookup with AI-assisted relevance filtering and optional embed
- Contextual internal link injection targeting the provided `product_url`
- X and Threads post generation
- Advisory backlink planning artifacts
- WordPress REST API draft/live publishing with Application Password auth
- WordPress presentation metadata for template/layout, category, tags, and optional featured image
- Explicit unattended publishing mode with auditable publish decisions
- Local review preview for generated jobs
- WordPress template/category/tag listing and IDs on publish
- SQLite/PostgreSQL persistence for jobs, artifacts, website analyses, suggestions, and structured job logs
- Placeholder publisher interfaces for Instagram and TikTok

WordPress publishing is manual-review first by default. Generated articles return `ready_for_review` with a local preview; drafts or live posts require explicit publish actions unless an automated publish policy is selected and enabled.

## Architecture

The API layer is intentionally thin:

```text
Trendplot Workspace -> Autopilot Service -> Website Intelligence / Planning / Generation / Publishing -> Repositories
```

FastAPI routes validate input and call the appropriate service layer. `app/autopilot/` owns the simple workspace experience, while `app/services/jobs.py` remains the advanced generation engine. Providers do not write directly to SQLite and do not import FastAPI objects.

Important modules:

- `app/article_schema.py`: canonical structured article schema and Markdown compatibility helpers.
- `app/content_generation.py`: OpenAI content generation provider.
- `app/prompts/`: YAML-backed prompt templates, rendering, registry, and validation.
- `app/providers/registry.py`: resolves replaceable providers.
- `app/website_analysis.py`: persisted website/competitor analysis and opportunity suggestions.
- `app/autopilot/`: Trendplot Workspace orchestration, status aggregation, policy state, and autopilot actions.
- `app/planning/`: content calendar generation and plan item lifecycle.
- `app/trends/`: generic trend signal normalization with null-provider fallback.
- `app/reassessment/`: periodic strategy review and calendar adjustment reports.
- `app/connectors/`: future Trendplot Connector contract for WordPress plugin integration.
- `app/performance/`: Search Console, rank, and traffic feedback provider boundary.
- `app/internal_links.py`: creates an internal link plan and injects contextual internal links before HTML conversion.
- `app/media/image_generation.py`: optional AI image prompt and image generation workflow, disabled by default.
- `app/product_data/`: future product data grounding interface for product facts, storage guidance, categories, and related products.
- `app/rendering/article_renderer.py`: renders canonical structured articles into WordPress-safe HTML and renderer logs.
- `app/rendering/schema_jsonld.py`: builds optional Article, FAQPage, VideoObject, BreadcrumbList, and Organization JSON-LD artifacts.
- `app/rendering/templates/`: reusable section rendering helpers.
- `app/quality_checks.py`: blocks WordPress publishing when the draft fails quality/safety checks.
- `app/review/redundancy_checker.py`: detects repeated headings, overlapping sections, repeated phrases, and cleanup candidates.
- `app/review/humanizer.py`: improves prose rhythm while preserving schema, links, facts, references, and required safety language.
- `app/review/sanity_checker.py`: blocks publishing when generated claims contradict brand/product rules.
- `app/rules/compliance_rules.py`: workspace/vertical-aware compliance rules and generic storage/handling fallback text.
- `app/services/publish_decisions.py`: chooses auditable WordPress metadata and publish status for manual or unattended flows.
- `app/wordpress.py`: WordPress publishing and category listing.
- `app/repositories.py`: database persistence layer.
- `app/services/jobs.py`: queue-safe orchestration boundary.

## Trendplot Connector

`Trendplot Connector` is the planned WordPress plugin compatibility layer. The backend now has a typed connector contract, signed connector client, plugin event ingestion, inventory sync, and a rollout path that keeps the current WordPress REST publisher as fallback.

Connector configuration:

```env
WORDPRESS_CONNECTOR_ENABLED=false
WORDPRESS_CONNECTOR_BASE_URL=https://example.com
WORDPRESS_CONNECTOR_SITE_ID=site_abc123
WORDPRESS_CONNECTOR_SECRET=
WORDPRESS_CONNECTOR_FALLBACK_TO_REST=true
```

Important backend endpoints:

- `GET /connectors/wordpress/contract`
- `GET /connectors/wordpress/health`
- `GET /connectors/wordpress/capabilities`
- `GET /connectors/wordpress/templates`
- `GET /connectors/wordpress/taxonomies/categories`
- `GET /connectors/wordpress/taxonomies/tags`
- `GET /connectors/wordpress/inventory/content`
- `GET /connectors/wordpress/inventory/products`
- `POST /connectors/wordpress/media/from-url`
- `POST /api/connectors/wordpress/events`
- `POST /autopilot/workspaces/{workspace_id}/connector-sync`

When `WORDPRESS_CONNECTOR_ENABLED=true`, publishing uses the connector first. If `WORDPRESS_CONNECTOR_FALLBACK_TO_REST=true` and the classic WordPress REST credentials are configured, Trendplot falls back to the existing REST publisher when the connector call fails. The connector owns Elementor/template metadata; the backend only sends normalized template intent and stores normalized connector responses.

## End-To-End Run Workflow

This is the full lifecycle from the dashboard action **Analyze website and suggest opportunities** to optional WordPress publishing. The default path is manual review: the app generates a local draft and does not publish anything to WordPress until a publish policy or publish endpoint explicitly allows it.

1. Start the app and load configuration.
   The service reads `.env`, creates the database connection, loads prompt templates, initializes provider adapters, and exposes the dashboard/API. The important safety defaults are `DEFAULT_PUBLISH_POLICY=manual_review`, `HUMAN_REVIEW_REQUIRED=true`, `ALLOW_LIVE_PUBLISH=false`, and `UNATTENDED_MODE_ENABLED=false`.

2. Open the dashboard.
   The dashboard at `http://localhost:8000` shows the website analysis form, generation form, API key status, recent jobs, local previews, artifact panels, WordPress category/template/tag helpers, and publishing controls.

3. Run **Analyze website and suggest opportunities**.
   The dashboard calls the persisted analysis flow, normally `POST /analysis-jobs`, with the main website URL, optional competitor URLs, a page limit, and optional vertical controls. `vertical_mode=auto` lets the Opportunity Engine detect the site profile; `generic`, `profile`, or `custom_context` can be used when you want a broader profile or user-provided context. The older stateless `POST /analyze-website` endpoint still exists, but the dashboard uses persisted analysis jobs so the results can be reviewed later.

4. Fetch website and competitor page signals.
   `app/website_analysis.py` fetches a small number of pages per site. It extracts lightweight SEO and content signals such as page URL, title, meta description, headings, commercial-looking links, and sample body text. The crawler is intentionally lightweight; it does not run a full SEO audit, keyword-volume lookup, SERP scrape, or WooCommerce product import.

5. Detect the vertical and build opportunity intelligence.
   `app/opportunities/verticals/` contains pluggable vertical profiles. The detector chooses the best profile in auto mode, or uses the requested override. The generic profile has no domain-specific assumptions; richer profiles such as peptides, shoes, fashion, supplements, and software provide optional entity hints, product-family maps, adjacent niches, compliance rules, and title guidance. The active profile is persisted as `vertical_detection`.

6. Optionally enrich with external research.
   External research is disabled by default with `ENABLE_EXTERNAL_RESEARCH=false`. When enabled, `app/intelligence/research_enrichment.py` generates research queries from the detected vertical, extracted products/entities, clusters, audiences, and competitor themes. It then calls configured provider interfaces for web, academic, YouTube, Reddit, and trend signals. Null providers are used by default, so no direct Google scraping or unapproved source access occurs. Results are summarized into directional themes, audience questions, entity relationships, caution notes, and possible article angles. Enriched opportunities carry `source_type`, `evidence_summary`, `evidence_items`, and `needs_verification`.

7. Ask AI for opportunity suggestions.
   The extracted website and competitor signals, detected vertical, vertical profile summary, entity expansions, audience examples, and safety rules are rendered into the website analysis prompt. The content provider returns suggested article opportunities: target keyword, article title, product name, product URL, and supporting rationale. The purpose is to use real site signals plus the active vertical profile to find semantic authority opportunities without turning the product into a hardcoded niche tool.

8. Persist the analysis.
   The app stores the analysis job, fetched page records, analysis prompt, raw AI response, summary, and suggestion rows in the database. The dashboard can list analyses, reopen one analysis, and show its pages, artifacts, and suggestions.

9. Review and edit suggestions.
   A human can approve, reject, or edit a suggestion before generation. This step is important because website analysis is advisory; it may choose a useful direction, but the product URL, product name, title, and keyword should still be checked.

10. Generate an article from an approved suggestion.
   `POST /analysis-suggestions/{id}/generate-article` passes the approved suggestion into the same job service used by `POST /generate-article`. Suggestions are generated with `publish_policy="manual_review"` so the analysis workflow never publishes by itself.

11. Create the article job.
   `app/services/jobs.py` validates the request, resolves the publish policy, creates a job row, stores request input, and writes a start log. If `unattended_mode=true` is sent while `UNATTENDED_MODE_ENABLED=false`, the request is rejected before generation.

12. Build and store the article generation prompt.
    The job service renders `app/prompts/templates/article_generation.yaml` with the title, target keyword, product name, product URL, and target length. The prompt requests canonical structured JSON, not final HTML. It asks for title, slug, excerpt, SEO fields, keywords, key takeaways, nested sections, FAQ, research context, limitations and safety, internal link suggestions, references to verify, rich components, related video metadata, social posts, and backlink plan.

13. Generate canonical structured article JSON.
    OpenAI returns structured JSON. The app normalizes the output through `app/article_schema.py` so reasonable model drift does not break the run. For example, legacy reference fields, string references, missing optional arrays, rich component aliases, and Markdown-derived sections are normalized into the canonical schema.

14. Run the initial quality check.
    `app/quality_checks.py` checks the normalized article before later polishing. It validates minimum word count, content sections, duplicate headings, empty sections, product URL/internal link presence, FAQ, research context, limitations/safety, RUO disclaimer for biomedical topics, forbidden medical claim phrases, placeholder images, malformed nested sections, repeated paragraphs, and other structural risks.

15. Repair fixable quality issues.
    If the initial quality check fails with fixable issues, the article repair service runs one or more configured repair passes. It asks the model to fix the specific errors/warnings while preserving safety language, schema, facts, and links. Each repair prompt, raw response, and summary is persisted.

16. Expand thin sections.
    The section expander targets shallow article sections or missing depth. It can expand section content and preserve the canonical schema. Its purpose is to avoid thin SEO pages and make each major section useful before the article is finalized.

17. Run redundancy review and cleanup.
    `app/review/redundancy_checker.py` detects duplicate headings, highly overlapping sections, repeated safety/RUO text, repeated handling/storage guidance, repeated CTA/product mentions, repeated phrases, and merge candidates. It stores `redundancy_review_results`, removes obvious duplicate paragraphs/sections where safe, and stores `redundancy_cleanup_summary`.

18. Humanize the article.
    `app/review/humanizer.py` runs a model-backed humanization pass plus deterministic cleanup. It reduces repetitive rhythm, obvious AI phrases, duplicated disclaimers, em dashes, overused transitions, and repeated sentence openers. It must preserve the schema, RUO disclaimer, facts, product URLs, internal links, references, FAQ, rich components, and compliance language.

19. Collect product grounding placeholders.
    The current provider is a no-op boundary in `app/product_data/`. It records a grounding plan for future WooCommerce/product data lookup without changing generated content yet. Future providers can ground product facts, storage guidance, categories, and related product links.

20. Store structured and Markdown artifacts.
    The final structured article is persisted as `structured_article_json` and `structured_article`. Markdown compatibility output is derived from the canonical schema and stored as `article_markdown`. Markdown is an artifact for review and compatibility; the structured schema remains the source of truth.

21. Build the internal link plan.
    `app/internal_links.py` uses the product URL, target keyword, product name, article suggestions, and optional research-use disclaimer URL. It injects natural contextual links, avoids repeating the same URL too often, avoids exact-match anchor stuffing, and does not invent related URLs. If no related links exist, it uses only the product URL and configured disclaimer page. The result is stored as `internal_links` and `internal_link_plan`.

22. Run optional AI image workflow.
    When `ENABLE_AI_IMAGE_GENERATION=false`, the workflow stores disabled media artifacts and makes no image API call. When enabled, the app first generates a safe editorial image prompt, blocks unsafe prompt concepts, and can generate a featured image. By default images require human review, are shown in the dashboard, and are not uploaded or set as featured media automatically.

23. Fetch enrichment assets.
    The enrichment service asks the configured image provider for a featured image candidate and the video provider for YouTube candidates. Placeholder images are not inserted by default. YouTube candidates are stored separately before AI evaluation.

24. Evaluate related YouTube video candidates.
    The YouTube evaluation prompt compares candidates against the article title, keyword, product/category, and outline. A video is selected only when it meets the configured relevance threshold. The article can render the title, channel, and relevance reason, but it does not treat the video as evidence for article facts unless transcript grounding is added later. The app stores `youtube_candidates`, `youtube_ai_evaluation`, `youtube_video`, and `youtube_relevance_summary`.

25. Render WordPress-safe HTML.
    `app/rendering/article_renderer.py` converts the canonical article into Elementor-friendly HTML with semantic `.bp-ai-*` classes. It supports H1 title, H2 sections, H3 subsections, key takeaways, table of contents, research metadata, definitions, study cards, comparison tables, callouts, cautions, conclusion/CTA flow, related topics, FAQ, references to verify, and optional related video. It does not inline CSS.

26. Run final quality checks.
    The final quality check runs against the enriched Markdown and rendered HTML. If it fails, the job saves artifacts and publishing remains blocked. Optional rich components are not required, but malformed or empty rich components can produce warnings.

27. Run semantic and deterministic sanity review.
    The semantic sanity reviewer asks AI to review the article against the brand/product rules, then deterministic sanity checks remain authoritative. The sanity layer blocks or rewrites unsafe claims such as human therapeutic benefit, dosing, patient guidance, unsupported storage/reconstitution instructions, or unverified references presented as confirmed facts. It must not remove the required RUO disclaimer.

28. Re-render after sanity changes.
    If the sanity review rewrites the article, the job updates the structured article, Markdown artifact, rendered HTML, renderer logs, and final quality artifacts so the local preview reflects the safe version.

29. Create SEO, social, research, media, metrics, and schema artifacts.
    The job stores SEO metadata, X/Threads posts, references to verify, advisory backlink plan, study cards, research metadata panel, rich component JSON, and optional `schema_jsonld` when `ENABLE_JSONLD_SCHEMA=true`. JSON-LD can include Article, FAQPage, VideoObject, BreadcrumbList, and Organization data where enough information exists.

30. Resolve WordPress presentation metadata.
    The publish decision service combines user inputs, configured defaults, AI/default choices, and safe fallbacks for template, category, tags, featured image, and publish status. It stores auditable artifacts such as `publish_decision_report`, `wordpress_template_selection`, `wordpress_category_selection`, `wordpress_tag_suggestions`, `wordpress_presentation_metadata`, and `final_publish_metadata`.

31. Persist run metrics.
    The job stores `job_run_metrics`, `stage_timing_summary`, and `model_cost_summary`. These summarize total runtime, per-stage runtime, slowest stages, model calls, token usage, estimated cost, repair passes, expansion passes, final word count, final quality status, and final sanity status.

32. Decide final job status.
    With `manual_review`, the job returns `ready_for_review` and no WordPress post is created. With `auto_draft`, a WordPress draft can be created only after quality and sanity pass. With `auto_live`, all live-publish flags must be enabled and gates must pass. If any blocking quality or sanity issue remains, the status is `failed_quality` or `failed_sanity`.

33. Review the local preview.
    `GET /jobs/{job_id}/preview` shows the generated article locally. The dashboard also shows artifacts, including redundancy review, internal link plan, study cards, research metadata, JSON-LD preview, renderer logs, quality results, sanity results, and publish decisions.

34. Publish a WordPress draft after review.
    `POST /jobs/{job_id}/publish-draft` publishes a draft only when the job is eligible and gates have passed. The WordPress client resolves categories, resolves or creates tags if allowed, optionally uploads a featured image, applies template metadata where supported, and stores the exact publish payload and WordPress response.

35. Publish live only with explicit safeguards.
    `POST /jobs/{job_id}/publish-live` requires `ALLOW_LIVE_PUBLISH=true` and `"confirm_live_publish": true`. Automatic live publishing also requires `UNATTENDED_MODE_ENABLED=true`, `UNATTENDED_ALLOW_AUTO_LIVE=true`, `ALLOW_AUTO_LIVE=true`, `ALLOW_LIVE_PUBLISH=true`, and passed quality/sanity gates. These checks are code-enforced and are not bypassed by prompts.

36. Keep an audit trail.
    Every major step stores logs and artifacts in the database: prompts, raw model responses, model usage, repair summaries, expansion summaries, review results, rendered HTML, publish metadata, WordPress payloads, and final status. This makes a run explainable for both humans and AI agents inspecting the job later.

## Artifacts

The service stores generated and debug artifacts in the configured database:

- `article_markdown`
- `article_html`
- `rendered_html`
- `seo_metadata`
- `meta_title`
- `meta_description`
- `internal_links`
- `featured_image`
- `youtube_video`
- `x_post`
- `threads_post`
- `wordpress_post`
- `wordpress_publish_response`
- `wordpress_presentation_metadata`
- `wordpress_template_selection`
- `wordpress_category_selection`
- `wordpress_tag_suggestions`
- `wordpress_tag_resolution_result`
- `wordpress_featured_image_result`
- `wordpress_publish_payload`
- `publish_decision_report`
- `ai_category_decision`
- `ai_tag_decision`
- `ai_template_decision`
- `unattended_policy_result`
- `final_publish_metadata`
- `publish_request`
- `category_selection`
- `structured_article_json`
- `structured_article`
- `quality_check_results`
- `quality_check`
- `backlink_plan`
- `references_to_verify`
- `suggested_external_references`
- `social_posts`
- `renderer_logs`
- `prompt`
- `raw_llm_response`
- `humanization_prompt`
- `humanization_raw_response`
- `humanization_summary`
- `pre_humanized_article_json`
- `post_humanized_article_json`
- `sanity_check_results`
- `sanity_rewrite_summary`
- `redundancy_review_results`
- `redundancy_cleanup_summary`
- `internal_link_plan`
- `study_cards`
- `research_metadata_panel`
- `rich_components_json`
- `schema_jsonld`
- `youtube_relevance_summary`
- `job_run_metrics`
- `stage_timing_summary`
- `model_cost_summary`
- `image_prompt`
- `image_generation_result`
- `image_alt_text`
- `image_caption`
- `image_safety_notes`
- `image_review_decision`
- `product_data_grounding_plan`

Artifacts also track provider, model, token usage when available, and estimated cost when possible.

## Vertical Profiles

The Opportunity Engine is built as a generic opportunity engine plus optional vertical intelligence profiles. Generic mode avoids domain-specific assumptions and extracts repeated terms, product/category names, capitalized entities, headings, questions, navigation themes, competitor-only terms, and product/category relationships.

Profiles live in `app/opportunities/verticals/`:

- `generic.py`: vertical-neutral defaults.
- `peptides.py`: research peptide intelligence with RUO-safe compliance rules.
- `shoes.py`: footwear, fit, material, care, and styling signals.
- `fashion.py`: fashion, bags, materials, styling, and trend signals.
- `supplements.py`: ingredient, label transparency, wellness, and testing signals.
- `software.py`: SaaS, workflow, integration, security, onboarding, and analytics signals.

`OPPORTUNITY_VERTICAL=auto` scores registered profiles and uses the highest-confidence match. If confidence is low, the engine falls back to `generic`. The dashboard also exposes a **Site vertical** dropdown so a user can override detection with `generic`, `peptides`, `shoes`, `fashion`, `supplements`, or `software`.

Each profile can provide stopword additions, boilerplate hints, product path hints, educational hints, known entities, mechanism/concept hints, product family maps, entity expansion maps, adjacent niches, audience examples, compliance rules, opportunity type weights, and title guidance. Detection and the selected profile are persisted as `vertical_detection`, and the dashboard shows the detected vertical and confidence after analysis.

To add a new vertical:

1. Create `app/opportunities/verticals/<name>.py`.
2. Define a `VerticalProfile` with lightweight deterministic hints and safety rules.
3. Register it in `app/opportunities/verticals/registry.py`.
4. Add the ID to the API/UI allowed vertical choices if it should be user-selectable.
5. Add smoke coverage to confirm the profile detects correctly and does not leak entities into unrelated verticals.

## External Research Enrichment

External research enrichment is an optional phase after crawl analysis, vertical detection, entity extraction, audience inference, and clustering. It is controlled by:

```env
ENABLE_EXTERNAL_RESEARCH=false
EXTERNAL_RESEARCH_MAX_QUERIES=20
EXTERNAL_RESEARCH_MAX_RESULTS_PER_QUERY=5
ENABLE_ACADEMIC_RESEARCH=false
ENABLE_REDDIT_RESEARCH=false
ENABLE_TREND_RESEARCH=false
```

The enrichment layer lives in `app/intelligence/research_enrichment.py`. It generates search queries, calls provider interfaces, summarizes returned signals, and feeds directional topics into opportunity generation. Provider interfaces live in `app/intelligence/providers.py`:

- `WebSearchProvider`
- `AcademicSearchProvider`
- `YouTubeSearchProvider`
- `RedditSignalProvider`
- `TrendSignalProvider`

All providers are null/disabled by default except YouTube can adapt the existing configured YouTube provider when external research is enabled. The app does not scrape Google directly. Academic, Reddit, and trends are placeholders until approved APIs are connected.

Enriched opportunities include evidence labels:

- `source_type`: `site`, `competitor`, `web`, `academic`, `youtube`, `reddit`, `trend`, or `inferred`
- `evidence_summary`: a short description of the directional signal
- `evidence_items`: provider result snippets/URLs/queries where available
- `needs_verification`: `true` unless a provider explicitly marks the result verified

External findings do not bypass quality gates, sanity gates, manual review, RUO rules, or WordPress publishing safeguards. They are treated as opportunity signals, not verified article facts.

## Configuration

Copy `.env.example` to `.env` and set:

```env
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_LIGHT_MODEL=gpt-5-nano
OPENAI_STANDARD_MODEL=gpt-5-mini
OPENAI_PREMIUM_MODEL=gpt-5
OPENAI_PROVIDER_NAME=openai
OPENAI_REQUEST_TIMEOUT_SECONDS=180
OPENAI_ENABLE_REASONING=false
OPENAI_REASONING_EFFORT=medium
WORDPRESS_BASE_URL=https://example.com
WORDPRESS_USERNAME=wordpress-user
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WORDPRESS_DEFAULT_TEMPLATE=elementor_full_width
WORDPRESS_DEFAULT_CATEGORY_ID=
WORDPRESS_DEFAULT_CATEGORY_SLUG=
WORDPRESS_DEFAULT_TAGS=
WORDPRESS_AUTO_CREATE_TAGS=true
WORDPRESS_MAX_TAGS=8
WORDPRESS_ALLOW_ELEMENTOR_CANVAS=false
WORDPRESS_REQUIRE_FEATURED_IMAGE=false
WORDPRESS_UPLOAD_FEATURED_IMAGE=false
WORDPRESS_FAIL_ON_TEMPLATE_ERROR=false
YOUTUBE_API_KEY=your-youtube-data-api-key
DATABASE_URL=sqlite:///./data/seo_content_worker.db
# Docker/PostgreSQL example:
# DATABASE_URL=postgresql+psycopg://seo_user:seo_password@postgres:5432/seo_worker
DEFAULT_PUBLISH_POLICY=manual_review
PUBLISH_POLICY=manual_review
ALLOW_LIVE_PUBLISH=false
ALLOW_AUTO_LIVE=false
UNATTENDED_MODE_ENABLED=false
UNATTENDED_DEFAULT_PUBLISH_POLICY=auto_draft
UNATTENDED_ALLOW_AUTO_LIVE=false
UNATTENDED_REQUIRE_QUALITY_PASS=true
UNATTENDED_REQUIRE_SANITY_PASS=true
HUMAN_REVIEW_REQUIRED=true
PROMPT_TEMPLATE_DIR=app/prompts/templates
ALLOW_PROMPT_FALLBACK=false
PROMPT_STRICT_MODE=true
ENABLE_JSONLD_SCHEMA=true
OPPORTUNITY_VERTICAL=auto
ENABLE_EXTERNAL_RESEARCH=false
EXTERNAL_RESEARCH_MAX_QUERIES=20
EXTERNAL_RESEARCH_MAX_RESULTS_PER_QUERY=5
ENABLE_ACADEMIC_RESEARCH=false
ENABLE_REDDIT_RESEARCH=false
ENABLE_TREND_RESEARCH=false
NICHE_INTELLIGENCE_ENABLED=true
OPPORTUNITY_INTELLIGENCE_ENABLED=true
DEMAND_INTELLIGENCE_ENABLED=true
DEMAND_PROVIDER_SEARCH_CONSOLE_ENABLED=false
SEARCH_CONSOLE_SITE_URL=
SEARCH_CONSOLE_CREDENTIALS_JSON_PATH=
DEMAND_LOOKBACK_DAYS=28
DEMAND_MAX_ROWS=1000
TREND_INTELLIGENCE_ENABLED=true
PUBLISHING_MEMORY_ENABLED=true
ENABLE_AI_IMAGE_GENERATION=false
AI_IMAGE_MODEL=gpt-image-1
AI_IMAGE_STYLE=clean editorial scientific
AI_IMAGE_VARIANTS_PER_PLACEMENT=1
AI_IMAGE_MAX_IMAGES=3
AI_IMAGE_PLAN_INLINE_IMAGES=true
AI_IMAGE_MAX_INLINE_IMAGE_PLACEMENTS=2
AI_IMAGE_ENABLE_VERTICAL_RULES=true
AI_IMAGE_GENERATE_FEATURED=true
AI_IMAGE_OUTPUT_DIR=data/generated-images
# Optional vertical-specific safety settings:
# RESEARCH_USE_DISCLAIMER_URL=
# BIOMEDICAL_RUO_DISCLAIMER=For research use only. Not intended for human consumption, therapeutic, or diagnostic use.
LOG_LEVEL=INFO
```

In WordPress, create an Application Password from the user profile page and use it as `WORDPRESS_APP_PASSWORD`.

## Niche And Trend Intelligence

Trendplot stores a persistent workspace niche profile so repeated analysis runs can reuse stable business context instead of rediscovering the same niche facts from scratch. The profile captures the primary niche, secondary niches, known entities, products, categories, audiences, terminology, confidence, and source counts.

Helpful endpoints:

```text
GET /autopilot/workspaces/{workspace_id}/niche-profile
POST /autopilot/workspaces/{workspace_id}/niche-profile/refresh
```

`NICHE_INTELLIGENCE_ENABLED=true` enables the feature. Trend discovery uses the profile as additional context for query generation, and the workspace UI shows the persisted profile beside Site Understanding.

## Opportunity Intelligence

Opportunity Intelligence turns collected signals into editorial decisions. It reuses Website Intelligence, Niche Intelligence, competitor snapshots, trend signals, existing opportunities, Publishing Memory, and published content to recommend a smaller set of actions:

- `create`
- `refresh`
- `expand`
- `merge`
- `monitor`
- `ignore`

Helpful endpoints:

```text
GET /autopilot/workspaces/{workspace_id}/opportunity-intelligence
POST /autopilot/workspaces/{workspace_id}/opportunity-intelligence/refresh
```

The workspace UI groups recommendations into Recommended Now, Refresh Existing Content, Monitor, and Ignore. `OPPORTUNITY_INTELLIGENCE_ENABLED=true` enables automatic refresh during analysis, trend refresh, and coverage refresh.

## Demand Observations

Demand Observations store source-agnostic search demand evidence. The first real provider is Google Search Console, using service account credentials and the Search Analytics API dimensions `query`, `page`, `country`, and `device`.

Helpful endpoints:

```text
GET /developer/demand/providers
POST /developer/demand/workspaces/{workspace_id}/fetch
GET /developer/demand/workspaces/{workspace_id}/observations
GET /developer/demand/workspaces/{workspace_id}/runs
GET /autopilot/workspaces/{workspace_id}/demand-insights
```

Search Console is optional. When it is disabled or incomplete, Trendplot records a clean `not_configured` provider/run status and existing analysis, planning, generation, and publishing flows continue without Search Console data. When configured, observations feed Opportunity Intelligence as high-weight external demand evidence.

## WordPress Presentation Metadata

The generator controls article content. The WordPress/Elementor template controls layout, and reusable site CSS controls design. Generated posts should not rely on inline article CSS for long-term styling.

Publishing supports optional presentation metadata:

- `wordpress_template`: WordPress/Elementor layout key. The recommended default for SEO blog posts is Elementor Full Width (`elementor_header_footer`). Elementor Canvas is usually not recommended because it removes the site header/footer.
- `wordpress_category_id`, `wordpress_category_slug`, `wordpress_category_name`: category selection. IDs are preferred; slug/name are fallback inputs.
- `wordpress_tags`: editable tag names. The publisher resolves or creates up to `WORDPRESS_MAX_TAGS` tags. Avoid exact-match stuffing.
- `featured_image_id`, `featured_image_url`, `featured_image_alt`: optional featured image metadata. Placeholder images are not used. If only a URL is provided, upload is skipped unless `WORDPRESS_UPLOAD_FEATURED_IMAGE=true`.

Helpful endpoints:

```text
GET /wordpress/templates
GET /wordpress/categories
GET /wordpress/tags
```

The publish payload may include `categories`, `tags`, `featured_media`, and template metadata. If template assignment is not supported by the site, the app stores a warning in the WordPress response but does not fail publishing unless `WORDPRESS_FAIL_ON_TEMPLATE_ERROR=true`.

Generated article HTML uses reusable classes for site-level CSS. Keep design in Elementor/theme CSS rather than inline post content. In addition to the base `.bp-ai-*` classes, richer article components may use:

- `.bp-ai-callout`
- `.bp-ai-study-card`
- `.bp-ai-definition`
- `.bp-ai-caution`
- `.bp-ai-research-metadata`
- `.bp-ai-comparison-table`
- `.bp-ai-image`
- `.bp-ai-featured-image`
- `.bp-ai-inline-image`
- `.bp-ai-image-caption`

## Optional AI Images

AI image generation is disabled by default. The article pipeline still creates an `image_placement_plan` so reviewers can see whether a featured image or inline visuals would improve the article. When `ENABLE_AI_IMAGE_GENERATION=true`, safe generated images are inserted into the rendered article automatically. Review happens at the whole-document level before publishing, not as a separate per-image approval step.

Generic image planning supports featured editorial images, product-context visuals, lifestyle images, comparison visuals, process/workflow visuals, concept maps, checklist graphics, diagrams, infographic-style visuals, trend visuals, and brand-safe abstract visuals. Generic avoid rules block misleading imagery, unsupported product claims, fake logos/brands/certifications, deceptive before/after imagery, unsafe product use, unsupported outcome implication, and copyrighted or trademark-infringing style requests.

Vertical profiles can add stricter visual rules. For example, the peptide/research profile adds lab-neutral and mechanism visuals while avoiding syringes, injections, clinical treatment scenes, and human-use implication. Shoes, fashion/bags, software, and supplements each define their own allowed image types and avoid rules in `app/opportunities/verticals/`.

`AI_IMAGE_MAX_IMAGES=3` caps the total number of generated images for an article. `AI_IMAGE_PLAN_INLINE_IMAGES=true` lets the planner recommend inline placements, and `AI_IMAGE_MAX_INLINE_IMAGE_PLACEMENTS=2` caps those inline recommendations. `AI_IMAGE_VARIANTS_PER_PLACEMENT=1` controls how many image variants are generated for each planned placement. Generated images are not uploaded to WordPress unless publishing occurs and `WORDPRESS_UPLOAD_FEATURED_IMAGE=true`.

## Unattended Publishing

Unattended publishing is disabled by default. A request with `unattended_mode=true` is rejected unless `UNATTENDED_MODE_ENABLED=true`.

When enabled, the publish decision service selects presentation metadata using this priority:

```text
User-provided value -> configured default -> AI suggestion where allowed -> safe fallback
```

For categories, AI may choose only from existing WordPress categories. It never creates categories. For tags, AI may suggest 3-8 tags, and the WordPress publisher resolves or creates tags only when `WORDPRESS_AUTO_CREATE_TAGS=true`. Elementor Canvas is blocked unless `WORDPRESS_ALLOW_ELEMENTOR_CANVAS=true`.

`auto_draft` can publish a draft only after quality and sanity pass. `auto_live` publishes live only when all live-publish flags are enabled:

```text
UNATTENDED_MODE_ENABLED=true
UNATTENDED_ALLOW_AUTO_LIVE=true
ALLOW_AUTO_LIVE=true
ALLOW_LIVE_PUBLISH=true
```

Decision artifacts are stored for auditability: `publish_decision_report`, `ai_category_decision`, `ai_tag_decision`, `ai_template_decision`, `unattended_policy_result`, and `final_publish_metadata`.

## Database And Migrations

SQLite remains available for lightweight local development:

```env
DATABASE_URL=sqlite:///./data/seo_content_worker.db
```

After installing dependencies, run migrations before starting the app directly:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Docker Compose defaults the app to PostgreSQL:

```bash
docker compose up -d postgres seo-content-worker
docker compose exec seo-content-worker alembic upgrade head
```

Existing SQLite data is not automatically migrated to PostgreSQL. Export/import can be handled later if existing local data needs to move.

## Run With Docker

```bash
docker compose up --build
docker compose exec seo-content-worker alembic upgrade head
```

## Run From VS Code Or Cursor

Press `F5` and select `Run seo-content-worker`. This starts Uvicorn with `.env` loaded and reload enabled.

If your selected Python environment does not have dependencies installed yet, run the `Install Python dependencies` task once from the command palette.

Open the local dashboard at:

```text
http://localhost:8000
```

The dashboard includes website analysis, suggestion cards, a guided generation form, API key checks, sample keyword ideas, links to health/API docs, recent jobs, and job artifact details.

API key checks are available in the dashboard and at:

```text
GET /config/api-keys
```

The check only reports whether the running app loaded missing, placeholder, or configured-looking values. It does not expose full secrets or call external APIs.

## Model Routing

Task routing uses `OPENAI_LIGHT_MODEL`, `OPENAI_STANDARD_MODEL`, and `OPENAI_PREMIUM_MODEL`. `OPENAI_MODEL` is kept as a legacy setting and does not override task-specific routing.

Default tier intent:

- Light: simple extraction, category lookup, cleanup, and classification.
- Standard: website analysis, YouTube evaluation, SEO metadata, social posts, backlink planning, and FAQ generation.
- Premium: article generation, article repair, section expansion, humanization, quality review, sanity review, and biomedical/research review.

Validate routing with:

```bash
python -m app.providers.validate_models
```

The command prints the selected model, task type, reasoning support, reasoning enabled yes/no, reasoning effort when used, reasoning decision source, token parameter compatibility, and whether estimated cost can be calculated from configured tier rates. Token usage is stored after live OpenAI calls when the API returns usage.

Reasoning mode is optional and disabled by default:

```env
OPENAI_ENABLE_REASONING=false
OPENAI_REASONING_EFFORT=medium
OPENAI_LIGHT_REASONING_ENABLED=false
OPENAI_STANDARD_REASONING_ENABLED=false
OPENAI_PREMIUM_REASONING_ENABLED=true
OPENAI_LIGHT_REASONING_EFFORT=low
OPENAI_STANDARD_REASONING_EFFORT=low
OPENAI_PREMIUM_REASONING_EFFORT=medium
OPENAI_REASONING_ARTICLE_GENERATION=medium
OPENAI_REASONING_SECTION_EXPANSION=high
OPENAI_REASONING_SANITY_REVIEW=high
OPENAI_REASONING_BIOMEDICAL_REVIEW=high
OPENAI_REASONING_HUMANIZATION=medium
OPENAI_REASONING_WEBSITE_ANALYSIS=low
```

Reasoning policy resolution is task override, then tier config, then global config, then disabled. Reasoning parameters are only sent when the resolved policy enables reasoning and the selected model appears to support reasoning, such as `gpt-5`, `gpt-5-mini`, or `gpt-5-nano`. Unsupported or unknown model configs emit warnings in the validation command, and reasoning is not sent for those models. Do not enable high reasoning globally by default; keep it task-specific and deliberate.

Reasoning does not bypass quality checks, sanity checks, RUO enforcement, or draft/live publishing rules.

## Prompt Templates

AI prompts live in editable YAML files under `app/prompts/templates`. Each template includes an id, version, model task, required variables, template body, output contract, and safety rules.

Validate all prompt templates with:

```bash
python -m app.prompts.validate
```

Prompt placeholders use simple `{{ variable_name }}` syntax. Missing variables fail clearly in strict mode, and the renderer does not use `eval`.

Current templates include article generation, repair, section expansion, humanization, website analysis, YouTube evaluation, backlink planning, social posts, SEO metadata, and optional sanity review.

Editing prompts can change AI behavior, but it cannot bypass code-enforced gates. Quality checks, sanity checks, RUO disclaimer enforcement, forbidden medical phrase checks, manual review defaults, and draft/live publishing guards remain enforced in Python after prompt rendering.

Prompt artifacts store metadata such as `prompt_id`, `prompt_version`, `model_task`, rendered prompt text, selected model, usage, and raw response where available. The dashboard shows prompt id/version/task and keeps full prompt text inside expandable sections.

## Analyze A Website

Use the dashboard at `http://localhost:8000` to enter your website and optional competitor URLs. The app fetches lightweight page signals, including titles, meta descriptions, headings, commercial-looking links, and text samples. OpenAI then suggests target keywords, article titles, product names, and product URLs.

Saved analysis workflow:

- `POST /analysis-jobs` creates a persisted analysis run and stores extracted pages/suggestions.
- `GET /analysis-jobs` lists recent analyses.
- `GET /analysis-jobs/{id}` returns saved pages, analysis artifacts, and suggestions.
- `PATCH /analysis-suggestions/{id}` updates suggestion fields or status.
- `POST /analysis-suggestions/{id}/generate-article` generates a review-ready article from an approved suggestion.

Suggestions can be edited, approved, rejected, or used to create an article. Website analysis never publishes content by itself. Article generation goes through the same manual-review job service.

API example:

```bash
curl -X POST http://localhost:8000/analysis-jobs \
  -H "Content-Type: application/json" \
  -d '{
    "website_url": "https://example.com",
    "competitor_urls": ["https://competitor.com"],
    "max_pages_per_site": 3
  }'
```

The stateless `POST /analyze-website` compatibility endpoint still exists, but the dashboard uses the persisted `POST /analysis-jobs` flow. This MVP does not use keyword-volume data, SERP data, or WooCommerce yet. Suggestions are based on fetched page signals and OpenAI reasoning.

On Windows PowerShell, deploy the latest local build with:

```powershell
.\deploy-local.ps1
```

Useful options:

```powershell
.\deploy-local.ps1 -NoCache
.\deploy-local.ps1 -ForceRecreate
.\deploy-local.ps1 -SkipHealthCheck
.\deploy-local.ps1 -Reset
```

The deployment script builds the app image, starts PostgreSQL, waits for the database healthcheck, starts the app, runs `alembic upgrade head` inside the app container, and prints the local dashboard URL.

Health check:

```bash
curl http://localhost:8000/health
```

## Generate An Article

```bash
curl -X POST http://localhost:8000/generate-article \
  -H "Content-Type: application/json" \
  -d '{
    "title": "How to Choose the Best Running Shoes",
    "target_keyword": "best running shoes",
    "product_name": "Acme Runner Pro",
    "product_url": "https://example.com/products/acme-runner-pro",
    "publish_policy": "manual_review",
    "category_id": 12
  }'
```

The response includes the job id, quality check result, publish policy, WordPress details when publishing occurs, video metadata, backlink plan, suggested references, generated X/Threads copy, structured article JSON, and rendered HTML. With the default `manual_review` policy, no WordPress post is created.

Preview and publish endpoints:

```text
GET  /jobs/{job_id}/preview
POST /jobs/{job_id}/publish-draft
POST /jobs/{job_id}/publish-live
GET  /wordpress/categories
```

Live publishing requires `ALLOW_LIVE_PUBLISH=true` and a request body containing `"confirm_live_publish": true`. Automatic live publishing additionally requires `ALLOW_AUTO_LIVE=true` and `publish_policy: "auto_live"`.

Supported publish policies:

- `manual_review`: generate and store locally, do not publish.
- `draft_after_review`: generate for review, then use the draft publish endpoint.
- `live_after_review`: generate for review, then use the live publish endpoint.
- `auto_draft`: publish a WordPress draft automatically after quality passes.
- `auto_live`: publish live automatically only when `ALLOW_AUTO_LIVE=true`.

Article generation now asks OpenAI for canonical structured JSON, including title, slug, excerpt, SEO metadata, primary/secondary keywords, key takeaways, table of contents, structured sections, FAQ, research context, limitations and safety notes, internal link suggestions, reference suggestions, social posts, related video metadata, and an advisory backlink plan. Markdown remains canonical only inside section content and derived compatibility artifacts.

Before publishing, the quality gate checks minimum word count, empty sections, duplicate headings, section depth, product link presence, RUO disclaimer presence for peptide/biomedical topics, forbidden medical claim phrases, FAQ presence, placeholder image usage, empty Related Video sections, and rendered HTML structure. If checks fail, artifacts are saved and the job returns `failed_quality`; publish endpoints reject the job.

After quality review, the domain sanity gate checks the canonical article and rendered HTML against workspace compliance rules. It blocks unsupported storage temperatures, reconstitution guidance, aliquot/freezing instructions, stability/degradation claims, human dosing, patient/clinical-use guidance, and therapeutic claims. Unsupported handling/storage text is deterministically replaced with:

```text
Storage and handling requirements can vary by formulation, batch, and supplier documentation. Researchers should refer to the product label, Certificate of Analysis, and any supplied handling instructions.
```

The rewrite is stored in `sanity_rewrite_summary`, the final report is stored in `sanity_check_results`, and publishing remains blocked with `failed_sanity` if blocking errors remain.

After repair and section expansion, a humanization pass performs deterministic cleanup and a model-backed style pass while preserving the canonical schema, RUO disclaimer, product links, FAQ, references, and compliance language. The final rendered HTML is created only after this cleanup and quality review.

WordPress output is rendered through `app/rendering/article_renderer.py` using semantic classes such as `bp-ai-article`, `bp-ai-section`, `bp-ai-key-takeaways`, `bp-ai-faq`, `bp-ai-cta`, and `bp-ai-video`. This is Elementor-friendly HTML, not Elementor API integration.

Backlink planning is advisory only. The worker does not create automatic backlinks, hidden links, outbound link networks, or link exchanges. Any backlink action requires human approval.

YouTube enrichment uses the YouTube Data API to fetch multiple candidates, then asks the content generation provider to evaluate relevance against the article title, target keyword, product/category, and article outline. A video is embedded only when the AI relevance score is at least `70`. Candidate metadata and the AI evaluation are stored as `youtube_candidates` and `youtube_ai_evaluation` artifacts. This is enrichment only, not scientific source grounding, and the video must not be treated as evidence for article claims.

## Future Boundaries

The architecture leaves room for:

- Real image providers.
- Source research and article grounding in `app/research/`.
- Cron-based content plans and scheduled publishing.
- Queue workers, retry backoff, concurrency limits, request throttling, and failed job replay.
- Instagram and TikTok publisher implementations.
