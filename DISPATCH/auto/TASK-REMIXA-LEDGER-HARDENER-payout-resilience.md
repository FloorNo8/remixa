# TASK: REMIXA-LEDGER-HARDENER-payout-resilience

## Agent Role
* **Agent**: Ledger-Hardener (Frontier LLM / Database & Payments Specialist)
* **Status**: ASSIGNED
* **Dependencies**: Stripe, psycopg2, FastAPI

## Context & Objectives
To deploy Remixa safely to staging and production, our royalty ledger must be absolute and resilient. We need to handle database rollbacks atomically and ensure Stripe Connect failures are handled correctly without leaving the payout queue or payouts table in an inconsistent state.

Your task is to audit transaction scopes and implement Connect webhook handlers.

## Files to Modify
1. [stripe_v2.py](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/backend/stripe_v2.py)
2. [api_v2.py](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/backend/api_v2.py)
3. [cron_runner.py](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/backend/cron_runner.py)

## Execution Instructions

### Step 1: Implement Connect Webhook Listener
* In `stripe_v2.py`, inside the `/webhook` endpoint, listen for `payout.failed` and `payout.canceled` events.
* When a payout fails, look up the target transfer/payout transaction ID, reverse the balance debit in the local `user_earnings` database ledger, and mark the instant payout status as `failed` in the database.

### Step 2: Ensure Transactional Atomicity
* Audit all endpoints in `api_v2.py` that distribute royalties or debit user balances.
* Wrap all SQL execution stages inside a single, explicit PostgreSQL transaction blocks using `with db:` or explicit `db.commit()` and `db.rollback()` exception handlers to prevent partial ledger updates.

### Step 3: Implement Daily Payout Cron Job
* In `cron_runner.py`, configure a daily cron trigger at midnight UTC that queries the `instant_payout_queue` for all pending transfers, checks if the users have set up Stripe Connect accounts, executes the payout via Stripe's Transfer API, and updates their queue status.

## Verification Checklist
* [ ] Verify that a simulated failed Stripe Transfer triggers a rollback of the user's debited balance in tests.
* [ ] Verify that database exceptions anywhere during a remix generation correctly roll back all royalty splits.
* [ ] Run `python3 -m pytest tests/` to confirm that standard mock flows pass.
