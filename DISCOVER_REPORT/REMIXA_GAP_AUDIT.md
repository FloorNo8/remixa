# Remixa Gap Audit — 7-Task Remediation Plan vs. Current Repo

**Date:** 2026-06-23
**Auditor:** Claude Code (read-only re-audit; **no code, migration, auth, royalty, payout, Stripe, or deploy changes made**)
**Source plan audited:** `CLAUDE_CODE_INTEGRATION_PROMPT.md` — 7 `## Task N` blocks (from: CLAUDE_CODE_INTEGRATION_PROMPT.md). A second copy with the same 7-block structure also exists at `.bob/CLAUDE_CODE_PROMPT.md` (from: .bob/CLAUDE_CODE_PROMPT.md); both counts confirmed via `grep -cE '^## Task [0-9]' = 7`.
**Repo HEAD:** `ead934a` (branch `main`; advanced from `2e501f2` mid-audit — `ead934a` is **docs-only**, rewriting the integration prompt to "ALL mocked features MUST be implemented, no Option B"; **no code changed**, so all code findings below stand). The audited plan is now the 921-line "no shortcuts" version; Task 7 was expanded to 7.1–7.6 and the "remove mocked features" option was deleted.

## Why this audit exists
The 7-task plan and `.bob/HANDOFF.md` are **stale bob artifacts**. `HANDOFF.md` is dated 2026-06-20 (commit `b78e203`) and asserts "production-ready, enterprise-grade… 26 tests passing… 40+ endpoints operational… Production deployed." Both predate the FN8-689 Clerk-auth work (`backend/clerk_auth.py`, Jun 22) — so the plan's **"START HERE: Task 1" is already complete**, and the test/endpoint counts are overselling, not ground truth. This audit re-derives true status per task from code.

---

## Summary table

| # | Task (per plan) | Status | Risk | One-line evidence |
|---|---|---|---|---|
| 1 | Real Clerk JWT auth | ✅ **DONE** | prod | `clerk_auth.py:252` RS256 `get_current_user`; commit `53970e7` (FN8-689); mig `006` |
| 2 | Mount `api_v2`/`api_advanced`/`api_c2pa` | ⚠️ **DESIGN-DECISION** | prod + money | `main.py:130` mounts only `admin_router`; AGENTS.md calls the rest deliberate dead code |
| 3 | Fix payout column mismatch | ✅ **DONE (dormant)** | money | `api_v2.py:883,901,936` reads balance from append-only ledger (FN8-692) — but router unmounted |
| 4 | Idempotency (stable IDs) | 🟡 **PARTIAL** | money | mig `007_idempotency_hardening.sql` exists but **not** in auto-apply list; lives in unmounted `api_v2` |
| 5 | Wire cron scheduler | ✅ **DONE** | prod | `scripts/cron_runner.py` scheduled via `backend/fly.toml:21` `cron=…` + `:27` `processes=['web','cron']`; 7 tests |
| 6 | Fix tests (65 passing, ≥70% cov) | ❓ **UNVERIFIED** | safe | ~89 `def test_` across 13 files (doc's "65"/"26" both stale); couldn't run — deps not installed |
| 7 | Implement/remove mocked features | ❌ **OPEN** | money + core | MusicGen/C2PA/NFT still mocked: `main.py:395-401`, `requirements.txt:30-32`, `nft_minter.py:325-326` |

Legend — **DONE**: implemented & verifiable. **DORMANT**: implemented but not served (router unmounted). **DESIGN-DECISION**: not a bug; a scope choice AGENTS.md made deliberately. **PARTIAL**: artifact exists, a wiring/apply gap remains. **OBSOLETE**: plan step no longer applies. **UNVERIFIED**: needs a live run this read-only audit didn't do.

---

## Per-task detail

### Task 1 — Real Clerk JWT auth — ✅ DONE
- **Evidence:** `backend/clerk_auth.py:252` `async def get_current_user(...)` does real RS256 verification (per AGENTS.md, fails closed → 401/503). Landed in commit `53970e7` "feat(auth): real Clerk JWT verification, replace mock get_current_user (FN8-689)". File dated Jun 22 17:28 — **after** the HANDOFF (Jun 20). Tests: `tests/test_clerk_auth.py` (7), `tests/test_auth_integration.py` (5). Schema: `migrations/006_clerk_auth.sql`.
- **Caveat (see Cross-cutting A):** `006_clerk_auth.sql` is **not** in `apply_migrations.py`'s hardcoded list → its schema may not be applied on a fresh deploy without a manual `psql -f`.
- **Verdict:** Plan's "START HERE" step is obsolete. Code-complete.

### Task 2 — Mount the unmounted routers — ⚠️ DESIGN-DECISION (not a plain fix)
- **Evidence (direct, repo-wide):** `grep -rn "include_router" backend/` returns exactly three hits — `main.py:130` (`admin_router`), and `api_advanced.py:9` / `api_c2pa.py:14`, both of which sit **inside registration helper functions** that `main.py` never imports or calls (`grep` for `import api_advanced|import api_c2pa` in `main.py` → no hit). `api_v2.py` has **zero** `include_router` anywhere. So `api_v2` / `api_advanced` / `api_c2pa` are all genuinely unmounted — confirmed by code, not only by AGENTS.md (which independently documents it: *"NOT mounted — dead code"*).
- **Why it's not a checkbox:** Mounting `api_advanced` exposes mocked blockchain/Lightning endpoints; mounting `api_c2pa` exposes C2PA whose embedding is still a TODO (Task 7). Mounting is a **product-scope decision**, and it's entangled with Tasks 3/4 (the real money logic lives in `api_v2`).
- **Verdict:** Needs a deliberate go/no-go, not an autonomous edit.

### Task 3 — Payout column mismatch — ✅ DONE in code, but DORMANT
- **Evidence:** `api_v2.py:841` comment: *"NOT the stale `users.pending_payout` column that `distribute_remix_royalties_v2` never…"*; `:883` `pending_payout=float(ledger_totals['current_balance'])`; `:901` and `:936` debit the **append-only ledger** instead of mutating `users.pending_payout`. Cites **FN8-692**. This is exactly the "read withdrawable balance from the ledger, not the stale column" fix the plan wanted.
- **Catch:** It lives in `api_v2.py`, which **is not mounted** (Task 2). So the corrected behaviour is **not served** by the live app. Meanwhile `admin_api.py:84-111` still surfaces a `pending_payouts` aggregate.
- **Verdict:** Fix is real but dormant until Task 2 is resolved. **Do not** re-implement.

### Task 4 — Idempotency with stable IDs — 🟡 PARTIAL
- **Evidence:** `migrations/007_idempotency_hardening.sql` exists; `migrations/004_royalty_hardening.sql` and `api_v2.py` both reference idempotency keys.
- **Gaps:** (a) `007` is **not** in `apply_migrations.py`'s auto-apply list → won't deploy without manual apply (Cross-cutting A); (b) the enforcing code path is in the unmounted `api_v2`.
- **Verdict:** Schema + logic drafted; deploy-wiring and router-mounting gaps remain.

### Task 5 — Wire cron scheduler — ✅ DONE
- **Evidence:** `scripts/cron_runner.py` exists alongside `process_payouts.py`, `update_exchange_rates.py`, `refresh_balances.py`, `update_leaderboards.py`, `daily_challenge.py`; `tests/test_cron_runner.py` (7 tests). **Scheduling is wired in deploy config:** `backend/fly.toml:21` `cron = 'python -m scripts.cron_runner'` and `:27` `processes = ['web', 'cron']` — Fly runs `cron_runner` as a dedicated `cron` process. (`main.py` itself has no in-process scheduler, by design — scheduling is a separate Fly process.)
- **Verdict:** Runner, tests, and deploy-config scheduling all present. Done. (Runtime liveness on the live machine is a deploy-health check, not a code gap.)

### Task 6 — Fix all test failures (65 passing, ≥70% cov) — ❓ UNVERIFIED
- **Evidence:** 13 test files, **~89** `def test_` functions total (plan said "65"; HANDOFF said "26" — both stale). `pytest.ini` enforces `--cov-fail-under=70`, `--strict-markers`, and markers `requires_db` / `requires_redis` / `requires_stripe`.
- **Could not run here:** `python -m pytest --collect-only` fails at `tests/conftest.py:9 import redis` → `ModuleNotFoundError`. Dependencies aren't installed in this environment; a real run needs `pip install -r requirements.txt` + live DB/Redis/Stripe-test. **No pass/fail is claimed.**
- **Verdict:** Requires a dedicated `pytest` run in a provisioned env — out of scope for this read-only audit. The "65 tests" target is itself obsolete.

### Task 7 — Implement or remove mocked features — ❌ OPEN (still mocked)
- **MusicGen (core product):** `main.py:395-396` `# TODO: Call MusicGen-Stem inference / For now, return mock response`; `:400` returns fake `https://cdn.eu-sound-lab.com/{id}.mp3`. The **live** `/api/v1/generate` (`main.py:368`) is the mock.
- **C2PA:** `requirements.txt:30-32` `c2pa-python` commented out ("Temporarily disabled due to Rust build issues on Fly.io"); `c2pa_embedder.py:232` `# TODO: Embed manifest in uuid box`.
- **Blockchain/NFT:** `nft_minter.py:325-326` `raise NotImplementedError("Arweave upload not yet implemented")`.
- **Also TODO:** TikTok upload (`main.py:474`), provenance logging (`:898`), GDPR export (`:903`), soft delete (`:908`).
- **Verdict:** Unchanged from the plan's premise. This is the largest real gap, spanning the core generation product **and** money-adjacent NFT/royalty code.

---

## Cross-cutting findings (not in the 7-task framing, but decisive)

**A. Migration auto-apply gap (highest-leverage).** `backend/apply_migrations.py:38-40` hardcodes **only** `database.sql`, `002`, `004`. Orphaned migration files that exist but are **not** auto-applied: `003`, `005`, `006_clerk_auth`, `007_idempotency_hardening`, `008_ledger_immutability`, `009`, `010`. So Tasks 1/4/8's *schema* support won't reach a fresh DB on deploy without manual `psql -f` + ratification (exactly the AGENTS.md gotcha). The plan's referenced `migrations/011_sync_pending_payout.sql` **does not exist** (highest on disk is `010`).

**B. The unmounted-router paradox — DB layer ≠ API layer (be precise).** Don't say "all money logic is dark" — split it:
- **DB-constraint layer = LIVE.** Migration `004_royalty_hardening.sql` **is** in `apply_migrations.py`'s auto-apply list, so its royalty constraints deploy and hold at the database.
- **Payout/withdraw API + later migrations = DORMANT / UNAPPLIED.** The FN8-692 ledger-payout and withdrawal *endpoints* live in `api_v2.py`, which is **unmounted** (Task 2) → not served. The idempotency (`007`) and ledger-immutability (`008`) migrations exist but are **not** in the auto-apply list → not deployed (Cross-cutting A).
- **Live HTTP surface** is `main.py`'s **v1** endpoints (generate/VAT/TikTok/GDPR/c2pa-verify/provenance), where generation is mocked (`main.py:400`).

Accurate one-liner: *core royalty constraints are live at the DB (mig 004); the payout/withdraw API surface and migs 007/008 are dormant/unapplied; the served generate endpoint is a mock.*

**C. Document provenance.** `HANDOFF.md` (`b78e203`, Jun 20) and the 7-task prompt both predate FN8-689. Their counts ("26"/"65" tests, "40+ endpoints operational", "Production deployed at eu-sound-lab.fly.dev") are bob overselling; treat them as historical narrative, not status.

---

## Recommended next actions (no work done yet — awaiting direction)

1. **Decide Task 2 first** — it gates Tasks 3 & 4. Either (a) mount `api_v2` (lights up the real payout/idempotency logic; **money-live**, needs verify pass), or (b) keep it dead and migrate the FN8-692 logic into the mounted surface. This is a Stefan/role-cpo call, not an autonomous edit.
2. **Reconcile migrations** — see `backend/migrations/APPLY_ORDER.md` (added 2026-06-24). Correction to this audit: do **NOT** auto-add `006`/`007`/`008`/`010` to `apply_migrations.py` — each file's header mandates **manual apply + ratification (FN8-701)** (006 is a "Type-1 schema change on a money-system DB"). Apply the `005→…→010` chain manually + ratified; the real fix is a tracked migration-ledger runner (proposal in APPLY_ORDER.md). Note: mounting `api_v2` depends on `010` being applied first.
3. **Task 7 scope split** — explicitly choose *implement* vs *remove* per feature (MusicGen ≠ NFT ≠ C2PA). MusicGen mock is the core-product blocker; NFT/blockchain are money-risk and may be cut.
4. **Task 6** — run `pytest` in a provisioned env (deps + DB/Redis/Stripe-test) to get a true pass/coverage number; the "65" target is obsolete.
5. **Tasks 1 & 3** — mark **complete** in any tracker; do not re-do.
