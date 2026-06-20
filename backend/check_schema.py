#!/usr/bin/env python3
import psycopg2
import os
import sys

try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    
    # Check tables
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    tables = cur.fetchall()
    
    print("=" * 60)
    print("PRODUCTION DATABASE SCHEMA CHECK")
    print("=" * 60)
    print(f"\nTotal tables: {len(tables)}")
    print("\nTables:")
    for t in tables:
        print(f"  - {t[0]}")
    
    # Check if license_transactions exists
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'license_transactions')")
    has_license = cur.fetchone()[0]
    print(f"\nlicense_transactions exists: {has_license}")
    
    # Check if user_ledger exists
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_ledger')")
    has_ledger = cur.fetchone()[0]
    print(f"user_ledger exists: {has_ledger}")
    
    # Check constraints on license_transactions if it exists
    if has_license:
        cur.execute("""
            SELECT conname FROM pg_constraint 
            WHERE conrelid = 'license_transactions'::regclass
            ORDER BY conname
        """)
        constraints = cur.fetchall()
        print(f"\nlicense_transactions constraints ({len(constraints)}):")
        for c in constraints:
            print(f"  - {c[0]}")
    
    print("\n" + "=" * 60)
    
    cur.close()
    conn.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
