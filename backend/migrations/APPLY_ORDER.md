# Remixa Migrations — Apply Order & Reconciliation

**Date:** 2026-06-24 · **Branch:** `floorno8/remixa-impl-mocked-features`
**Decision:** `apply_migrations.py` was **NOT modified** to auto-apply 006/007/008/010. Reason below.

## The problem
`apply_migrations.py:37-41` is a **blind re-execute runner** — it has no `applied_migrations`
tracking table; it just `cur.execute()`s a hardcoded list on every invocation:

```
database.sql  →  002_v2_social_features  →  004_royalty_hardening
```

Six migrations exist on disk but are **not** in that list:
`003`, `005`, `006`, `007`, `008`, `009`, `010` (highest on disk is `010`; the old plan's
`011_sync_pending_payout.sql` and `012_c2pa_manifest_structure.sql` were never created).

## Why NOT just add them to the runner
Every money/identity migration carries an explicit **manual-apply + ratification** directive
in its own header — auto-wiring them into a runner that re-executes on **every deploy** would
violate that handling and remove the ratification gate:

| Mig | Header directive (verbatim-sourced from the file) | Money/Type-1 |
|---|---|---|
| `006_clerk_auth` | "Type-1 schema change on a money-system DB — apply manually with Stefan's ratification (no auto-apply path exists; see FN8-701)" (`006:7-8`) | yes |
| `007_idempotency_hardening` | "Money-critical — apply manually with ratification (FN8-701)" (`007:2`) | yes |
| `008_ledger_immutability` | "Money-critical — apply manually with ratification (FN8-701)" (`008:2`) | yes |
| `010_matview_refresh_out_of_band` | "Money-critical — apply manually" (`010:2`) | yes |

(`003_performance_indexes` and `005_advanced_features` carry no such flag; `009` is
"Apply AFTER 008. Idempotent.") **All four money/Type-1 migrations are idempotent** (re-runnable:
`ADD COLUMN IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`, `DROP TRIGGER IF EXISTS … CREATE TRIGGER`),
so the block is *policy* (ratification), not a mechanical re-run hazard.

> This supersedes `DISCOVER_REPORT/REMIXA_GAP_AUDIT.md` Cross-cutting A, which suggested adding
> 006/007/008 to the runner. On reading each header, the correct action is manual apply — not auto-wire.

## Correct manual apply order (with ratification)
Already applied by the runner: `database.sql`, `002`, `004` (004 creates `user_balances_derived`
matview + `refresh_user_balances()` at `004:90,102`).

Then, **each gated on Stefan's ratification (FN8-701)**, in this order:

```
003_performance_indexes          # non-money, anytime (indexes only)
005_advanced_features            # before 006
006_clerk_auth                   # after 005 — adds users.clerk_user_id, users.role
007_idempotency_hardening        # after 006 — needs 004's refresh_user_balances() (present)
008_ledger_immutability          # after 007 — append-only triggers on user_ledger
009_drop_orphaned_payout_fn      # after 008 — idempotent
010_matview_refresh_out_of_band  # after 009 — redefines refresh_user_balances() out-of-band
```

Apply one at a time: `psql "$DATABASE_URL" -f migrations/006_clerk_auth.sql` (etc.), reviewing output.

## Cross-links (decisive)
- **Mounting `api_v2` (the remix router) REQUIRES `010` applied first.** `010`'s header: without the
  out-of-band refresh, "the moment FN8-691 mounts the remix router every remix would error" (the matview
  refresh runs inside the remix transaction). So the api_v2-mount work (see `API_V2_MOUNT_SCOPING.md`)
  is blocked on the 005→…→010 chain being applied + ratified.
- `clerk_auth.py` (landed, FN8-689) reads `users.clerk_user_id` / `users.role` from `006`. If `006`
  isn't applied on a given DB, auth queries fail — confirm `006` is applied wherever auth runs.

## Recommendation (the real fix — needs ratification, not autonomous)
Replace the blind runner with a **tracked migration ledger**:
- an `applied_migrations(filename, checksum, applied_at)` table,
- apply each pending file **once**, in lexical order, recording it,
- a `MANUAL_RATIFY` marker on money/Type-1 files so the runner **skips** them unless an explicit
  `--apply-ratified <file>` flag is passed (preserving the FN8-701 gate).

This is a Type-1 substrate change to the deploy path — drafted here as a proposal; do not wire it
into deploy without ratification.
