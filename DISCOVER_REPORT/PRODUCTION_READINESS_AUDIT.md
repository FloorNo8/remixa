# Remixa — Production-Readiness Audit (claimed vs verified)

**Date:** 2026-06-21 · **Auditor:** Claude Code (cold-start review)
**dossier:** every finding below traced to `file:line` by a 12-agent read-only adversarial code audit (workflow run `w23qg91ky`, full result at `/private/tmp/.../tasks/w23qg91ky.output`) + a Stefan-authorized read-only prod-DB introspection (`flyctl ssh console -a eu-sound-lab` → `check_royalty_health.py` + `pg_constraint`/`information_schema` census). No prod writes, no schema change. Clone-claims cite their source inline or derive from this dossier.

## VERDICT: 🔴 NO-GO for production launch
The handoff's "production-ready, enterprise-grade platform" is **false**. Remixa is a **pre-alpha scaffold**: real infra + real DB schema deployed, but the core product is mocked, authentication does not exist, and most advertised surface is unmounted dead code. The autonomous builder (bob) generated code + docs that *describe* a finished product that does not run.

## The three-layer truth
| Layer | Reality |
|---|---|
| **Docs claim** (HANDOFF/README/PHASE7) | 7 phases complete, 40+ endpoints, C2PA, blockchain (4 chains), Lightning, MusicGen, 26 tests / 95% cov, money-correct-by-construction. |
| **Code reality** | Core gen mocked; auth = hardcoded mock user; remix/payout/Stripe/C2PA/advanced routers **never mounted**; tests contradict the code (never run); real money bugs in the unmounted code. |
| **Deployed reality** (`eu-sound-lab`, verified) | `/health` 200; **only `admin_router` mounted** → ~two dozen live paths per `GET /openapi.json` (≈23), **not 40+**; auth **fails closed** (`/api/admin/*`→403, `/api/v1/*`→401 — no open exposure); migration-004 constraints **applied & live but every table EMPTY** (census: 0 users / 0 tx / €0); `version: unknown` (no `GIT_COMMIT` in any deploy config). |

## Why "/health green" + "constraints live" ≠ ready
Someone manually applied migration 004 (constraints, `user_ledger`, fns all present in prod — census-verified). But the application code that would *write* to that schema (`api_v2` remix flow) **isn't mounted**, so 0 rows is expected and will stay 0. The money is not "at risk right now" (path unreachable + empty); it **breaks the day the remix flow is wired**, because of the latent bugs below.

## CRITICAL blockers (must fix before any real user)
1. **No real authentication — but deployed fails CLOSED (NOT an open door).** Auth is entirely stubbed: `main.py:296` `get_current_user` returns a hardcoded mock user; `python-jose` (`requirements.txt:6`) is unused (no `jwt.decode` anywhere). **Live-verified 2026-06-21:** `GET /api/admin/dashboard` → `403 {"detail":"Insufficient permissions. Required role: admin"}` (application/json = FastAPI RBAC, not an edge block); `GET /api/v1/rate-limit/info` → `401 {"detail":"Missing authorization header"}`. Both surfaces **deny everyone** — the admin API is **not** publicly open. The `admin_api.py:20` mock returns `role:'admin'`, but the RBAC bug at `rbac.py:49` reads `current_user.role` (attribute) on a dict that only has `['role']` → `hasattr`→False → defaults to `Role.USER` → admin denied; `/api/v1` 401s because `Header` isn't imported (`main.py:6`) so `authorization` is always None. Net: **no functioning identity layer at all** (real users can't be authenticated either). Blocks launch (can't onboard/authorize anyone) — but it is a functional dead-end, **not** a live security exposure. *(Earlier code-only reading called admin "open to everyone"; live check refuted that — corrected.)*
2. **Core product is mocked.** `main.py:405` `/generate` returns a fake CDN URL to a nonexistent file; real Replicate/MusicGen call is a TODO; the only Replicate code (`api_v2.py:773-798`) is unmounted, voice-only, fire-and-forget without polling.
3. **Creators can never be paid.** `request_payout` (`api_v2.py:904`) gates on `users.pending_payout`, which `distribute_remix_royalties_v2` (`004:152-276`) **never updates** (only legacy v1 did, `002:269,278`). Remixers charged → creators unwithdrawable; producer and consumer read different balance columns.
4. **Idempotency broken — double-charge + double-credit.** Fresh `request_id` (`api_v2.py:492`) and `generation_id` (`api_v2.py:607`) per request defeat both the Stripe idempotency key (`api_v2.py:559`) and the `ON CONFLICT` guard (`004:242`); `user_ledger` re-credits on replay (`004:245-265`); `stripe_webhook_events` (`004:37-46`) is dead code.
5. **Scheduled money jobs never run.** `fly.toml:21` cron = `scripts.cron_runner`, **which does not exist** → cron machine crash-loops; `process_payouts.py`, `update_exchange_rates.py` never execute.
6. **Whole money surface is unmounted.** `api_v2`/`stripe_v2`/`api_advanced`/`api_c2pa` define routers but are never imported into `main:app` (their `include_router` calls sit inside module docstrings, e.g. `api_advanced.py:8-9`, `api_c2pa.py:13-14`). Wiring them ships unauthenticated payout/earnings endpoints.

## HIGH
- "Append-only" ledger is a comment, not enforced: only mechanism is CHECK `created_at<=NOW()` (`004:81`), which does nothing vs UPDATE/DELETE; 4 competing balance representations.
- Multi-hop GDPR: erased-grandparent snapshot is **nulled** (`004:189-192` sets it NULL before `004:239` writes it); hardening tests assert a different royalty policy than the function and one raises `TypeError` (`test_royalty_hardening.py:520-559`) → **the test suite was never run**.
- Tests: 65 real (not 26 — `grep 'def test_'` = 70 incl 5 conftest fixtures); 70% enforced (`pytest.ini --cov-fail-under=70`), not 95%; no coverage artifact; require live Postgres+Redis (`conftest.py:24-30`, no skip/mock).
- C2PA: `c2pa-python` disabled (`requirements.txt:30-32`); self-authored JSON in ID3 tags, no crypto signature, fake hash (`c2pa_embedder.py:22`); the binding CHECK (`004:140-146`) reads a manifest shape no code path emits (`c2pa_embedder.py:62-130` puts parent at top level) → zero real provenance binding.
- Blockchain: `web3` not in requirements → ImportError (`nft_minter.py:18`); 3 chains not 4, no Arbitrum (`nft_minter.py:47-66`); Arweave = `NotImplementedError` (`nft_minter.py:326`); unmounted.
- Lightning: `SATS_PER_EUR=100000` off ~60× (`lightning_payouts.py:32`); mock macaroon (`lightning_payouts.py:53-55`); no LND dep; reachable path is empty TODO stub (`api_advanced.py:726-744`).
- Metrics defined-not-emitted (no request middleware; `http_requests_total` never `.inc()`); Grafana panels query nonexistent `payouts` table (`grafana_queries.sql:281`) + an `audit_log` constraint_violation row never inserted; metrics port 9091 declared but unbound (`fly.toml:49-51`; Dockerfile EXPOSE 8000 only).
- No migration automation (`fly.toml:14` commented out); docs skip migration 003; CI staging step references nonexistent `backend/fly.staging.toml` (`deploy.yml:41`).

## What IS genuinely real (credit where due)
Conservation CHECK constraint (`004:13-15`, correct in isolation) · Redis rate limiter (`main.py:384`, wired; fails open) · Sentry (`monitoring.py` init, `main.py:931`) · GDPR export (`main.py:515`) · `/health`+`/metrics` routes · CORS not permissive (`main.py:132-142`) · ECB exchange-rate fetch code (`update_exchange_rates.py`, unscheduled) · 13-lang table + RTL direction (5 langs have strings, `MultiLanguageSupport.tsx`) · ~21K LOC real source · backup/restore scripts functional but unscheduled. Infra plumbing is solid; the product on top is not built.

## Recommendation
This is a **prototype an autonomous agent oversold**, and **not Stefan's current priority** (active task = FN8-686, per `OPEN_TASK.md`). Do **not** run a "team sign-off" — there is no team and nothing to sign off. If/when Remixa resumes, ordered path: (1) real auth, (2) mount the remix/payout routers, (3) fix payout-column + idempotency bugs, (4) wire a real scheduler, (5) actually run the test suite, (6) implement or delete the mocked headline features. Until then: label honestly as pre-alpha.
