# Article generation trace: Best Practices for Storing Bacteriostatic Water

Investigation of a completed generation job (read-only; no code changes). Artifacts were read from `data/seo_content_worker.db`.

## Job identity

| Field | Value |
|--------|--------|
| Job ID | `2509c670-0e5e-4284-a3b4-fb271be226b1` |
| Status | `ready_for_review` |
| Workspace | `48c761a6-2698-4a1d-8022-f23bfd1d5cb6` |
| Content plan item | `9628cdeb-8b87-4e71-ab34-3cbc8c56b802` |
| Origin | `content_plan_item` / `ai_opportunity_ideation` |

---

## 1. Exact prompt template(s) used

### Primary: `article_generation` (v1)

Source: `app/prompts/templates/article_generation.yaml`, rendered by `build_article_prompt()` → `app/prompts/__init__.py`.

The registry appends **Output contract** and **Safety rules** after variable substitution (`app/prompts/prompt_renderer.py`).

**Template body (placeholders before render):**

```yaml
Create a high-quality SEO article as strict JSON.

Input:
- Title: {{ title }}
- Target keyword: {{ target_keyword }}
- Product name: {{ product_name }}
- Product URL: {{ product_url }}
- Target length: {{ target_word_count }} words unless the topic genuinely requires less.
- Editorial opportunity brief (when provided, use as planning context — do not copy verbatim): {{ opportunity_context_json }}

Return strict JSON with exactly the canonical article schema:
title, slug, excerpt, meta_title, meta_description, primary_keyword, secondary_keywords,
key_takeaways, table_of_contents, sections, faq, research_context, limitations_and_safety,
internal_links, references_to_verify, related_video, social_posts, backlink_plan,
callout_boxes, research_insights, study_cards, definition_boxes, caution_boxes,
comparison_tables, research_metadata_panel, related_topics, and inline_citation_markers.

Article quality requirements:
- The article body must live in sections[*].content_markdown, not final HTML.
- The combined section content must contain at least 1800 words.
- Use 10-14 meaningful sections with 150-300 words in most body sections.
- Use hierarchy: H1 is title, sections are H2-level, and sections may include subsections as H3-level subtopics.
- Avoid flat section dumps. Use subsections when a major topic contains distinct methods, models, mechanisms, limitations, or interpretation notes.
- Add rich components only when useful: study cards, definitions, caution boxes, comparison tables, research metadata, and callouts.
- Label unverified sources as references to verify. Do not present reference leads as confirmed citations.
- Include Key Takeaways, Research Context, practical researcher-oriented sections, Limitations and Safety Notes, References to verify, and FAQ.
- Mention the product/category naturally and include the product URL through a natural internal link suggestion.
- Include a concise conclusion or closing research-context summary before FAQ/references.
- Backlink planning is advisory only and requires human approval before action.
- Avoid generic AI-style phrases and formulaic transitions.

Output contract:
Return valid JSON matching the canonical article schema. Do not wrap it in Markdown.

Safety rules:
- Do not invent citations, PubMed IDs, DOIs, prices, guarantees, awards, reviews, or unverifiable claims.
- Do not provide dosage instructions, human-use instructions, treatment recommendations, or therapeutic claims.
- Preserve research-use-only framing and include the configured RUO disclaimer when relevant.
- Do not output HTML in section content.
- Do not use emoji, em dashes, en dashes, or smart quotes.
```

**System message** (not in YAML; set in `app/content_generation.py`):

```text
You are a senior SEO content strategist and scientific editor. Return strict JSON only.
```

**API shape:** `response_format: { "type": "json_object" }`, task `ARTICLE_GENERATION` → premium tier.

### Secondary prompts (same job, later stages)

| Stage | Prompt ID | When |
|--------|-----------|------|
| Article repair | `article_repair` | Initial quality check failed (missing RUO disclaimer) |
| Section expansion | `section_expansion` | 5 expansion passes (thin `research_context`, `limitations_and_safety`, and 3 body sections) |
| Humanization | `humanization` (+ per-section prompts) | All 27 rewrite targets |
| Narrative editor | `narrative_editor` | Final polish pass (0 edits applied) |
| Semantic sanity | `sanity_review` (semantic domain) | Compliance/factual guardrails |
| SEO metadata | `seo_metadata` | Meta title/description after article finalized |
| YouTube evaluation | `youtube_evaluation` | Candidate scoring (`gpt-5.4-mini`) |

---

## 2. Exact context payload supplied to the model

### Generation command (`request_input`)

```json
{
  "title": "Best Practices for Storing Bacteriostatic Water",
  "target_keyword": "Best Practices for Storing Bacteriostatic Water",
  "product_name": "Bacteriostatic Water",
  "product_url": "https://www.example.com/",
  "publish_policy": "manual_review",
  "workspace_id": "48c761a6-2698-4a1d-8022-f23bfd1d5cb6",
  "content_plan_item_id": "9628cdeb-8b87-4e71-ab34-3cbc8c56b802",
  "origin_type": "content_plan_item",
  "opportunity_context": {
    "headline": "Best Practices for Storing Bacteriostatic Water",
    "abstract": "Learn the optimal conditions for storing Bacteriostatic Water to ensure its stability and effectiveness in laboratory settings.",
    "search_intent": "informational",
    "content_type": "guide",
    "recommendation_type": "create",
    "related_products": ["Bacteriostatic Water", "Bacteriostatic Water - Example Lab"],
    "related_topics": ["storage", "handling"],
    "target_audience": "Laboratory Technicians",
    "safety_notes": ["For research use only. Not intended for human consumption."],
    "source": "ai_opportunity_ideation"
  }
}
```

### Rendered user prompt (artifact `prompt`, target `structured_article`)

The stored artifact matches the template above with:

- `target_word_count`: `1800-3000` (default in `ArticlePromptInput`)
- `opportunity_context_json`: pretty-printed JSON of `opportunity_context` (embedded in the prompt body)

No separate RAG bundle, PubMed fetch, or product DB grounding was attached to this generation call (`product_data_grounding_plan` artifact provider: `null-product-data`).

---

## 3. Model name

| Call | Model | Tier | Notes |
|------|--------|------|--------|
| Initial article generation | **`gpt-5.4`** (`gpt-5.4-2026-03-05` in API response) | PREMIUM | Reasoning enabled, effort `medium` |
| Article repair | `gpt-5.4` | PREMIUM | 1 pass |
| Section expansion | `gpt-5.4` | PREMIUM | 5 section targets |
| Humanization | `gpt-5.4` | PREMIUM | 27 sections rewritten |
| Narrative editor | `gpt-5.4` | PREMIUM | |
| Sanity review | `gpt-5.4` | PREMIUM | |
| SEO metadata / social / references artifacts | `gpt-5.4` | PREMIUM | Post-article enrichment |
| YouTube evaluation | `gpt-5.4-mini` | STANDARD | Selected video `Ik_iivTlvrU` |

Router mapping: `ModelTask.ARTICLE_GENERATION` → `ModelTier.PREMIUM` (`app/providers/model_router.py`).

**Usage (initial generation only):** 741 prompt tokens, 10,738 completion tokens (2,975 reasoning tokens).

---

## 4. Raw model response before post-processing

**Artifact:** `raw_llm_response` with `target_artifact_type: structured_article_initial`.

**Format:** OpenAI chat completion; assistant `message.content` is a single JSON string (not Markdown-wrapped).

**Shape:** Canonical article schema JSON. Initial generation already included:

- 11 `sections` with `content_markdown` and H3 subsections
- `research_insights` (4 items; alternate field names `evidence_status`, `practical_use`)
- `study_cards` (3 items titled **`Evidence gap: …`**)
- `callout_boxes`, `definition_boxes`, `caution_boxes`, `comparison_tables`
- `research_metadata_panel` (editorial fields like `evidence_profile`, not the normalized lab panel)
- `references_to_verify` (5 items with `source_lead`, `what_to_verify[]`, `status: unverified`)
- `research_context` and `limitations_and_safety` as **objects** (not plain strings)

**Excerpt — `study_cards[0]` as returned by the model (unchanged semantics in final output):**

```json
{
  "title": "Evidence gap: Preservative performance after repeated vial access",
  "summary": "Laboratories should not assume that preservative presence alone defines safe repeated access conditions.",
  "what_to_verify": [
    "Manufacturer challenge data if available",
    "Any labeled limits or use-after-opening statements",
    "Applicability of internal risk assessments to multi-user workflows"
  ],
  "status": "verification needed"
}
```

**Excerpt — `research_insights[0]` as returned:**

```json
{
  "insight": "Most practical failures arise from documentation gaps and repeated-access handling, not from storage shelving alone.",
  "evidence_status": "Practice-based insight requiring local verification against SOPs and product documents.",
  "practical_use": "Focus training on opened-vial control, traceability, and quarantine decisions."
}
```

Full raw payload is stored in the job artifact (~10.7k completion tokens). It is not duplicated here in full.

---

## 5. Post-processing steps applied

Pipeline order from `app/services/jobs.py` `_run_generation_job`:

| Step | Component | This job |
|------|-----------|----------|
| 1 | **`normalize_article()`** | Maps alternate LLM shapes → `ArticleSchema` (e.g. `research_insights` fields, `study_cards.summary` → `observed_finding`, object `limitations_and_safety` → string) |
| 2 | **Quality checks** | Failed: missing biomedical RUO disclaimer |
| 3 | **Article repair** (`article_repair`) | 1 pass; added disclaimer, expanded limitations/references, filled `research_metadata_panel` |
| 4 | **Section expansion** | 5 targets; words 3,235 → 4,482 |
| 5 | **Redundancy review + cleanup** | Deterministic dedupe |
| 6 | **Humanization** | Section-based rewrite; 27/27 sections; AI pattern score 60 → 52 |
| 7 | **Post-humanization redundancy review** | |
| 8 | **Narrative editor** | Attempted; **0 edits applied** (15 skipped) |
| 9 | **Internal linking** | Product URL woven into markdown |
| 10 | **Image placement / generation** | Featured image placeholder (AI image disabled in env) |
| 11 | **YouTube evaluation + embed** | `gpt-5.4-mini` selected one video |
| 12 | **`render_article()`** | HTML via `app/rendering/article_renderer.py` + bleach sanitize |
| 13 | **Semantic sanity review** | Targeted rewrites in 4 locations + deterministic guardrail on 3 |
| 14 | **Re-render** | Updated `structured_article_json`, `article_html` |
| 15 | **SEO metadata / social / reference artifacts** | Separate LLM calls; stored as job artifacts |
| 16 | **Publish decision / WordPress metadata** | Manual review policy |

**Not applied:** Second `structured_article_json` pass differed only after sanity; rich-component arrays (`study_cards`, `research_insights`, etc.) were present in both pre- and post-sanity structured JSON snapshots for this job.

---

## 6. Source of named UI sections

| User-facing section | JSON / data source | Display heading source |
|---------------------|-------------------|-------------------------|
| **Research Insights** | `research_insights[]` | **Formatter:** `article_renderer._research_insights()` → H2 `"Research Insights"` |
| **Research Notes To Verify** | `study_cards[]` | **Formatter:** `_study_cards()` → H2 `"Research Notes To Verify"`; card **titles** from model (e.g. `"Evidence gap: …"`) |
| **Research Callouts** | `callout_boxes[]` | **Formatter:** `_callout_boxes()` → H2 `"Research Callouts"` |
| **Confidence Notes** | `research_metadata_panel.confidence_notes` | **Formatter:** `_research_metadata()` → parent H2 `"Research Metadata"`, sub-label **"Confidence notes"** (fixed label in renderer) |
| **Evidence Gaps** | *Not a separate H2 in codebase* | **Prompt + model content:** gaps appear as **`study_cards[].title`** prefixed with `"Evidence gap:"`, rendered **inside** "Research Notes To Verify" |
| **References To Verify** | `references_to_verify[]` | **Prompt** names the field; **formatter** → H2 `"References to verify"` (`_references()`) |

**Related (not in your list but in rendered HTML):**

- **Research Metadata** — `research_metadata_panel` (status, study types, human-use, RUO, confidence notes)
- **Research Context** — `research_context` string
- **Limitations and Safety Notes** — `limitations_and_safety` string
- **Research Material Reference** — **Formatter only** (`_research_use_cta()`): boilerplate + first `internal_links[0]` (product URL)

---

## 7. Origin classification per section

| Section | Prompt instructions | Structured metadata (schema) | Article formatter | Post-processing |
|---------|--------------------|------------------------------|-------------------|-----------------|
| Research Insights | Requires `research_insights` in schema list; “rich components when useful” | `ResearchInsight` model; `_normalize_research_insights()` maps `evidence_status` → `limitation` | H2 title + card layout | Repair/humanization may rewrite prose fields; heading unchanged |
| Research Notes To Verify | Requires `study_cards`; “label unverified sources” | `StudyCard` model; normalizes `summary` → `observed_finding` | H2 title + card field labels (Source, Context, …) | Same; **“Evidence gap”** wording is **model-authored** in `title` |
| Research Callouts | Requires `callout_boxes` | `CalloutBox`; `content[]` → joined `message` | H2 + simple boxes | Humanization may rephrase `message` text |
| Confidence Notes | Implied via `research_metadata_panel` | `confidence_notes` field; repair filled content | Fixed subheading under Research Metadata | Repair populated panel; normalizer maps `notes`/`limitations` aliases |
| Evidence Gaps | No exact string in prompt; model uses gap framing in `study_cards` | Stored as `study_cards[].title` | Shown as H3 inside study-cards section | Not split into separate field |
| References To Verify | Explicit in requirements + schema | `ReferenceToVerify`; repair reshaped to `title`/`search_query`/`reason` | H2 + list markup | Repair + optional `seo_metadata` artifact duplication |

---

## Rendered document order (formatter)

From `render_article()` section assembly:

1. Hero (title + excerpt)  
2. Key Takeaways  
3. Table of Contents  
4. Research Metadata (includes Confidence notes)  
5. Definitions  
6. Research Context  
7. Body sections (H2 from `sections[].heading`)  
8. **Research Insights**  
9. **Research Notes To Verify** (includes Evidence gap cards)  
10. Comparison tables  
11. **Research Callouts**  
12. Cautions  
13. Limitations and Safety Notes  
14. Research Material Reference (CTA)  
15. Related Research Topics  
16. FAQ  
17. **References to verify**  
18. Related Video (YouTube embed)

---

## Conclusion

### **C) Mixed origin**

- **Prompt-driven:** JSON field names, requirement to include rich research components, references-to-verify discipline, and model-chosen content (including `"Evidence gap:"` card titles and insight text).
- **Formatter-driven:** All top-level H2 labels (`Research Insights`, `Research Notes To Verify`, `Research Callouts`, `Research Metadata` / `Confidence notes`, `References to verify`, `Research Material Reference`), HTML structure, and fixed study-card sublabels.
- **Post-processing:** `normalize_article`, article repair (RUO + references + metadata panel), section expansion (body + research_context + limitations), humanization (section prose), sanity guardrails, internal linker, and bleach sanitization—without changing formatter section titles.

There is **no** dedicated `evidence_gaps` schema field; “Evidence Gaps” in the UI are **study card titles** under the formatter heading **Research Notes To Verify**.

---

*Generated from job `2509c670-0e5e-4284-a3b4-fb271be226b1` on 2026-06-02.*
