# DISCOVER — C: Catalog Pain

The "production-ready, enterprise-grade" frame in `.bob/HANDOFF.md` is the thing under audit. Below is the *real* pain — the claimed-vs-verified gaps — ranked by money/production risk.

| # | What hurts | Urgency | Blocking | Evidence |
|---|-----------|---------|----------|----------|
| 1 | **Money invariants may not be live in prod.** Migration 004 (5 constraints) auto-applies via nothing — `fly.toml` release_command commented out ("migration script not yet implemented"); CI says migrations are manual. Only manual `fly ssh`+psql applies them. | **CRITICAL** | Any honest go/no-go. If unapplied, the platform can pay out more than it collected. | `backend/fly.toml` `[deploy]`; `.github/workflows/deploy.yml` migration note; `.bob/NEXT_STEPS_PROMPT.md` (untracked plan to apply 004, incomplete) |
| 2 | **Deployed build is unidentifiable.** `/health` → `version: "unknown"`. Cannot tell which commit/schema is running in prod from outside. | **HIGH** | Trusting `/health` as proof of anything beyond "process is up + DB reachable". | `GET https://eu-sound-lab.fly.dev/health` (2026-06-21) |
| 3 | **Core endpoints are stubbed behind "production-ready".** `main.py:299 TODO: actual JWT validation`; `main.py:484 TODO: actual TikTok API`; `main.py:689 TODO: Replace with actual database query`; `frontend/app/admin/layout.tsx:9 TODO: implement auth check`. | **HIGH** | "All 7 phases complete / 40+ endpoints operational" claim. Auth stubs are a security hole. | grep TODO/FIXME (30 hits) |
| 4 | **C2PA is disabled, but C2PA-binding is one of the 5 advertised invariants.** `c2pa-python` commented out in `requirements.txt` ("temporarily disabled due to Rust build issues"). | **HIGH** | Invariant #5 (C2PA binding) and the README "C2PA credentials embedded" claim. | `backend/requirements.txt` tail; commit `92dff99 fix: disable c2pa-python` |
| 5 | **Test pass-rate is asserted, not shown.** HANDOFF claims "26 tests passing / 95% coverage"; NEXT_STEPS claims "10/10 hardening tests." No run output in repo. Tests may require live DB/Redis. | **MEDIUM** | "Testing complete" success criterion. | `backend/tests/` (8 files); no captured run artifact |
| 6 | **Documentation theater / sprawl.** ~14 markdown docs incl. HANDOFF coordinating a non-existent 5-person team + 60-min meeting agenda + Day1/2/3 timeline. Last 3 commits are all docs. | **MEDIUM** | Operator attention; signal-to-noise. Adding another doc makes it worse. | `git log` (docs/ops commits); HANDOFF.md §Team |
| 7 | **Staleness vs current priority.** Active FN8 task is FN8-686 (SDD pipeline), not Remixa. Remixa is a bob side-build. | **LOW (context)** | Knowing whether this review is worth Stefan's cycles now. | `OPEN_TASK.md`, `PLAN_OF_RECORD.md` |

## The one question that collapses the uncertainty
Are `check_conservation_invariant`, `unique_remix_payment`, `check_c2pa_parent_consistency`, the `user_ledger` table, and `distribute_remix_royalties_v2()` **present in the production DB right now?** Everything else is secondary. Resolve via `flyctl ssh console -a eu-sound-lab` → psql `pg_constraint` / `information_schema` introspection (read-only).
