# Mounting `api_v2` — Scoping & STOP Findings

**Date:** 2026-06-24 · **Branch:** `floorno8/remixa-impl-mocked-features`
**Status:** SCOPE-ONLY. No router was wired; `main.py` is unchanged for v2. Mounting is gated on
the blockers below + a verify pass + Stefan's ratification (money + auth surface).

## TL;DR — do not mount as-is
`api_v2.py` is a module of ~12 `@handle_errors`-decorated async functions with **no `APIRouter`,
no route decorators, no paths**, never imported by `main.py`. Two independent blockers make a naïve
mount unsafe:

1. **🔴 AUTH SPOOF (critical).** The handlers take identity as **plain scalar parameters** —
   `user_id: str`, `subscription_tier: str`, `reporter_id: str` — **not** `Depends(get_current_user)`.
   Mounted directly, FastAPI binds `user_id` as a **caller-supplied query parameter**. Result:
   - `request_payout(user_id)` → **anyone can request a payout for any user_id**.
   - `get_earnings(user_id)` → **anyone can read any user's balance**.
   - `create_remix(..., user_id, subscription_tier)` → **spoof identity + tier, triggering royalty
     distribution as another user**.
   These MUST be refactored to derive identity from the verified token before they can be routes.
2. **🔴 MIGRATION DEP.** `010_matview_refresh_out_of_band` (money-critical, manual) must be applied
   first — its header: without it "the moment FN8-691 mounts the remix router every remix would error."
   See `backend/migrations/APPLY_ORDER.md`.

## Per-handler scoping

| Handler (`api_v2.py:line`) | Method | Proposed path | Identity bug | Risk |
|---|---|---|---|---|
| `get_explore_feed` (303) | GET | `/api/v2/explore` | — (db only) | safe |
| `get_generation_detail` (411) | GET | `/api/v2/generations/{id}` | — | safe |
| `get_leaderboard` (982) | GET | `/api/v2/leaderboard` | — | safe |
| `create_remix` (464) | POST | `/api/v2/generations/{id}/remix` | `user_id`,`subscription_tier` plain | **money** (royalty distribution) |
| `get_earnings` (818) | GET | `/api/v2/earnings` | `user_id` plain | **money** (balance read) |
| `request_payout` (890) | POST | `/api/v2/payout` | `user_id` plain | **money — CRITICAL** (initiates payout) |
| `get_streak_badge` (958) | GET | `/api/v2/streak` | `user_id` plain | info-leak |
| `create_report` (1021) | POST | `/api/v2/reports` | `reporter_id` plain | low |
| `generate_invite` (1062) | POST | `/api/v2/invites` | `user_id` plain | low |
| `redeem_invite` (1113) | POST | `/api/v2/invites/redeem` | `user_id` plain | low |
| `get_waitlist_status` (1167) | GET | `/api/v2/waitlist` | `user_id` plain | info-leak |
| `generate_remix_audio` (758) | — | (background task, not a route) | — | — |

## Required refactor BEFORE any mount (pattern, not yet applied)
Each handler must derive identity from the token instead of trusting a parameter:

```python
# BEFORE (unsafe as a route — user_id is a caller-supplied query param):
async def request_payout(user_id: str, db = Depends(get_db), request_id: str = None) -> dict:

# AFTER (identity from the verified Clerk token):
@router.post("/payout")
async def request_payout(user = Depends(get_current_user), db = Depends(get_db)) -> dict:
    user_id = user["user_id"]
    ...
```

`request_id` (used only for logging) should move to a dependency or be dropped from the signature.

## Mount checklist (all required; none done here)
- [ ] Refactor all identity params → `Depends(get_current_user)` (+ tier from the user row, not the caller).
- [ ] Apply the `005→…→010` migration chain (ratified) — esp. `010` (else remix errors).
- [ ] Add an `APIRouter(prefix="/api/v2")`, attach handlers, define `response_model`s.
- [ ] Verify pass on the money routes (`create_remix`, `get_earnings`, `request_payout`) — they have
      never been served or integration-tested.
- [ ] Stefan ratification (money + auth surface) before `include_router` in `main.py`.

A draft router is intentionally **not** committed: wiring these signatures verbatim would ship the
auth-spoof above. The refactor is the prerequisite, not the router.
