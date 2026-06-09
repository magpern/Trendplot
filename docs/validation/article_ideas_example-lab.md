# Article idea experiment — Example Lab

- Workspace: `2a71aaf6-cc69-4663-be7f-7b13e50c3722`
- URL: https://www.example.com/
- Niche: peptides
- Catalog products in brief: 7
- Headlines generated: 26
- Product coverage: 1.0 (7/7)

## Request sent to OpenAI

**Model:** `gpt-4o-mini`

### System message

```text
You generate SEO article headlines for research-oriented ecommerce sites. No medical claims. No human consumption or dosing. Every catalog product in the brief must appear in at least one headline. Respond with JSON only.
```

### Catalog products (must be covered)

- Kisspeptin
- Retatrutide
- MOTS-C
- BPC-157
- GHK-CU
- CJC-1295
- Bactiostatic Water

### Site brief JSON

```json
{
  "workspace_id": "2a71aaf6-cc69-4663-be7f-7b13e50c3722",
  "analysis_job_id": "98d47dd8-c8e3-4d3e-bbe5-96b2182720ed",
  "website_url": "https://www.example.com/",
  "site_name": "Example Lab",
  "niche": "peptides",
  "site_description": "Peptides ecommerce site (https://www.example.com/).",
  "business_type": "ecommerce",
  "catalog_products": [
    "Kisspeptin",
    "Retatrutide",
    "MOTS-C",
    "BPC-157",
    "GHK-CU",
    "CJC-1295",
    "Bactiostatic Water"
  ],
  "products": [
    "Kisspeptin",
    "Retatrutide",
    "MOTS-C",
    "BPC-157",
    "GHK-CU",
    "CJC-1295",
    "Bactiostatic Water"
  ],
  "categories": [
    "aging research",
    "bpc-157",
    "mots-c",
    "peptides",
    "topical_article",
    "ampk",
    "cjc-1295"
  ],
  "entities": [
    "Research Peptides & Laboratory Compounds Example Lab",
    "Product Variations & Concentrations",
    "Kisspeptin",
    "Retatrutide",
    "MOTS-C",
    "CJC-1295 No DAC + IPA",
    "BPC-157",
    "GHK-CU",
    "CJC-1295",
    "aging research",
    "ampk",
    "angiogenesis",
    "autophagy",
    "bactriostatic",
    "bioenergetics",
    "biohacking",
    "card",
    "cellular stress",
    "clear",
    "comparison",
    "comparison discussions",
    "copper peptides",
    "customer",
    "dac",
    "european",
    "peptides",
    "Research",
    "Laboratory",
    "Compounds",
    "Example Lab"
  ],
  "services": [
    "Research Peptides & Laboratory Compounds Example Lab",
    "Shop",
    "Product Variations & Concentrations",
    "Kisspeptin",
    "Retatrutide",
    "MOTS-C",
    "CJC-1295 No DAC + IPA",
    "BPC-157",
    "GHK-CU",
    "Bpc-157",
    "CJC-1295",
    "Cjc-1295",
    "Ghk-Cu",
    "Mots-C"
  ],
  "audiences": [
    "Research-oriented readers",
    "Comparison and sourcing visitors"
  ],
  "constraints": [
    "Research and laboratory use framing only",
    "No human consumption, dosing, treatment, clinical, or veterinary use",
    "No medical claims"
  ],
  "disclaimers": [
    "For research use only. Not intended for human consumption, therapeutic, or diagnostic use."
  ],
  "existing_page_titles": [],
  "competitor_domains": [],
  "competitor_gap_topics": [],
  "suggested_themes": [
    "reconstitution",
    "storage",
    "handling",
    "stability",
    "concentration",
    "lab calculations",
    "comparison articles",
    "FAQ and guide articles"
  ]
}
```

### User prompt

```text
Generate SEO article headline ideas for this website.

You receive a compact site brief — not a crawl dump. Use only fields present in the JSON.

Generate between 25 and 50 headline ideas.

**Catalog coverage (required):** The brief includes `catalog_products` — the site's actual product SKUs.
When `catalog_products` has 25 or fewer items, include **every catalog product by exact name** in at least one headline.
Spread remaining headlines across comparisons, storage, reconstitution, handling, FAQ, and lab guides using those products.

Focus on article ideas that could plausibly attract organic search traffic:
- Product/niche-specific questions, comparisons, guides, storage, handling, preparation
- FAQ and research-context topics tied to catalog products
- Comparison articles (Product A vs Product B) where products are listed
- Lab-practice guides: reconstitution, storage, handling, stability, concentration, calculations

Avoid:
- Generic glossary spam ("What is X" for every entity unless X is a core catalog product)
- Topics unrelated to products, categories, niche, or competitor gaps in the brief
- Legal, policy, or navigation pages as article subjects

Safety (mandatory):
- Use research/laboratory framing when the brief indicates research peptides, lab compounds, or RUO context
- Do NOT make medical claims
- Do NOT imply human consumption, dosing, treatment, clinical use, or veterinary use
- Headlines should be useful SEO titles, not article bodies

Include product names from `catalog_products` where relevant — do not invent products not in the brief.
Respect constraints and disclaimers in the brief.

Site brief JSON:
{"workspace_id":"2a71aaf6-cc69-4663-be7f-7b13e50c3722","analysis_job_id":"98d47dd8-c8e3-4d3e-bbe5-96b2182720ed","website_url":"https://www.example.com/","site_name":"Example Lab","niche":"peptides","site_description":"Peptides ecommerce site (https://www.example.com/).","business_type":"ecommerce","catalog_products":["Kisspeptin","Retatrutide","MOTS-C","BPC-157","GHK-CU","CJC-1295","Bactiostatic Water"],"products":["Kisspeptin","Retatrutide","MOTS-C","BPC-157","GHK-CU","CJC-1295","Bactiostatic Water"],"categories":["aging research","bpc-157","mots-c","peptides","topical_article","ampk","cjc-1295"],"entities":["Research Peptides & Laboratory Compounds Example Lab","Product Variations & Concentrations","Kisspeptin","Retatrutide","MOTS-C","CJC-1295 No DAC + IPA","BPC-157","GHK-CU","CJC-1295","aging research","ampk","angiogenesis","autophagy","bactriostatic","bioenergetics","biohacking","card","cellular stress","clear","comparison","comparison discussions","copper peptides","customer","dac","european","peptides","Research","Laboratory","Compounds","Example Lab"],"services":["Research Peptides & Laboratory Compounds Example Lab","Shop","Product Variations & Concentrations","Kisspeptin","Retatrutide","MOTS-C","CJC-1295 No DAC + IPA","BPC-157","GHK-CU","Bpc-157","CJC-1295","Cjc-1295","Ghk-Cu","Mots-C"],"audiences":["Research-oriented readers","Comparison and sourcing visitors"],"constraints":["Research and laboratory use framing only","No human consumption, dosing, treatment, clinical, or veterinary use","No medical claims"],"disclaimers":["For research use only. Not intended for human consumption, therapeutic, or diagnostic use."],"existing_page_titles":[],"competitor_domains":[],"competitor_gap_topics":[],"suggested_themes":["reconstitution","storage","handling","stability","concentration","lab calculations","comparison articles","FAQ and guide articles"]}

Output contract:
Return strict JSON only: {"headlines":["Headline one","Headline two"]}
Headlines only — no explanations, rationales, or extra keys.

Safety rules:
- Never generate article body text.
- Never include medical or dosing advice in headlines.
```

## Article headline recommendations

1. Exploring Kisspeptin: Applications and Storage Techniques for Research
2. Retatrutide vs. CJC-1295: A Comparative Analysis for Laboratory Use
3. Understanding MOTS-C: Stability and Handling Guidelines
4. BPC-157: Best Practices for Reconstitution and Storage in Research
5. GHK-CU: A Comprehensive Guide to Handling and Stability
6. CJC-1295 No DAC + IPA: Key Considerations for Laboratory Handling
7. Using Bactiostatic Water: Essential Tips for Research Applications
8. Kisspeptin and Aging Research: Insights and Storage Recommendations
9. Retatrutide: A Researcher's Guide to Concentration and Stability
10. MOTS-C: Handling and Storage Best Practices for Lab Environments
11. BPC-157 vs. GHK-CU: Comparing Stability and Handling Techniques
12. CJC-1295: Reconstitution Methods for Optimal Laboratory Use
13. Bactiostatic Water: Importance in Peptide Research and Storage
14. Kisspeptin: Frequently Asked Questions for Researchers
15. Retatrutide: Key Handling Guidelines for Laboratory Applications
16. MOTS-C: Understanding Concentration and Stability for Research
17. BPC-157: Comparison with Other Peptides in Research Applications
18. GHK-CU: Storage Solutions for Optimal Research Outcomes
19. CJC-1295 No DAC + IPA: Handling Techniques for Laboratory Settings
20. Bactiostatic Water: Essential for Peptide Reconstitution
21. Kisspeptin: Research Applications and Storage Best Practices
22. Retatrutide: Stability Considerations for Research Use
23. MOTS-C: Handling and Storage FAQs for Researchers
24. BPC-157 vs. CJC-1295: A Comparative Guide for Laboratory Use
25. GHK-CU: Reconstitution Techniques for Research Applications
26. CJC-1295: Handling and Stability Best Practices in the Lab
