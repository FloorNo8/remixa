-- Migration 009: drop the orphaned process_pending_payouts() SQL function (FN8-692)
-- Apply AFTER 008. Idempotent.
--
-- migration 002:343-360 defined a SQL function process_pending_payouts() that gated payouts
-- on the stale `users.pending_payout` column (never updated by distribute_remix_royalties_v2).
-- It was never called by anything — the actual cron path is scripts/process_payouts.py, now
-- rewritten to process `payout_requests` against the append-only `user_ledger`. Drop the dead
-- function so nothing wires it later.

DROP FUNCTION IF EXISTS process_pending_payouts();

-- Rollback: re-create from migration 002 (CREATE OR REPLACE FUNCTION process_pending_payouts()
-- RETURNS TABLE(processed_count INT) ... gating on users.pending_payout >= 20). Not recommended.
