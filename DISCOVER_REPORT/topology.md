# DISCOVER — D: Detect Topology

**Repo:** `/Users/stefantalos/My Space/Fn8 - Projects/remixa`
**Cold-start session:** 2026-06-21
**Git:** 27 commits, branch `main`, remote `https://github.com/FloorNo8/remixa.git`, `gpgsign = false`, notes ref `refs/notes/bob`.

## Observed structure (actual paths, no inference)

```
backend/                 FastAPI (Python 3.11), 15,342 LOC Python
  main.py                Primary API surface (heavily TODO-stubbed)
  api_v2.py              Remix/royalty flow (Stripe → distribute_remix_royalties)
  api_advanced.py        Phase-7 advanced features
  c2pa_embedder.py       C2PA manifest embedding (lib c2pa-python DISABLED in requirements)
  nft_minter.py          NFT/EIP-2981 (TODO: Arweave upload)
  gdpr_tools.py          GDPR erasure/export
  monitoring.py          Health checks, Sentry, Prometheus
  rate_limiter.py        Redis-backed (lazy init)
  database.sql           Base schema
  migrations/
    002_v2_social_features.sql      distribute_remix_royalties() v1
    003_performance_indexes.sql
    004_royalty_hardening.sql       *** 5 money-correctness constraints (L5 corner) ***
    005_advanced_features.sql
  monitoring/grafana_queries.sql
  scripts/               process_payouts.py, daily_challenge.py, cron_runner (ref'd)
                         NOTE: scripts/migrate_db referenced by fly.toml but NOT IMPLEMENTED
  tests/                 8 test files incl. test_royalty_hardening.py,
                         test_gdpr_royalty_survival.py, test_remix_flow.py
  fly.toml               app='eu-sound-lab', region ams, Fly Postgres volume eu_sound_lab_data
  Dockerfile
frontend/                Next.js 14, Clerk auth, Stripe, wavesurfer, recharts (~7.7K TS/TSX)
  app/(protected)/, app/admin/   admin/layout.tsx:9 TODO: implement auth check
.github/workflows/       deploy.yml (Fly + Vercel; migrations MANUAL), fn8 observability
.bob/                    HANDOFF.md, NEXT_STEPS_PROMPT.md (untracked), notes/  — bob agent artifacts
backend/.bob/notes/      royalty-engine-assessment.md  (genuine Phase-0 gap analysis)
```

## Deploy targets
- **Backend:** Fly.io app `eu-sound-lab`, region `ams`, web=`uvicorn main:app`, cron process, `/health` + `/metrics`. **LIVE** (verified `/health` → 200, 2026-06-21).
- **Frontend:** Vercel (deploy.yml `vercel deploy --prod`).
- **DB:** Fly Postgres (volume-mounted), `DATABASE_URL` = Fly secret. NOT Neon → neon-db MCP cannot reach it; introspection requires `flyctl ssh console -a eu-sound-lab`.

## Migration application path (critical)
`fly.toml`: `release_command` **commented out** ("Disabled - migration script not yet implemented").
`deploy.yml`: "Database migrations are applied manually for safety (money-critical schema)."
→ **Nothing auto-applies migrations.** Migration 004 reaches prod only via a manual `fly ssh` + psql run.

## Build/health
- `version: "unknown"` returned by `/health` → deployed build is not git-SHA-stamped; cannot identify running commit from outside.
- Boot history is a firefighting trail (lazy imports, disabled slowapi/c2pa/release_command) to make the container start on Fly.
