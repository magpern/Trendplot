# Science-first ideation sample validation

**Date:** 2026-06-05  
**Workspace:** `48c761a6-2698-4a1d-8022-f23bfd1d5cb6` (Example Lab)  
**Prompt:** `ai_opportunity_ideation` v4  
**Sample size:** 25 opportunities (`force_refresh=true`)

---

## Category distribution

| Category | Count | % |
|----------|------:|--:|
| Product/science overview | 11 | 44.0% |
| Comparison | 9 | 36.0% |
| Product relationship | 4 | 16.0% |
| Mechanism/background | 1 | 4.0% |
| Handling/storage/reconstitution | 0 | 0.0% |
| FAQ/resource | 0 | 0.0% |
| Supplier/catalog guidance | 0 | 0.0% |

**Science editorial categories (overview + comparison + relationship + mechanism):** 25 / 25 = **100%**

No opportunities classified as supplier listings, catalog navigation, documentation quality, or inventory planning.

---

## Top 20 sample recommendations

1. BPC-157 research overview: signaling pathways and literature themes
2. BPC-157 vs TB-500: how researchers distinguish related preclinical peptide themes
3. CJC-1295 (No DAC + IPA) research overview: GH axis signaling and experimental context
4. CJC-1295 vs GHRH: receptor pathway differences and why literature often separates them
5. GHK-CU research overview: copper peptide biology and cellular signaling themes
6. GHK-CU vs GHK: what researchers mean by copper-associated peptide effects
7. Kisspeptin research overview: KISS1 signaling and reproductive-axis pathway themes
8. Kisspeptin vs GHRH: comparing neuroendocrine peptide pathway logic
9. MELANOTAN-II research overview: melanocortin receptor signaling themes
10. MELANOTAN-II vs TRIPLE-G: comparing GPCR-linked peptide signaling themes
11. MOTS-C research overview: mitochondrial peptide signaling and cellular stress pathways
12. MOTS-C vs Humanin: related mitochondrial peptide signaling themes and distinctions
13. TB-500 research overview: actin-related biology themes and preclinical signaling context
14. TB-500 vs BPC-157: comparing how literature frames cellular repair and signaling hypotheses
15. Tirzepatide research overview: GLP-1/GIP receptor signaling themes
16. Tirzepatide vs Retatrutide: comparing multi-receptor incretin pathway concepts
17. TRIPLE-G research overview: receptor pathway themes in multi-incretin discourse
18. TRIPLE-G vs Tirzepatide: how researchers compare multi-receptor incretin signaling
19. Retatrutide research overview: receptor pathway logic in multi-incretin literature
20. Retatrutide vs Tirzepatide: comparing how receptor engagement shapes signaling interpretations

---

## Success criteria

| Criterion | Result |
|-----------|--------|
| Reads like editorial science content | **Pass** — headlines emphasize signaling, receptors, literature, biology |
| Not supplier/documentation/catalog guides | **Pass** — 0% supplier/catalog classification |
| Mechanism/pathway language present | **Pass** — receptor biology, signaling, pathway themes throughout |
| Handling not dominant | **Pass** — 0% handling |

**Note:** Catalog coverage warning (`catalog_products_not_fully_covered:13`) is expected on a 25-idea sample with full-catalog rules; production runs use 40–75 ideas.

---

## Implementation reference

| Change | File |
|--------|------|
| Science-first examples + supplier avoidance + depth scoring | `app/prompts/templates/ai_opportunity_ideation.yaml` (v4) |
| Article brief enrichment (`science_focus`, pathways, concepts) | `app/ai_opportunity_ideation/article_brief.py` |
| Recommendation metadata `article_brief` | `app/ai_opportunity_ideation/recommendations.py` |
| Generation-time brief enrichment | `app/services/jobs.py` |
| UI uses enriched `article_brief` | `app/analyze_ui.py` |
| `science_focus` generation instruction | `app/prompts/templates/article_generation.yaml` |
