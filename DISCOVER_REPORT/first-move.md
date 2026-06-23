# DISCOVER — E: First Micro-Move

**Action (low-risk, reversible, high-signal):** Read-only introspection of the `eu-sound-lab` production DB (Stefan-authorized; ran the existing `backend/scripts/check_royalty_health.py` + a `pg_constraint`/`information_schema` object census via `flyctl ssh console`, all SELECTs + rollback). No writes, no schema change, no migration applied.

**Result:**
- All 6 royalty health checks PASS (constraints, conservation, idempotency, ledger drift, ledger integrity, orphaned snapshots).
- All 11 migration-004 objects PRESENT in prod: 3 constraints, `user_ledger` + `stripe_webhook_events` tables, `user_balances_derived` matview, `distribute_remix_royalties_v2` + `refresh_user_balances` functions, `platform_fee_explicit`/`*_snapshot` columns, `users.is_erased`.
- **All tables EMPTY:** 0 users, 0 generations, 0 license_transactions, 0 user_ledger, 0 stripe_webhook_events; sums €0.
- No migration-tracking table (no schema_migrations/alembic_version) → migration order/state untracked in DB.
- Container note: app venv is `/opt/venv/bin/python`; `apply_migrations.py` + `check_schema.py` exist in the deployed image (so a migration runner DOES exist — just not wired to `release_command`). Deployed build timestamp Jun 20 22:38.

**Learning signal / hypothesis resolution:**
- **H1 (constraints NOT in prod) → FALSE.** Migration 004 was manually applied.
- **H2 (applied but ungoverned) → CONFIRMED, with a sharper truth:** applied AND zero traffic. The platform is **deployed-but-pre-launch / empty**, not a live money system at risk.
- The presupposition that broke: "config says migrations never auto-apply → therefore constraints are missing." Reality: someone ran them manually (`apply_migrations.py`), config just doesn't reflect it. Lesson: config-state ≠ DB-state; verify the DB, not the deploy pipeline.
- Reframed verdict axis: money-correctness *machinery* = real ✅; "production-ready as a live business" = false (0 users, stubbed auth, disabled C2PA). The go/no-go is now a **pre-launch hardening** question, not a "money is leaking" emergency.
