-- ============================================================================
-- GRAFANA DASHBOARD QUERIES FOR REMIXA ROYALTY MONITORING
-- ============================================================================
-- 
-- These queries are designed for Grafana with PostgreSQL data source.
-- Each query includes:
-- - Purpose: What the query monitors
-- - Visualization: Recommended Grafana panel type
-- - Alert: Suggested alert threshold
--
-- Setup:
-- 1. Add PostgreSQL data source in Grafana (DATABASE_URL)
-- 2. Create dashboard and add panels
-- 3. Copy queries into panel query editor
-- 4. Configure alerts as needed
--
-- ============================================================================

-- ============================================================================
-- PANEL 1: CONSTRAINT VIOLATIONS (Time Series)
-- ============================================================================
-- Purpose: Track constraint violations over time
-- Visualization: Time series graph
-- Alert: > 0 violations in 5 minutes
-- ============================================================================

SELECT 
    DATE_TRUNC('hour', created_at) as time,
    COUNT(*) as violations
FROM audit_log
WHERE action = 'constraint_violation'
    AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY time;

-- ============================================================================
-- PANEL 2: ROYALTY DISTRIBUTION RATE (Time Series)
-- ============================================================================
-- Purpose: Track remix rate and royalty distributions
-- Visualization: Time series graph with dual axis
-- Alert: < 10 remixes/hour during peak hours
-- ============================================================================

SELECT 
    DATE_TRUNC('hour', created_at) as time,
    COUNT(*) as remixes,
    SUM(amount) as total_distributed,
    AVG(amount) as avg_amount
FROM license_transactions
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY time;

-- ============================================================================
-- PANEL 3: LEDGER DRIFT DETECTION (Stat)
-- ============================================================================
-- Purpose: Show users with ledger drift > €0.01
-- Visualization: Stat panel (single number)
-- Alert: > 0 users with drift
-- ============================================================================

SELECT COUNT(*) as drift_count
FROM (
    SELECT 
        u.id,
        u.total_earned,
        COALESCE(SUM(l.amount), 0) as ledger_balance,
        ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) as drift
    FROM users u
    LEFT JOIN user_ledger l ON u.id = l.user_id
    GROUP BY u.id, u.total_earned
    HAVING ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) > 0.01
) drifts;

-- ============================================================================
-- PANEL 4: TOP DRIFTS (Table)
-- ============================================================================
-- Purpose: Show users with highest ledger drift
-- Visualization: Table
-- Alert: N/A (informational)
-- ============================================================================

SELECT 
    u.username,
    u.total_earned,
    COALESCE(SUM(l.amount), 0) as ledger_balance,
    ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) as drift
FROM users u
LEFT JOIN user_ledger l ON u.id = l.user_id
GROUP BY u.id, u.username, u.total_earned
HAVING ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) > 0.01
ORDER BY drift DESC
LIMIT 10;

-- ============================================================================
-- PANEL 5: CONSERVATION INVARIANT VIOLATIONS (Stat)
-- ============================================================================
-- Purpose: Count transactions violating conservation
-- Visualization: Stat panel (single number)
-- Alert: > 0 violations
-- ============================================================================

SELECT COUNT(*) as violation_count
FROM license_transactions
WHERE ABS(amount - platform_fee - creator_share - COALESCE(grandparent_share, 0)) > 0.001;

-- ============================================================================
-- PANEL 6: ROYALTY SPLIT DISTRIBUTION (Pie Chart)
-- ============================================================================
-- Purpose: Show distribution of royalties (platform vs creators)
-- Visualization: Pie chart
-- Alert: N/A (informational)
-- ============================================================================

SELECT 
    'Platform' as category,
    SUM(platform_fee) as amount
FROM license_transactions
WHERE created_at >= NOW() - INTERVAL '24 hours'
UNION ALL
SELECT 
    'Parent Creators' as category,
    SUM(creator_share) as amount
FROM license_transactions
WHERE created_at >= NOW() - INTERVAL '24 hours'
UNION ALL
SELECT 
    'Grandparent Creators' as category,
    SUM(COALESCE(grandparent_share, 0)) as amount
FROM license_transactions
WHERE created_at >= NOW() - INTERVAL '24 hours';

-- ============================================================================
-- PANEL 7: ORPHANED SNAPSHOTS (Stat)
-- ============================================================================
-- Purpose: Count transactions with NULL snapshots
-- Visualization: Stat panel (single number)
-- Alert: > 0 orphaned snapshots
-- ============================================================================

SELECT COUNT(*) as orphaned_count
FROM license_transactions
WHERE (
    (original_creator_id_snapshot IS NULL AND original_creator_id IS NOT NULL)
    OR
    (grandparent_creator_id_snapshot IS NULL AND grandparent_creator_id IS NOT NULL)
);

-- ============================================================================
-- PANEL 8: IDEMPOTENCY VIOLATIONS (Stat)
-- ============================================================================
-- Purpose: Count duplicate payments (idempotency violations)
-- Visualization: Stat panel (single number)
-- Alert: > 0 duplicates
-- ============================================================================

SELECT COUNT(*) as duplicate_count
FROM (
    SELECT 
        remixer_id,
        generation_id,
        COUNT(*) as count
    FROM license_transactions
    GROUP BY remixer_id, generation_id
    HAVING COUNT(*) > 1
) duplicates;

-- ============================================================================
-- PANEL 9: LEDGER BALANCE DISTRIBUTION (Histogram)
-- ============================================================================
-- Purpose: Show distribution of user balances
-- Visualization: Histogram
-- Alert: N/A (informational)
-- ============================================================================

SELECT 
    CASE 
        WHEN balance < 1 THEN '€0-1'
        WHEN balance < 5 THEN '€1-5'
        WHEN balance < 10 THEN '€5-10'
        WHEN balance < 20 THEN '€10-20'
        WHEN balance < 50 THEN '€20-50'
        WHEN balance < 100 THEN '€50-100'
        ELSE '€100+'
    END as balance_range,
    COUNT(*) as user_count
FROM (
    SELECT 
        user_id,
        SUM(amount) as balance
    FROM user_ledger
    GROUP BY user_id
) balances
GROUP BY balance_range
ORDER BY 
    CASE balance_range
        WHEN '€0-1' THEN 1
        WHEN '€1-5' THEN 2
        WHEN '€5-10' THEN 3
        WHEN '€10-20' THEN 4
        WHEN '€20-50' THEN 5
        WHEN '€50-100' THEN 6
        ELSE 7
    END;

-- ============================================================================
-- PANEL 10: REMIX CHAIN DEPTH (Bar Chart)
-- ============================================================================
-- Purpose: Show distribution of remix chain depths
-- Visualization: Bar chart
-- Alert: N/A (informational)
-- ============================================================================

SELECT 
    CASE 
        WHEN grandparent_creator_id IS NOT NULL THEN '3-level'
        WHEN original_creator_id IS NOT NULL THEN '2-level'
        ELSE '1-level (original)'
    END as chain_depth,
    COUNT(*) as count
FROM license_transactions
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY chain_depth;

-- ============================================================================
-- PANEL 11: TOP EARNERS (Table)
-- ============================================================================
-- Purpose: Show top earning creators
-- Visualization: Table
-- Alert: N/A (informational)
-- ============================================================================

SELECT 
    u.username,
    COUNT(DISTINCT lt.generation_id) as remixes_received,
    SUM(lt.creator_share + COALESCE(lt.grandparent_share, 0)) as total_earned,
    AVG(lt.creator_share) as avg_per_remix
FROM users u
JOIN license_transactions lt ON (
    u.id = lt.original_creator_id 
    OR u.id = lt.grandparent_creator_id
)
WHERE lt.created_at >= NOW() - INTERVAL '7 days'
GROUP BY u.id, u.username
ORDER BY total_earned DESC
LIMIT 10;

-- ============================================================================
-- PANEL 12: NEGATIVE BALANCES (Stat)
-- ============================================================================
-- Purpose: Count users with negative ledger balance
-- Visualization: Stat panel (single number)
-- Alert: > 0 negative balances
-- ============================================================================

SELECT COUNT(*) as negative_balance_count
FROM (
    SELECT 
        user_id,
        SUM(amount) as balance
    FROM user_ledger
    GROUP BY user_id
    HAVING SUM(amount) < 0
) negative_balances;

-- ============================================================================
-- PANEL 13: PAYOUT PROCESSING (Time Series)
-- ============================================================================
-- Purpose: Track payout requests and processing
-- Visualization: Time series graph
-- Alert: Pending payouts > 100
-- ============================================================================

SELECT 
    DATE_TRUNC('day', created_at) as time,
    COUNT(*) as payout_requests,
    SUM(amount) as total_amount,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
FROM payouts
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY time;

-- ============================================================================
-- PANEL 14: GDPR DELETIONS IMPACT (Time Series)
-- ============================================================================
-- Purpose: Track GDPR deletions and snapshot usage
-- Visualization: Time series graph
-- Alert: N/A (informational)
-- ============================================================================

SELECT 
    DATE_TRUNC('day', created_at) as time,
    COUNT(*) as total_transactions,
    COUNT(CASE WHEN original_creator_id_snapshot != original_creator_id THEN 1 END) as using_parent_snapshot,
    COUNT(CASE WHEN grandparent_creator_id_snapshot != grandparent_creator_id THEN 1 END) as using_grandparent_snapshot
FROM license_transactions
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY time;

-- ============================================================================
-- PANEL 15: SYSTEM HEALTH SCORE (Gauge)
-- ============================================================================
-- Purpose: Overall health score (0-100)
-- Visualization: Gauge
-- Alert: < 95
-- ============================================================================

SELECT 
    100 - (
        (SELECT COUNT(*) FROM license_transactions 
         WHERE ABS(amount - platform_fee - creator_share - COALESCE(grandparent_share, 0)) > 0.001) * 10 +
        (SELECT COUNT(*) FROM (
            SELECT remixer_id, generation_id, COUNT(*) as count
            FROM license_transactions
            GROUP BY remixer_id, generation_id
            HAVING COUNT(*) > 1
        ) dups) * 10 +
        (SELECT COUNT(*) FROM (
            SELECT u.id, ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) as drift
            FROM users u
            LEFT JOIN user_ledger l ON u.id = l.user_id
            GROUP BY u.id, u.total_earned
            HAVING ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) > 0.01
        ) drifts) * 5
    ) as health_score;

-- ============================================================================
-- ALERT RULES CONFIGURATION
-- ============================================================================
-- 
-- Recommended Grafana alert rules:
--
-- 1. Constraint Violations
--    Query: PANEL 1
--    Condition: violations > 0
--    For: 5 minutes
--    Severity: Critical
--
-- 2. Ledger Drift
--    Query: PANEL 3
--    Condition: drift_count > 0
--    For: 1 hour
--    Severity: High
--
-- 3. Conservation Violations
--    Query: PANEL 5
--    Condition: violation_count > 0
--    For: 5 minutes
--    Severity: Critical
--
-- 4. Orphaned Snapshots
--    Query: PANEL 7
--    Condition: orphaned_count > 0
--    For: 1 hour
--    Severity: High
--
-- 5. Idempotency Violations
--    Query: PANEL 8
--    Condition: duplicate_count > 0
--    For: 5 minutes
--    Severity: Critical
--
-- 6. Negative Balances
--    Query: PANEL 12
--    Condition: negative_balance_count > 0
--    For: 1 hour
--    Severity: High
--
-- 7. System Health
--    Query: PANEL 15
--    Condition: health_score < 95
--    For: 15 minutes
--    Severity: Warning
--
-- ============================================================================
