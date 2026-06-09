# Phase 2A Logging Audit

Date: 2026-06-01

Scope audited:
- `app/entity_relevance/`
- `app/opportunity_intelligence/`
- `app/autopilot/`
- `app/logging_config.py`
- approval event metadata + OI summary output path

## Findings Matrix

| Item | Status | Notes |
|---|---|---|
| `entity_relevance.enabled` | present | Included in Phase 2A metrics payload. |
| `entities_requested` | present | Included in metrics payload. |
| `entities_scored` | present | Included in metrics payload. |
| `model_calls` | present | Included in metrics payload. |
| `cache_hits` | present | Included in metrics payload. |
| `cache_misses` | present | Included in metrics payload. |
| `cache_hit_rate` | missing | Added as computed aggregate (`hits / (hits + misses)`). |
| `filtered_by_relevance` | present | Included in metrics payload. |
| `down_ranked_by_relevance` | present | Included in metrics payload. |
| `fallback_count` | present but incomplete | Count existed; reason was not surfaced. Added `fail_open_reason`. |
| `latency_seconds` | missing | Added as aggregate model-call latency across batches. |
| `cost_usd` | missing | Added as token-based estimate for `gpt-4o-mini`; `0.0` for other models. |
| `batch_size` | missing | Added from config (`ENTITY_RELEVANCE_BATCH_SIZE`). |
| model name | present | Included as `model`. |
| timeout events | present but incomplete | Fail-open existed; explicit timeout warning event added. |
| malformed response events | present but incomplete | Fail-open existed; explicit malformed-response warning event added. |
| fail-open reason | missing | Added `fail_open_reason` metric (comma-separated reason set). |
| `low_content_warning` | present | Surfaced in `analyze_workspace` response when conditions are met. |
| `sparse_site_warning` | present | Added to recommendation metadata in OI service when sparse-site gate is active. |

## What Was Already Sufficient

- Core Phase 2A counters and enablement state were already emitted.
- OI summary wiring to response + approval-event metadata was already in place.
- Fail-open behavior was already preserved and safe.
- Logging formatter already supported structured JSON with `extra` fields.

## What Was Missing

- Missing production-facing aggregates: `cache_hit_rate`, `latency_seconds`, `cost_usd`, `batch_size`.
- No surfaced fail-open reason despite fallback counts.
- Timeout/malformed cases were not explicitly distinguished in warning logs.

## What Was Implemented

- Added metrics in `EntityRelevanceService`:
  - `cache_hit_rate`
  - `latency_seconds`
  - `cost_usd`
  - `batch_size`
  - `fail_open_reason`
- Added structured INFO summary log:
  - message: `entity_relevance_summary`
  - payload in `extra.entity_relevance`
- Added explicit WARNING events:
  - `entity_relevance_timeout`
  - `entity_relevance_malformed_response`
  - `entity_relevance_batch_failed` (generic)
- Kept prompt/body/entity-list logging out of INFO logs.
- Preserved fail-open contract and non-crashing behavior.

## Tests Added/Updated

- `tests/test_entity_relevance.py`
  - verifies required metrics keys are present for Phase 2A output
  - verifies fallback reason is surfaced on malformed scorer failure
  - verifies disabled flag yields no scoring activity (`model_calls=0`, `entities_scored=0`)
  - verifies INFO logs do not include sensitive prompt payload / entity labels
- Existing low-content/sparse-site warning coverage remains in:
  - `tests/test_entity_quality_filters.py`

## Test Results

- Command: `PYTHONPATH=. pytest tests/test_entity_relevance.py tests/test_entity_quality_filters.py -q`
- Result: `215 passed in 1.99s`

## Remaining Non-Blocking Improvements

- Optional: export true pricing by configurable model-rate table (instead of only `gpt-4o-mini` estimate).
- Optional: add an integration test around `AutopilotService.refresh_opportunity_intelligence` summary embedding.
- Optional: emit per-batch latency histogram in downstream observability pipeline.

## Production Rollout Safety

With these additions, logging/observability is sufficient for safe monitored rollout under `ENTITY_RELEVANCE_SCORING_ENABLED=true`, while preserving deterministic fail-open behavior and rollout constraints.

A) Logging sufficient for production rollout
