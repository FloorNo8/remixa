# AGENTS.md — Remixa (EU TikTok Sound Lab)

Guidance for AI coding agents (Linear Coding Sessions, Claude Code, Codex, Cursor) working in this repo.
This is the **canonical** agent guidance. `CLAUDE.md` points here via `@AGENTS.md`; `skills.md` is the filename Linear's Coding-sessions docs read.

## What this is
Remixa = "EU TikTok Sound Lab": AI music/sound generation for creators. **Monorepo, two stacks:**
- `backend/` — FastAPI (Python), Pydantic **v2**, `psycopg2` (Postgres), `structlog`, Stripe, Clerk-verified auth.
- `frontend/` — Next.js **14 App Router**, `@clerk/nextjs` v5, Stripe, Tailwind, **Zustand** (state), **SWR** (server fetching).

Compliance-heavy: GDPR / EU AI Act / VAT-MOSS, Stripe payments, creator payouts, royalty logic, C2PA provenance. Pre-alpha — treat prod as fragile.

## Setup & run
- Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload`  (prod runs `uvicorn main:app`).
- Frontend: `cd frontend && npm install && npm run dev`.

## Build / test / lint — RUN THESE before finishing
- **Backend tests:** `cd backend && pytest` — the **`--cov-fail-under=70` coverage gate must pass** (configured in `backend/pytest.ini`). Service-dependent tests use markers `requires_db` / `requires_redis` / `requires_stripe`.
- **Frontend:** `cd frontend && npm run lint && npm run type-check && npm run build`. (There is **no** frontend unit-test script.)

## Architecture orientation
- **Routing:** `backend/main.py` is the app and mounts **only `admin_router`**. `api_v2.py` / `api_advanced.py` / `api_c2pa.py` define routers that are **NOT mounted — dead code**. To add an endpoint you must `app.include_router(...)` it in `main.py` explicitly.
- **Auth:** real Clerk JWT verification in `backend/clerk_auth.py` — `get_current_user` does RS256 verification against `CLERK_JWKS_URL` / `CLERK_ISSUER` (fails closed → 401/503). RBAC in `backend/rbac.py` (`require_role`, dict-or-object safe). The frontend sends the Clerk token via `getToken()` → `Authorization: Bearer`.
- **DB:** `psycopg2.connect(os.getenv("DATABASE_URL"))`; schema in `backend/database.sql` + numbered `backend/migrations/NNN_*.sql`.
- **Payments/payouts:** Stripe (`stripe_v2.py`); creator payouts + royalties run as cron scripts in `backend/scripts/`.

## Gotchas / what NOT to do (highest-leverage — read this)
- **Migrations are a manual, hardcoded list.** `backend/apply_migrations.py` applies ONLY `database.sql`, `002`, `004`. A new `NNN_*.sql` is **NOT auto-applied** — apply it manually (`psql "$DATABASE_URL" -f migrations/NNN_*.sql`) with ratification. Add the file AND document the manual apply; never assume it runs on deploy.
- **Don't lower or remove the 70% coverage gate** to make tests pass — add tests.
- **Frontend auth:** always use Clerk `getToken()`. **Do NOT use `frontend/lib/fetcher.ts`** — it reads a stale `localStorage('auth_token')`, not the Clerk token.
- **Don't add a second state library** — Zustand is the convention; SWR for server data.
- **Pydantic v2 idioms** in the backend (not v1).
- **Compliance / money code is high-risk:** touch GDPR, VAT-MOSS, royalty / smart-contract, or payout code only when the task explicitly asks. Use Stripe **test mode** keys.

## Security / secrets (non-negotiable)
- **Never read, print, log, or commit `.env` files or secret values** (Stripe / Clerk / Lightning keys, DB URLs, PII). Use the host's injected env vars.
- Don't bypass RBAC or rate limiters.

## PR / commit conventions
- Branch: **`floorno8/fn8-NNN-slug`** — this is the format Linear's native GitHub integration auto-links on (PR ↔ FN8-NNN issue + status automation).
- Reference the `FN8-NNN` issue in the branch/PR; let native Linear linking handle issue status.
