# Editorial Opportunity Generator — Phase 1 Review

**Validation run:** `docs/validation/runs/2026-06-01T083533Z/`
**Workspace:** [example.com](https://www.example.com/) (`2a71aaf6-cc69-4663-be7f-7b13e50c3722`), niche = peptides
**Config:** deterministic only — `EDITORIAL_GENERATOR_ENABLED=true`, `EDITORIAL_GENERATOR_AI_ENABLED=false`, external market providers off.
**Method:** read-only; semi-manual rubric scoring of the top 25 against [OPPORTUNITY_QUALITY_VALIDATION_PLAN.md](../OPPORTUNITY_QUALITY_VALIDATION_PLAN.md). No code changed.

> Companion (same run, longer rubric table): [docs/validation/runs/2026-06-01T083533Z/EOG_PHASE1_REVIEW.md](../validation/runs/2026-06-01T083533Z/EOG_PHASE1_REVIEW.md).

---

## Recommendation: **Continue deterministic improvements. Do NOT begin Phase 2 AI refinement.**

Every quality-limiting defect in this run is deterministic — seed filtering, title string construction, diversity selection, and ranking. None is editorial nuance. An LLM pass now would add cost/latency while still inheriting garbage seeds and glossary-only finalists. Fix the rules, re-validate across ≥3 verticals, then reconsider Phase 2 only if the *residual* gap is genuine editorial voice.

**Primary limiters, ranked:** **C) diversity selection** ≈ **A) seed quality** > **B) title generation** > **D) opportunity ranking.**

---

## Scorecard (top 25, human review vs. automated)

| Metric | Automated | Human | Threshold | Status |
| --- | ---: | ---: | --- | --- |
| Publishable rate | — | **36% (9/25)** | ≥60% / <40% = pause | ❌ fail |
| Mean rubric score | — | **16.6/30** | ≥22 | ❌ fail |
| Junk rate | **0%** | **~44% (11/25)** | ≤10% / >25% = fail | ❌ fail |
| Content-type / topic-class diversity | **1** (`glossary`×25) | 1 | ≥4 | ❌ fail |
| Market-led CREATE share | 100% | 100% | ≥50% | ✅ |

Three failure thresholds triggered. **Automated metrics are misleading**: junk reads 0% because the tagger only knows the nav blocklist; explainability reads 100% because it checks field presence, not truth.

---

## 1. Top 25 recommendations

**Evidence** (`top25_analysis.json`, `metrics.json`): all 25 are `action=create`, `source_type=editorial_opportunity`, `topic_class=glossary`, identical pattern **`What Is {X}? Research Overview`**. Scores 0.857 → 0.699.

**Rubric scoring** (R/A/E/Au/N/Ac; publishable = ≥22 and no dim ≤2):

| # | Topic | Total | Pub |
|--:|---|--:|:--:|
| 1 | BPC-157 | 27 | Y |
| 2 | aging research | 18 | N |
| 3 | angiogenesis | 25 | Y |
| 4 | autophagy | 25 | Y |
| 5 | bactriostatic *(typo)* | 11 | N |
| 6 | bioenergetics | 22 | Y |
| 7 | biohacking | 16 | N |
| 8 | Research Peptides & Laboratory Compounds Example Lab *(brand)* | 7 | N |
| 9 | Kisspeptin | 26 | Y |
| 10 | Retatrutide | 27 | Y |
| 11 | CJC-1295 No DAC + IPA *(SKU)* | 12 | N |
| 12 | CJC-1295 | 25 | Y |
| 13 | exercise adaptation | 18 | N |
| 14 | copper peptides | 26 | Y |
| 15 | cellular stress | 20 | N |
| 16 | comparison discussions *(meta)* | 10 | N |
| 17 | customer *(ecommerce)* | 8 | N |
| 18 | comparison *(structural)* | 8 | N |
| 19 | european *(fragment)* | 7 | N |
| 20 | experimental design | 17 | N |
| 21 | focused *(fragment)* | 6 | N |
| 22 | peptides *(=niche, over-broad)* | 17 | N |
| 23 | fulfillment *(ops)* | 8 | N |
| 24 | glossary *(meta label)* | 7 | N |
| 25 | glucose metabolism | 22 | Y |

**Publishable: 9/25 (36%); mean 16.6/30.**
**Severity: High** — below the pause threshold. **Suggested fix:** not a single fix; addressed via findings 2–5 below.

---

## 2. Diversity across content types — **root cause C (critical)**

**Evidence** (`editorial_finalists.json`, `editorial_concepts.json`):

| Stage | Distribution |
| --- | --- |
| All concepts | glossary 165, educational_guide 148, research_overview 74, beginner_guide 60, faq 53 |
| **Finalists (148)** | **glossary 74, faq 74 — nothing else** |
| Top 25 | glossary 25 |

**Example:** every seed produces exactly one glossary + one faq finalist; `educational_guide` (148 generated) and `research_overview` (74) never reach OI.

**Why:** `select_finalists` ([app/editorial_opportunity/dedupe.py:43-86](../../app/editorial_opportunity/dedupe.py#L43-L86)) ranks by a **static `type_priority`** (`glossary=0.9`, `faq=0.85` always top) and `finalists_per_seed=2` → glossary+faq every time. `dedupe_across_workspace` ([dedupe.py:89-109](../../app/editorial_opportunity/dedupe.py#L89-L109)) caps per *topic-key* but has **no per-content-type cap**.

**Severity: Critical** — single biggest limiter.
**Suggested fix:** pick finalist content-types from the seed's own dominant intents/signal mix (the menu already exists in `generator.py`), and add a workspace-level per-content-type share cap so educational_guide / research_overview / comparison / beginner_guide reach OI. Target ≥4 classes in top 25.

---

## 3. Diversity across entities/topics — **acceptable**

**Evidence:** the 25 topics are 25 distinct entities (BPC-157, angiogenesis, Kisspeptin, Retatrutide…); `dedupe_across_workspace` `max_per_topic_key=3` works — no topic repeats.

**Severity: Low.** Topic spread is fine; the problem is the *same format* across distinct topics (finding 2), which makes the set *feel* repetitive despite topic variety.
**Suggested fix:** none for topic diversity itself; resolved by finding 2.

---

## 4. Repetition patterns — **root cause B + C**

**Evidence / examples:**
- 25/25 titles are `What Is {X}? Research Overview` (consequence of finding 2).
- **Title double-prefix bug: 30/148 finalist titles read `What Is what is {X}? …`** — e.g. `What Is what is Research Peptides & Laboratory Compounds Example Lab? Research Overview`. Seeds already starting with a question stem get re-prefixed by the glossary/faq template ([generator.py:243-252](../../app/editorial_opportunity/generator.py#L243-L252)).

**Severity: High** (monotony) / **Medium** (string bug, but very visible).
**Suggested fix:** (a) finding 2 for monotony; (b) strip leading question stems (`what is`, `how to`, `why`, `guide to`) from the seed topic before applying templates.

---

## 5. Weak concepts that should be filtered — **root cause A (critical)**

**Evidence:** `editorial_run.json` warnings show the filter *did* skip `Product Variations & Concentrations`, `MOTS-C`, `GHK-CU`, `Concentrations`, `stress`. But `is_weak_seed_topic` ([title_guards.py:18-27](../../app/editorial_opportunity/title_guards.py#L18-L27)) only blocks nav labels, a product-attribute regex, and single tokens **≤6 chars**, so these leaked into the top 25:

| Leaked seed | Class | Should block because |
| --- | --- | --- |
| `Research Peptides & Laboratory Compounds Example Lab` | brand/site name | matches workspace name |
| `peptides` | over-broad | equals the **primary niche** |
| `customer`, `fulfillment`, `european`, `focused` | generic/ops/fragments | generic English / ecommerce ops (7+ chars slip the length rule) |
| `comparison`, `comparison discussions`, `glossary` | meta/structural | not entities |
| `CJC-1295 No DAC + IPA` | SKU/variant | dosage/variant label, not a topic |
| `bactriostatic` | typo | misspelling of "bacteriostatic" |

Origin: a **polluted `niche_profile.known_entities`** (contains `Shop`, `checkout`, `card`, `gift`, `secure`, `clear`, `water`, `why`, `questions`, `customer`, `fulfillment`, `european`, `focused`, `glossary`, `comparison`…).

**Severity: Critical** — ~11/25 of the top set.
**Suggested fix (deterministic, niche-agnostic):** in `is_weak_seed_topic` add: (a) drop topic == workspace/brand name; (b) drop topic == or ⊆ primary niche; (c) a generic-English / ecommerce-ops / meta-label stoplist; (d) replace the `≤6 chars` heuristic with "single generic token not in known entities." **Better:** filter site-chrome out of `known_entities` / market-signal generation upstream so junk never becomes a seed (EOG filter is the backstop). Typo handling (`bactriostatic`) is lowest priority — gate low-confidence single entities against a domain lexicon; not LLM-worthy.

---

## 6. Strongest concepts

**Evidence:** highest rubric totals, all clean real entities.

| Topic | Total | Why strong |
|---|--:|---|
| BPC-157 | 27 | flagship entity, high demand |
| Retatrutide | 27 | high-interest GLP-1 peptide |
| Kisspeptin | 26 | clean entity, draftable |
| copper peptides | 26 | real category |
| angiogenesis | 25 | legitimate mechanism explainer |
| autophagy | 25 | legitimate mechanism explainer |
| CJC-1295 (canonical) | 25 | core entity |

**Note:** even these all share one format — the diversity fix (finding 2) would let each spawn glossary + faq + comparison + research_overview instead of glossary alone.

---

## 7. Weakest concepts

| Topic | Total | Failure |
|---|--:|---|
| focused | 6 | adjective fragment |
| Research Peptides & Laboratory Compounds Example Lab | 7 | brand/site name |
| european | 7 | fragment |
| glossary | 7 | meta label (the word itself) |
| customer | 8 | ecommerce generic |
| comparison | 8 | structural label |
| fulfillment | 8 | ops term |
| comparison discussions | 10 | meta |
| bactriostatic | 11 | typo |
| CJC-1295 No DAC + IPA | 12 | SKU/variant |

All are finding-5 seed-quality leakage.

---

## 8. Are deterministic improvements sufficient? — **Yes.**

Mapping every limiter to its (deterministic) root cause:

| Finding | Root cause | LLM needed? |
| --- | --- | --- |
| Glossary-only finalists / top 25 | **C** diversity selection | No |
| `What Is what is X?` | **B** title construction | No |
| Monotone `Research Overview` | **C** (+ template) | No |
| brand / `peptides` / `customer` / SKU / fragments | **A** seed quality | No |
| glossary outranks faq → sweeps top | **D** ranking | No |
| dishonest "competitor evidence exists" reason (`source_mix` is internal-only; see `recommendations.json[0]`) | rule/text | No |
| `bactriostatic` typo | input data | Marginal, not LLM |

**Evidence for D:** finalists are 50/50 glossary/faq, but glossary (`authority_value=0.7`) outscores faq (`0.58`) in OI, so glossary fills the top 25. Secondary to C — fixing C makes D mostly moot, but a content-type diversity cap in OI ranking is a cheap reinforcement.

**Severity of remaining gap after deterministic fixes:** unknown until re-validation, but the *visible* defects are all addressable without AI.

---

## 9. Is Phase 2 AI refinement justified? — **Not yet.**

**Evidence:** the input quality (`evidence_summary` = "Cluster backed by 1 signals from internal-context" for 102/148 finalists; `source_mix` = internal-context only for all 148) means an LLM would refine prose over thin, sometimes-garbage seeds. The deterministic layer has not yet produced a clean, diverse, honest top 25, so there is no proven editorial-nuance ceiling to break through.

Phase 2 becomes justifiable **only after** deterministic fixes 2/4/5 land and re-validation shows: publishable ≥ ~60%, ≥4 topic classes, ≤10% junk — and the *remaining* complaint is "titles are correct but generically phrased / lack voice." We are not there.

---

## Conclusion

**Continue deterministic improvements.** Priority order:

1. **Finalist diversity (C):** intent-driven finalist content-types + workspace per-type cap.
2. **Seed filtering (A):** brand/niche-equality/generic-token/meta-label blocks; ideally clean `known_entities` upstream.
3. **Title bug (B):** strip leading question stems before templating.
4. **SKU/variant filtering (A):** extend product-attribute regex.
5. **Ranking diversity (D):** content-type cap in OI top-N as reinforcement.
6. **Reason honesty:** don't claim competitor evidence when no competitor provider is in `source_mix`.

Then re-run `python scripts/run_opportunity_quality_validation.py --refresh` on example-lab **plus ≥2 more verticals** (current evidence is single-workspace) and re-score. **Hold Phase 2 AI refinement** until deterministic output is clean, diverse, and honest.
