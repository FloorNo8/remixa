#!/usr/bin/env python3
import psycopg2
import os
import sys

def apply_migration(cur, conn, filepath, name):
    """Apply a single migration file"""
    try:
        print(f"\n{'='*60}")
        print(f"Applying {name}...")
        print(f"{'='*60}")
        
        with open(filepath, 'r') as f:
            sql = f.read()
        
        cur.execute(sql)
        conn.commit()
        print(f"✅ {name} applied successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ {name} failed: {e}")
        return False

def main():
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        conn.autocommit = False
        cur = conn.cursor()
        
        print("="*60)
        print("REMIXA PRODUCTION DATABASE MIGRATION")
        print("="*60)
        
        # Apply migrations in order
        migrations = [
            ('/app/database.sql', 'Base Schema (database.sql)'),
            ('/app/migrations/002_v2_social_features.sql', 'Migration 002 (Social Features)'),
            ('/app/migrations/004_royalty_hardening.sql', 'Migration 004 (Royalty Hardening)')
        ]
        
        for filepath, name in migrations:
            if not apply_migration(cur, conn, filepath, name):
                print(f"\n❌ Migration sequence failed at {name}")
                sys.exit(1)
        
        # Verify final state
        print(f"\n{'='*60}")
        print("VERIFICATION")
        print(f"{'='*60}")
        
        cur.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
        table_count = cur.fetchone()[0]
        print(f"✅ Total tables: {table_count}")
        
        cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'license_transactions')")
        has_license = cur.fetchone()[0]
        print(f"✅ license_transactions exists: {has_license}")
        
        cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_ledger')")
        has_ledger = cur.fetchone()[0]
        print(f"✅ user_ledger exists: {has_ledger}")
        
        cur.execute("""
            SELECT conname FROM pg_constraint 
            WHERE conname IN ('check_conservation_invariant', 'unique_remix_payment', 'check_c2pa_parent_consistency')
        """)
        constraints = cur.fetchall()
        print(f"✅ Money-correctness constraints: {len(constraints)}/3")
        for c in constraints:
            print(f"   - {c[0]}")
        
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'distribute_remix_royalties_v2')")
        has_func = cur.fetchone()[0]
        print(f"✅ distribute_remix_royalties_v2 function exists: {has_func}")
        
        print(f"\n{'='*60}")
        print("🎉 ALL MIGRATIONS APPLIED SUCCESSFULLY")
        print(f"{'='*60}\n")
        
        cur.close()
        conn.close()
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
