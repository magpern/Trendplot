# Cleanup Phase 2 — execution plan

Destructive cleanup: single product analyze path (AI ideation). No legacy steps, packages, env vars, or DB tables retained.

## Batches

| Batch | Work | Status |
|-------|------|--------|
| 0 | DB backup + `legacy_table_counts.json` | Done |
| 1 | Architecture docs (this folder) | Done |
| 2 | Single analyze flow; product autopilot; strip opportunity engine from website analysis | Done |
| 3 | Delete legacy packages; `app/catalog/filters.py`; 410 legacy API routes | Done |
| 4 | `config.py`, `.env.example`, `.env` prune; merge ideation flags | Done |
| 5 | Alembic `0016` drops; trim `Repositories` wiring | Done (models may retain Table defs for history) |
| 6 | Test suite + manual analyze smoke test | Run `pytest tests/` |

## Product path

```text
workspace_setup → sitemap_discovery → website_crawl → website_analysis
→ niche_intelligence → ai_opportunity_ideation → opportunity_ranking
→ content_calendar → draft_generation → wordpress_upload
```

## Rollback

Git revert per batch; DB restore from Batch 0 backup if migration 0016 was applied.

## Related docs

- [CONFIG_CLEANUP_PLAN.md](CONFIG_CLEANUP_PLAN.md)  
- [DB_CLEANUP_PLAN.md](DB_CLEANUP_PLAN.md)  
- [UI_CLEANUP_PLAN.md](UI_CLEANUP_PLAN.md)  
- [AI_IDEATION_ONLY_USED_PATH.md](AI_IDEATION_ONLY_USED_PATH.md)  
- [CODE_CLEANUP_PLAN.md](CODE_CLEANUP_PLAN.md)  
