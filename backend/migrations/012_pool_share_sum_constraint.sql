-- Migration 012: enforce that a royalty pool's member shares sum to <= 100%
-- Apply AFTER 011. Idempotent. Money-critical — apply manually with ratification (FN8-701).
--
-- royalty_pool_members.valid_share only bounds EACH row to 0..100; nothing stopped a pool's
-- members from summing PAST 100% (over-allocating royalties beyond the whole). A CHECK constraint
-- cannot express a cross-row SUM, so enforce the pool-level invariant with a trigger. It RAISEs
-- with SQLSTATE 23514 (check_violation) so clients see a CheckViolation / IntegrityError, exactly
-- as a CHECK constraint would — no client code needs to special-case a trigger error class.

CREATE OR REPLACE FUNCTION enforce_pool_share_sum() RETURNS TRIGGER AS $$
DECLARE
    v_total NUMERIC(6,2);
BEGIN
    -- Sum the OTHER members of this pool (exclude the row being updated), then add NEW.
    SELECT COALESCE(SUM(share_percentage), 0) INTO v_total
    FROM royalty_pool_members
    WHERE pool_id = NEW.pool_id AND id <> NEW.id;

    IF v_total + NEW.share_percentage > 100 THEN
        RAISE EXCEPTION 'royalty_pool_members: shares for pool % would total %, exceeding 100',
            NEW.pool_id, (v_total + NEW.share_percentage)
            USING ERRCODE = '23514';  -- check_violation -> psycopg2 CheckViolation (IntegrityError)
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pool_share_sum ON royalty_pool_members;
CREATE TRIGGER trg_pool_share_sum
    BEFORE INSERT OR UPDATE ON royalty_pool_members
    FOR EACH ROW EXECUTE FUNCTION enforce_pool_share_sum();

-- ============================================================================
-- ROLLBACK
-- ============================================================================
-- DROP TRIGGER IF EXISTS trg_pool_share_sum ON royalty_pool_members;
-- DROP FUNCTION IF EXISTS enforce_pool_share_sum();
