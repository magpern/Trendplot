# DB and config cleanup

**Phase 2 policy:** `REMOVE` means delete code, env, and tables — not `OPTIONAL` or hide.

- **Database:** [DB_CLEANUP_PLAN.md](DB_CLEANUP_PLAN.md) — migration `0016_drop_legacy_pipeline_tables.py`
- **Environment:** [CONFIG_CLEANUP_PLAN.md](CONFIG_CLEANUP_PLAN.md) — `.env.example` four sections (core, OpenAI, crawl/ideation, WordPress)

Historical Alembic revisions `0001`–`0015` remain in repo; only `0016+` performs drops. Downgrade is backup restore, not empty recreate.
