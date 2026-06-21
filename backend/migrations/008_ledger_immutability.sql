-- Migration 008: Enforce append-only immutability on user_ledger (FN8-695)
-- Apply AFTER 007. Money-critical — apply manually with ratification (FN8-701).
--
-- migration 004 declared the ledger "append-only" with only `CHECK (created_at <= NOW())`,
-- which validates the inserted value and does NOTHING against UPDATE/DELETE/TRUNCATE.
-- A REVOKE would be bypassed by the table owner (the app's DB role), so enforce with a
-- trigger that fires regardless of role. INSERT remains allowed (the only legitimate op;
-- corrections are new rows: payout_failed / payout_reversed credit-backs).
--
-- Verified no code path issues UPDATE/DELETE on user_ledger (grep, 2026-06-21), so this
-- breaks nothing. distribute_remix_royalties_v2 and request_payout only INSERT.

CREATE OR REPLACE FUNCTION prevent_user_ledger_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'user_ledger is append-only; % is not permitted (corrections must be new rows)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_ledger_no_mutation ON user_ledger;
CREATE TRIGGER trg_user_ledger_no_mutation
    BEFORE UPDATE OR DELETE ON user_ledger
    FOR EACH ROW EXECUTE FUNCTION prevent_user_ledger_mutation();

DROP TRIGGER IF EXISTS trg_user_ledger_no_truncate ON user_ledger;
CREATE TRIGGER trg_user_ledger_no_truncate
    BEFORE TRUNCATE ON user_ledger
    FOR EACH STATEMENT EXECUTE FUNCTION prevent_user_ledger_mutation();

-- ============================================================================
-- Balance source-of-truth note (the "4 competing representations" in FN8-695)
-- ============================================================================
-- After this migration the canonical model is:
--   * user_ledger              = the append-only source of truth (now enforced)
--   * user_balances_derived    = the derived read model (matview, refreshed by v2)
--   * generations.earnings     = a per-TRACK stat (not a user balance) — retained for the
--                                "top earning tapes" view; not a competing balance.
--   * users.total_earned /
--     users.pending_payout     = legacy/stale. FN8-692 already moved the withdrawable-balance
--                                reads (request_payout, get_earnings) onto the ledger, so these
--                                columns no longer gate money. Remaining cleanup: point
--                                check_royalty_health's drift check at ledger↔matview instead
--                                of users.total_earned (it currently false-alarms). Tracked.
--
-- ============================================================================
-- ROLLBACK
-- ============================================================================
-- DROP TRIGGER IF EXISTS trg_user_ledger_no_truncate ON user_ledger;
-- DROP TRIGGER IF EXISTS trg_user_ledger_no_mutation ON user_ledger;
-- DROP FUNCTION IF EXISTS prevent_user_ledger_mutation();
