#!/usr/bin/env python3
"""
Daily Royalty Health Check Script

Verifies money-correctness invariants in production:
1. All constraints exist
2. No ledger drift (ledger balance matches users.total_earned)
3. No orphaned snapshots (NULL after GDPR deletion)
4. Conservation holds for all transactions

Run daily via cron:
0 9 * * * cd /app && python scripts/check_royalty_health.py

Exit codes:
0 - All checks passed
1 - One or more checks failed
2 - Critical error (database connection, etc.)
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

# Sentry integration (optional)
try:
    import sentry_sdk
    SENTRY_ENABLED = bool(os.getenv("SENTRY_DSN"))
    if SENTRY_ENABLED:
        sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
except ImportError:
    SENTRY_ENABLED = False

class HealthCheckResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.warnings = []
        self.errors = []
        self.details = {}
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    def add_error(self, message: str):
        self.errors.append(message)
        self.passed = False
    
    def to_dict(self):
        return {
            "name": self.name,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "details": self.details
        }

def check_constraints(cur) -> HealthCheckResult:
    """Verify all money-correctness constraints exist"""
    result = HealthCheckResult("Constraints Check")
    
    required_constraints = [
        "check_conservation_invariant",
        "unique_remix_payment",
        "check_c2pa_parent_consistency"
    ]
    
    cur.execute("""
        SELECT conname 
        FROM pg_constraint 
        WHERE conname IN %s
    """, (tuple(required_constraints),))
    
    existing = [row['conname'] for row in cur.fetchall()]
    result.details['existing_constraints'] = existing
    result.details['required_constraints'] = required_constraints
    
    missing = set(required_constraints) - set(existing)
    if missing:
        result.add_error(f"Missing constraints: {', '.join(missing)}")
    
    return result

def check_ledger_drift(cur) -> HealthCheckResult:
    """Verify ledger balance matches users.total_earned"""
    result = HealthCheckResult("Ledger Drift Check")
    
    cur.execute("""
        SELECT 
            u.id,
            u.username,
            u.total_earned,
            COALESCE(SUM(l.amount), 0) as ledger_balance,
            ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) as drift
        FROM users u
        LEFT JOIN user_ledger l ON u.id = l.user_id
        GROUP BY u.id, u.username, u.total_earned
        HAVING ABS(u.total_earned - COALESCE(SUM(l.amount), 0)) > 0.01
        ORDER BY drift DESC
        LIMIT 10
    """)
    
    drifts = cur.fetchall()
    result.details['drift_count'] = len(drifts)
    
    if drifts:
        result.add_error(f"Found {len(drifts)} users with ledger drift > €0.01")
        result.details['top_drifts'] = [
            {
                'user_id': str(row['id']),
                'username': row['username'],
                'total_earned': float(row['total_earned']),
                'ledger_balance': float(row['ledger_balance']),
                'drift': float(row['drift'])
            }
            for row in drifts[:5]  # Top 5 only
        ]
    
    return result

def check_orphaned_snapshots(cur) -> HealthCheckResult:
    """Verify no NULL snapshots after GDPR deletion"""
    result = HealthCheckResult("Orphaned Snapshots Check")
    
    # Check for transactions with NULL snapshots where creator is erased
    cur.execute("""
        SELECT COUNT(*) as orphaned_count
        FROM license_transactions lt
        WHERE (
            (lt.original_creator_id_snapshot IS NULL AND lt.original_creator_id IS NOT NULL)
            OR
            (lt.grandparent_creator_id_snapshot IS NULL AND lt.grandparent_creator_id IS NOT NULL)
        )
    """)
    
    orphaned = cur.fetchone()
    result.details['orphaned_count'] = orphaned['orphaned_count']
    
    if orphaned['orphaned_count'] > 0:
        result.add_error(f"Found {orphaned['orphaned_count']} transactions with NULL snapshots")
    
    return result

def check_conservation_invariant(cur) -> HealthCheckResult:
    """Verify conservation holds for all transactions"""
    result = HealthCheckResult("Conservation Invariant Check")
    
    cur.execute("""
        SELECT 
            id,
            amount,
            platform_fee,
            creator_share,
            COALESCE(grandparent_share, 0) as grandparent_share,
            (amount - platform_fee - creator_share - COALESCE(grandparent_share, 0)) as violation
        FROM license_transactions
        WHERE ABS(amount - platform_fee - creator_share - COALESCE(grandparent_share, 0)) > 0.001
        LIMIT 10
    """)
    
    violations = cur.fetchall()
    result.details['violation_count'] = len(violations)
    
    if violations:
        result.add_error(f"Found {len(violations)} transactions violating conservation invariant")
        result.details['violations'] = [
            {
                'id': str(row['id']),
                'amount': float(row['amount']),
                'platform_fee': float(row['platform_fee']),
                'creator_share': float(row['creator_share']),
                'grandparent_share': float(row['grandparent_share']),
                'violation': float(row['violation'])
            }
            for row in violations[:5]  # Top 5 only
        ]
    
    return result

def check_ledger_integrity(cur) -> HealthCheckResult:
    """Verify user_ledger table integrity"""
    result = HealthCheckResult("Ledger Integrity Check")
    
    # Check for negative balances
    cur.execute("""
        SELECT 
            user_id,
            SUM(amount) as balance
        FROM user_ledger
        GROUP BY user_id
        HAVING SUM(amount) < 0
    """)
    
    negative_balances = cur.fetchall()
    result.details['negative_balance_count'] = len(negative_balances)
    
    if negative_balances:
        result.add_warning(f"Found {len(negative_balances)} users with negative ledger balance")
        result.details['negative_balances'] = [
            {
                'user_id': str(row['user_id']),
                'balance': float(row['balance'])
            }
            for row in negative_balances[:5]
        ]
    
    # Check for orphaned ledger entries (no matching transaction)
    cur.execute("""
        SELECT COUNT(*) as orphaned_count
        FROM user_ledger l
        WHERE l.license_transaction_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM license_transactions lt 
            WHERE lt.id = l.license_transaction_id
        )
    """)
    
    orphaned = cur.fetchone()
    result.details['orphaned_ledger_entries'] = orphaned['orphaned_count']
    
    if orphaned['orphaned_count'] > 0:
        result.add_error(f"Found {orphaned['orphaned_count']} orphaned ledger entries")
    
    return result

def check_idempotency(cur) -> HealthCheckResult:
    """Verify no duplicate payments"""
    result = HealthCheckResult("Idempotency Check")
    
    cur.execute("""
        SELECT 
            remixer_id,
            generation_id,
            COUNT(*) as duplicate_count
        FROM license_transactions
        GROUP BY remixer_id, generation_id
        HAVING COUNT(*) > 1
        LIMIT 10
    """)
    
    duplicates = cur.fetchall()
    result.details['duplicate_count'] = len(duplicates)
    
    if duplicates:
        result.add_error(f"Found {len(duplicates)} duplicate payments (idempotency violation)")
        result.details['duplicates'] = [
            {
                'remixer_id': str(row['remixer_id']),
                'generation_id': str(row['generation_id']),
                'count': row['duplicate_count']
            }
            for row in duplicates[:5]
        ]
    
    return result

def run_health_checks():
    """Run all health checks and return results"""
    try:
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            cursor_factory=RealDictCursor
        )
        cur = conn.cursor()
        
        checks = [
            check_constraints(cur),
            check_conservation_invariant(cur),
            check_idempotency(cur),
            check_ledger_drift(cur),
            check_ledger_integrity(cur),
            check_orphaned_snapshots(cur)
        ]
        
        cur.close()
        conn.close()
        
        return checks
        
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection error: {e}", file=sys.stderr)
        if SENTRY_ENABLED:
            sentry_sdk.capture_exception(e)
        sys.exit(2)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        if SENTRY_ENABLED:
            sentry_sdk.capture_exception(e)
        sys.exit(2)

def main():
    print(f"🔍 Running Royalty Health Check - {datetime.utcnow().isoformat()}")
    print("=" * 80)
    
    checks = run_health_checks()
    
    all_passed = True
    has_warnings = False
    
    for check in checks:
        status = "✅" if check.passed else "❌"
        print(f"\n{status} {check.name}")
        
        if check.errors:
            all_passed = False
            for error in check.errors:
                print(f"  ❌ {error}")
        
        if check.warnings:
            has_warnings = True
            for warning in check.warnings:
                print(f"  ⚠️  {warning}")
        
        if check.passed and not check.warnings:
            print(f"  ✓ All checks passed")
    
    print("\n" + "=" * 80)
    
    # Generate JSON report
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "all_passed": all_passed,
        "has_warnings": has_warnings,
        "checks": [check.to_dict() for check in checks]
    }
    
    # Write report to file
    report_path = "/tmp/royalty_health_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📄 Report saved to: {report_path}")
    
    # Alert Sentry if checks failed
    if not all_passed and SENTRY_ENABLED:
        failed_checks = [c.name for c in checks if not c.passed]
        sentry_sdk.capture_message(
            f"Royalty health check failed: {', '.join(failed_checks)}",
            level="error",
            extras=report
        )
    
    # Exit with appropriate code
    if all_passed:
        print("\n✅ All health checks passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {sum(1 for c in checks if not c.passed)} health check(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
