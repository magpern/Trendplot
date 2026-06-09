# Competitor Discovery Verification

Verification date: 2026-06-02

## Part 1 — Current Implementation (before merge fix)

### 1. Does competitor discovery execute during first-run analysis?

**Yes, conditionally.** `AutopilotService.analyze_workspace()` always attempted competitor discovery when workspace settings had no competitor URLs. On first-run, discovery ran but typically found no candidates because it only consulted prior site understanding and competitor snapshots (both empty on first run).

### 2. Does it execute when user-provided competitors exist?

**No (prior behavior).** When workspace settings already contained competitor URLs, discovery was skipped entirely and marked `skipped` with `source=provided`. Automatic discovery did not run in parallel with provided URLs.

### 3. Is `competitor_discovery` populated in diagnostics?

**Yes.** The analyze flow summary and step details include a `competitor_discovery` block from `analysis_payload["competitor_discovery"]`, populated by `AutopilotService.analyze_workspace()` and surfaced through `extract_flow_summary()` and `summarize_steps_from_payloads()`.

### 4. Are discovered competitors passed into competitor analysis?

**Yes, when discovery succeeded and no provided competitors existed.** Discovered URLs were written to workspace settings and passed to `WebsiteAnalysisService.create_analysis_job()` as `competitor_urls`. When provided competitors existed, those were used and discovery results were not merged.

### 5. Is the feature implemented or only documented?

**Implemented, but incomplete relative to product spec.** Core discovery, filtering, diagnostics, and UI surfacing existed. Merge behavior (provided + discovered), total cap, first-run web-search fallback, and unified diagnostics counts were missing.

## Part 2 — Merge behavior (implemented)

After this change:

```text
final_competitors =
    normalized provided competitors
    + normalized discovered competitors
    - duplicates (by registrable domain)
    - same-domain
    - rejected domains (social, directories, marketplaces)
```

Ordering: provided first, discovered second. Cap: `COMPETITOR_TOTAL_MAX_COMPETITORS`.

Discovery runs even when provided competitors exist (unless `COMPETITOR_DISCOVERY_ENABLED=false`).

## Diagnostics contract

```json
{
  "competitor_discovery": {
    "enabled": true,
    "source": "provided|discovered|provided+discovered|none",
    "provided_count": 2,
    "discovered_count": 3,
    "merged_count": 5,
    "selected_count": 5,
    "competitors": []
  }
}
```

## First-run limitation

Discovery executes before the current-run website analysis completes, so first-run workspaces rely on:

- operator-provided competitors
- workspace name / user context (niche hints)
- prior understanding or snapshots (empty on first run)
- optional web search when `ENABLE_EXTERNAL_RESEARCH=true`, `MARKET_PROVIDER_WEB_ENABLED=true`, and a configured web search provider exist

Without a safe discovery provider and with no history, discovery returns `source=none` with a warning and does not fail the run.

## Test coverage

See `tests/test_competitor_discovery.py` and `tests/test_analyze_website_flow.py`.

## Conclusion

A) Competitor discovery merge implemented
