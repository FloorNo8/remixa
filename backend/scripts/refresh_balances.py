#!/usr/bin/env python3
"""
Refresh the user_balances_derived materialized view out-of-band (FN8-703).

Run by scripts.cron_runner. Uses a direct `REFRESH MATERIALIZED VIEW CONCURRENTLY` in
autocommit (lock-free — readers are never blocked, and CONCURRENTLY cannot run inside a
transaction). The royalty path (distribute_remix_royalties_v2) no longer refreshes the
matview synchronously, since that ran CONCURRENTLY inside the request transaction.
"""
import os

import psycopg2


def main():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    conn.autocommit = True  # REFRESH ... CONCURRENTLY must not run inside a transaction block
    try:
        cur = conn.cursor()
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY user_balances_derived")
        print("✅ user_balances_derived refreshed")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
