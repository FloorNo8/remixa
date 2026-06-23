-- Migration 011: drop the dead legacy distribute_remix_royalties (v1) (FN8-696)
-- Apply AFTER 010. Idempotent.
--
-- v1 (migration 002) predates the hardened schema: its license_transactions INSERT omits
-- original_creator_id_snapshot (made NOT NULL by migration 004), so any call fails with
-- NotNullViolation. Production and all tests use distribute_remix_royalties_v2 (migration 007);
-- v1 is unreferenced dead code (verified: api_v2.py:636 calls _v2; no migration PERFORMs v1).
-- Removing it eliminates the broken-function surface rather than resurrecting a redundant
-- second royalty engine.

DROP FUNCTION IF EXISTS distribute_remix_royalties(UUID, UUID, UUID);

-- ============================================================================
-- ROLLBACK: re-create from migration 002 if v1 is ever needed (it should not be).
-- ============================================================================
