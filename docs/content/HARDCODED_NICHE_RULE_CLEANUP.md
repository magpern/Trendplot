# Hardcoded niche rule cleanup

Implementation of [HARDCODED_NICHE_RULE_AUDIT.md](./HARDCODED_NICHE_RULE_AUDIT.md). Focused removal of Example Lab- and peptide-specific assumptions from global platform code while preserving generic compliance and safety behavior.

## What changed

### Brand and publisher defaults

| Before | After |
|--------|--------|
| `app/rules/compliance_rules.py` with `brand_name: "Example Lab"` | **Removed.** Replaced by `app/rules/compliance_rules.py` |
| `schema_jsonld.py` default publisher `"Example Lab"` | `default_publisher_name()` from workspace name, product name/URL host, or generic `"Publisher"` |
| Global sanity rules imported from brand module | Per-job `build_compliance_rules()` in `JobService._generation_compliance_context()` |

### Storage temperature handling

| Before | After |
|--------|--------|
| Platform whitelist for `-20°C` and `4–8°C` in brand rules + sanity bypass helpers | **Removed.** No global approved temperatures |
| Definitive storage/reconstitution blocked unless in configured claims | Unchanged pattern: only `approved_storage_claims` / `approved_handling_claims` from workspace or vertical profile allow specific wording |

### Catalog and SKU extraction

| Before | After |
|--------|--------|
| Hardcoded peptide SKUs (BPC-157, TB-500, GHK-CU, etc.) and Example Lab skip strings | Generic `_SKU_LIKE` regex and inventory/sitemap-driven catalog; spelling aliases only for common lab-supply typos (e.g. bacteriostatic water) |

### Peptide-specific behavior gating

| Area | Behavior |
|------|----------|
| `quality_checks.is_biomedical_article` | Generic `GENERIC_REGULATED_HINTS` always; `PEPTIDE_BIOMEDICAL_HINTS` only when `vertical_id == "peptides"` or vertical supplies `biomedical_keyword_hints` |
| `requires_ruo_disclaimer` | Honors `vertical_compliance.requires_ruo_framing` |
| `opportunities/verticals/peptides.py` | Peptide entities, expansion maps, compliance hints, `ideation_themes` |
| AI ideation brief | `GENERIC_SUGGESTED_THEMES` vs `PEPTIDE_SUGGESTED_THEMES` based on niche/vertical |
| Ideation YAML / top-up prompts | No fixed 25%/20% reconstitution mix; uses `suggested_themes` from brief |

### RUO disclaimer (single source of truth)

| Before | After |
|--------|--------|
| Duplicated `RUO_DISCLAIMER` literals in quality, redundancy, internal links | `Settings.biomedical_ruo_disclaimer` via `_resolve_required_disclaimer()` / `_resolve_disclaimer()` |
| Detection phrases like `"for research use only"` in pattern detectors | **Kept** (detection only, not copy) |

### Pipeline wiring (`jobs.py`)

- `_generation_compliance_context()` loads workspace compliance settings, vertical profile, publisher name, compliance rules, and biomedical flag.
- Sanity checker rules updated per generation pass.
- Redundancy cleanup, internal links, section expansion, and schema JSON-LD use workspace-aware publisher and shared disclaimer.

### Minor UX / copy

- `ui.py` tag placeholder made generic.
- `article_repair.py` safety FAQ wording made niche-agnostic.
- `analysis_digest.py` product path regex no longer treats `/peptide/` as a global product path marker.
- `README.md` points to `compliance_rules.py`.

## Moved to workspace configuration

Set under `workspace.settings.compliance` (JSON):

| Field | Purpose |
|-------|---------|
| `brand_name` | Brand string for rules context (optional; workspace name used when empty) |
| `approved_storage_claims` | Exact sentences allowed to mention specific storage temperatures |
| `approved_handling_claims` | Exact sentences allowed for reconstitution/handling specifics |
| `safe_storage_handling_fallback` | Override generic COA/label fallback paragraph |
| `rules` | Extra compliance rule strings merged into sanity rules |

Publisher name for schema: workspace `name`, else `product_name`, else host derived from `product_url`, else `"Publisher"`.

Environment: `BIOMEDICAL_RUO_DISCLAIMER` (see `Settings.biomedical_ruo_disclaimer`).

## Moved to vertical profiles

`app/opportunities/verticals/peptides.py` retains peptide-specific:

- `known_entities`, `entity_expansion_map`, `product_family_map`
- `compliance_profile`: `requires_ruo_framing`, `biomedical_keyword_hints`, `ideation_themes`
- Opportunity weights, image rules, audience examples

Other verticals should add their own profiles; generic code must not assume peptides.

## Remains global (unchanged intent)

- `FORBIDDEN_MEDICAL_PHRASES` and dosing/treatment safeguards
- Citation / reference verification expectations
- `ArticleSanityChecker` storage/reconstitution **pattern warnings** (source-dependent framing), without global temperature approval
- `DEFAULT_COMPLIANCE_RULES` generic rules and `SAFE_STORAGE_HANDLING_FALLBACK`
- Biomedical article detection framework (`is_biomedical_article`, `requires_ruo_disclaimer`)
- Semantic sanity, editorial repair, publish decision framework

## Migration considerations

1. **Example Lab / peptide workspaces** — Add `approved_storage_claims` and `approved_handling_claims` under workspace compliance if articles must repeat previously whitelisted temperature sentences verbatim. Without them, sanity review will flag definitive temperature/reconstitution wording and suggest the generic fallback.
2. **Rename** — Update any external docs or scripts referencing `compliance_rules.py` to `compliance_rules.py`.
3. **RUO text** — Customize once via `BIOMEDICAL_RUO_DISCLAIMER`; do not duplicate in code.
4. **Ideation** — Peptide sites still get reconstitution/storage themes via niche detection or `vertical_id: peptides` on workspace niche profile.

## Remaining intentional niche signals (not platform defaults)

- Peptide vertical profile and detection in `app/opportunities/verticals/`
- `PEPTIDE_BIOMEDICAL_HINTS` when vertical is `peptides`
- Validation/docs/scripts that mention Example Lab as **test fixtures** only
- `website_analysis.yaml` research-framing guidance for peptide/biomedical **when detected in analysis**, not as a global default publisher
- Config default string for `BIOMEDICAL_RUO_DISCLAIMER` (overridable per environment)

## Validation

Run:

```bash
pytest tests/ -q --tb=short
```

Confirm:

- No production import of `compliance_rules`
- No default publisher `"Example Lab"` in `app/`
- No `-20°C` / `4–8°C` global whitelist in `app/`
- RUO body text only from `Settings.biomedical_ruo_disclaimer` in production modules
