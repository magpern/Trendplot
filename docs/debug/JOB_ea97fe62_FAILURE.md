# Job failure report: `ea97fe62-00f1-4b3a-a7c6-fd55b19233a7`

**Job title:** CJC-1295 No DAC + IPA: what "No DAC + IPA" means for lab handling (RUO)  
**Final status:** `failed_generation`  
**Investigated:** 2026-06-05  
**Database:** `data/seo_content_worker.db`

---

## Executive summary

The job **completed article generation, rendering, quality checks, deterministic sanity, and publish metadata** successfully, then **crashed while building the final return payload** with:

```text
NameError: name 'rendered_article' is not defined
```

**Exact failing lines:** [`app/services/jobs.py`](../../app/services/jobs.py) **1573** and **1584** (referenced during evaluation of the `return { ... }` dict at the end of `_run_generation_job`).

This is a **pipeline code bug**, not a config mismatch or article validation failure.

---

## Exact exception

| Field | Value |
|-------|--------|
| Exception type | `NameError` |
| Message | `name 'rendered_article' is not defined` |
| Stored on job | `jobs.last_error` |
| Log step | `job` / level `error` / `"Job failed."` |
| Log time | `2026-06-05T06:53:54.230663+00:00` |

### Failing code (current tree)

```1571:1585:app/services/jobs.py
            "structured_article": structured_article,
            "rendered_html": article_html,
            "renderer_logs": rendered_article.logs,
            "job_run_metrics": run_metric_artifacts["job_run_metrics"],
            ...
            "image_rendering_summary": _image_rendering_summary(
                image_workflow.image_generation_result.content_json or {},
                rendered_article.logs,
            ),
```

`rendered_article` is never assigned in `_run_generation_job`. Rendering uses `_save_rendered_article_artifacts(...)`, which returns `(publishable_html, editorial_html)` and **persists** renderer logs to the `renderer_logs` artifact — it does not expose a `rendered_article` object in this scope.

---

## Timeline (job_logs)

| Time (UTC) | Step | Message |
|------------|------|---------|
| 06:48:26 | job | Article generation queued. |
| 06:48:26 | job | Job started. |
| 06:53:45 | section_expansion | Expanding thin article sections. |
| 06:53:45 | redundancy_review | Reviewing article redundancy. |
| 06:53:46 | narrative_editor | Running final narrative editor pass. |
| 06:53:46 | content_generation | Generated structured article. |
| 06:53:48 | rendering | Rendering article preview. |
| 06:53:49 | sanity_review | Running deterministic sanity guardrails. |
| 06:53:54 | job | Job failed. (`NameError`) |

Wall time ~327s per `job_run_metrics`.

---

## 1. Why did `section_expansion` run?

The **stage ran** (`metrics.start_stage("section_expansion")` and progress log fire **before** the gate), but **LLM expansion did not execute**.

Evidence — `section_expansion_summary` artifact:

```json
{
  "attempted": false,
  "skipped": true,
  "stage": "section_expansion",
  "reason": "Simplified pipeline: section expansion disabled or article already meets 1800 words.",
  "word_count_before": 2592,
  "word_count_after": 2592,
  "pass_count": 0,
  "expanded_sections": []
}
```

- `job_run_metrics.stages[section_expansion].model_calls`: **[]**
- Initial quality word count: **2592** (above 1800 threshold)

**Conclusion:** Progress text is misleading; expansion was **skipped by design**, not expanded.

---

## 2. Why did `narrative_editor` run?

Same pattern: **stage wrapper + progress log**, **no LLM call**.

Evidence — `narrative_editor_summary`:

```json
{
  "attempted": false,
  "skipped": true,
  "stage": "narrative_editor",
  "reason": "Simplified pipeline: narrative editor disabled."
}
```

- `job_run_metrics.stages[narrative_editor].model_calls`: **[]**
- `narrative_editor_prompt` content length: **0**

**Conclusion:** Narrative editor **did not run**; only the orchestration step and skip artifacts ran.

---

## 3. Was `SIMPLIFIED_ARTICLE_PIPELINE=true` loaded?

**Yes — inferred from runtime behavior** (no `runtime_config` artifact is persisted).

| Signal | Value |
|--------|--------|
| Total LLM cost | $0.069 (single `article_generation` call) |
| Humanization skipped | `"Simplified pipeline: editorial humanization disabled."` |
| Narrative skipped | `"Simplified pipeline: narrative editor disabled."` |
| Sanity mode | `"mode": "deterministic"` |
| YouTube selection | `youtube-heuristic` (not AI eval) |
| Current `Settings()` defaults | `simplified_article_pipeline=True` |

`.env` does **not** override `SIMPLIFIED_ARTICLE_PIPELINE` (flag absent → default `true`).

---

## 4. Was `ENABLE_SECTION_EXPANSION=false` loaded?

**Yes.**

- Skip reason explicitly cites disabled expansion / word target met.
- Zero expansion model calls.
- Current `Settings()`: `enable_section_expansion=False`
- `.env`: flag not set → default `false`

---

## 5. Was `ENABLE_NARRATIVE_EDITOR=false` loaded?

**Yes.**

- `narrative_editor_summary.skipped: true` with simplified-pipeline reason.
- Zero narrative model calls.
- Current `Settings()`: `enable_narrative_editor=False`

---

## 6. What happened after deterministic sanity guardrails?

| Step | Result |
|------|--------|
| Deterministic sanity | **Passed** (`sanity_check_results.passed: true`) |
| Sanity rewrite | No changes (`changed_locations: []`) |
| Re-render after sanity | Completed (second `publishable_html` / `article_html` pair) |
| Final quality check | **Passed** (`word_count: 2592`, 1 warning: missing closing summary) |
| Publish decision | **Completed** (`publish_decision_report` artifact exists) |
| WordPress metadata | **Written** (`final_publish_metadata`, tag suggestions) |
| Final return dict | **Crashed** on `rendered_article.logs` |

Sanity warnings (non-blocking): repeated `storage_handling_needs_source` on title/excerpt/sections.

---

## 7. Does `structured_article_json` exist?

**Yes.**

| Artifact | Created (UTC) | JSON size |
|----------|---------------|-----------|
| `structured_article_json` | 2026-06-05T06:53:46.544807 | 26,394 bytes |
| `structured_article` | 2026-06-05T06:53:46.566756 | 26,394 bytes |
| `article_markdown` | 2026-06-05T06:53:46.585135 | 17,853 chars text |

---

## 8. Does `publishable_html` exist?

**Yes** (two saves: pre- and post-sanity render).

| Artifact | Count | Latest created (UTC) | Text length |
|----------|------:|----------------------|------------:|
| `publishable_html` | 2 | 06:53:49.959391 | 24,241 chars |

---

## 9. Does `article_html` exist?

**Yes.**

| Artifact | Count | Latest created (UTC) |
|----------|------:|----------------------|
| `article_html` | 2 | 06:53:50.125313 |
| `rendered_html` | present | same pipeline |
| `renderer_logs` | present | `{"publishable_logs": [], "editorial_logs": []}` |

Rendering succeeded; logs were saved via `_save_rendered_article_artifacts`.

---

## 10. What caused final job failure?

| Category | Applicable? | Notes |
|----------|-------------|-------|
| Config/runtime mismatch | **No** | Simplified flags behaved correctly |
| Pipeline bug | **Yes** | Undefined `rendered_article` in return dict |
| Article validation failure | **No** | Quality + sanity **passed** |
| Artifact/rendering failure | **No** | All key artifacts persisted |
| Publish metadata failure | **No** | `publish_decision_report` + `final_publish_metadata` exist |

Failure occurs **after** successful validation/rendering/metadata, when `_run_generation_job` assembles its Python return value. Exception handler marks job `failed_generation` ([`jobs.py` ~276–309](../../app/services/jobs.py)).

---

## Model / cost summary

| Stage | OpenAI calls | Cost |
|-------|-------------:|-----:|
| article_generation | 1 | $0.069 |
| section_expansion | 0 | $0 |
| humanization | 0 | $0 |
| narrative_editor | 0 | $0 |
| sanity (LLM) | 0 | $0 |

Simplified pipeline operated as intended until the return-dict bug.

---

## Recommended fix (not applied — investigation only)

Replace `rendered_article.logs` with logs already persisted or returned from `_save_rendered_article_artifacts` (e.g. load from latest `renderer_logs` artifact, or extend that helper to return logs alongside HTML).

---

## Conclusion

**B) Pipeline bug**

Exact exception: `NameError: name 'rendered_article' is not defined` at **`app/services/jobs.py:1573`** (and line **1584** in the same return dict).
