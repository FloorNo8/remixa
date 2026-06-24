#!/usr/bin/env python3
"""
Remixa tracked migration runner.

Replaces the old blind-re-execute runner (a hardcoded 3-file list with no
tracking table) with a real, idempotent migration ledger:

  * a `schema_migrations` tracking table records every applied file + its
    sha256 checksum, so a second run applies nothing new;
  * migrations are DISCOVERED (database.sql first, then sorted migrations/NNN_*.sql)
    rather than hardcoded;
  * each pending file runs once, in lexical order, in its own transaction;
  * the run aborts (exit 1) on the first failure WITHOUT recording the failed file;
  * money / Type-1 migrations (RATIFIED_REQUIRED) are GATED: they are skipped
    unless explicitly authorized via `--apply-ratified <file>` (repeatable) or
    the REMIXA_RATIFIED_MIGRATIONS env var (comma-separated). This preserves the
    FN8-701 manual-ratification gate documented in migrations/APPLY_ORDER.md.

The pure decision functions (discover_migrations, is_ratified,
needs_ratification, compute_checksum, filter_pending) are DB-free and unit-tested
in tests/test_apply_migrations.py.

Entry point unchanged: `python apply_migrations.py` (reads DATABASE_URL from env).

NOTE: migrations run in AUTOCOMMIT and are split into individual statements (respecting
$$-quoted function bodies and comments), so statements that REQUIRE it — CREATE INDEX
CONCURRENTLY / REFRESH MATERIALIZED VIEW CONCURRENTLY (migrations 003/004/005/010) — work
without stripping CONCURRENTLY (which would lock prod tables). Migrations are idempotent, so a
partial failure is safe to re-run; a file is recorded only after all its statements succeed.
"""
import argparse
import glob
import hashlib
import os
import re
import sys

import psycopg2

# Directories resolved relative to THIS file so the runner works whether it runs
# from the repo (backend/) or from a container image where it lives at /app.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")
BASE_SCHEMA_FILENAME = "database.sql"

# Money / Type-1 migrations. Each carries an explicit "apply manually with
# ratification (FN8-701)" directive in its own header (see migrations/APPLY_ORDER.md).
# The runner will NOT apply any of these unless it is explicitly ratified.
RATIFIED_REQUIRED = {
    "006_clerk_auth.sql",
    "007_idempotency_hardening.sql",
    "008_ledger_immutability.sql",
    "010_matview_refresh_out_of_band.sql",
    "011_drop_legacy_distribute_remix_royalties.sql",
    "012_pool_share_sum_constraint.sql",
}

CREATE_TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    checksum TEXT,
    applied_at TIMESTAMPTZ DEFAULT now()
)
"""


# ---------------------------------------------------------------------------
# Pure / DB-free logic (unit-tested without a database)
# ---------------------------------------------------------------------------
def discover_migrations(backend_dir=BACKEND_DIR, migrations_dir=MIGRATIONS_DIR):
    """
    Discover migrations in apply order.

    Returns a list of (filename, filepath) tuples:
      1. database.sql first (base schema, recorded under filename 'database.sql'),
      2. then migrations/NNN_*.sql in lexical (sorted) order.

    Only files matching NNN_*.sql are picked up from the migrations dir, so docs
    like APPLY_ORDER.md are ignored. Pure function: no DB, no side effects.
    """
    discovered = []

    base_path = os.path.join(backend_dir, BASE_SCHEMA_FILENAME)
    discovered.append((BASE_SCHEMA_FILENAME, base_path))

    pattern = os.path.join(migrations_dir, "[0-9][0-9][0-9]_*.sql")
    for filepath in sorted(glob.glob(pattern)):
        discovered.append((os.path.basename(filepath), filepath))

    return discovered


def needs_ratification(filename, ratified_required=RATIFIED_REQUIRED):
    """True if `filename` is a money/Type-1 migration gated behind ratification."""
    return filename in ratified_required


def is_ratified(filename, ratified_set):
    """True if `filename` has been explicitly authorized for application."""
    return filename in (ratified_set or set())


def compute_checksum(content):
    """sha256 hex digest of migration content (str or bytes)."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def filter_pending(discovered, applied_filenames):
    """
    From discovered [(filename, filepath), ...], drop the files already recorded
    in schema_migrations. Preserves order. Pure function.
    """
    applied = applied_filenames or set()
    return [(fn, fp) for (fn, fp) in discovered if fn not in applied]


def resolve_ratified_set(cli_apply_ratified=None, env_value=None):
    """
    Build the set of explicitly-ratified filenames from:
      * the repeatable CLI flag `--apply-ratified <file>` (a list), and
      * the env var REMIXA_RATIFIED_MIGRATIONS (comma-separated).
    Whitespace-trimmed; empty entries dropped. Pure function.
    """
    ratified = set()
    for name in cli_apply_ratified or []:
        name = (name or "").strip()
        if name:
            ratified.add(name)
    if env_value:
        for name in env_value.split(","):
            name = name.strip()
            if name:
                ratified.add(name)
    return ratified


# ---------------------------------------------------------------------------
# DB-touching helpers
# ---------------------------------------------------------------------------
def ensure_tracking_table(conn):
    """Create the schema_migrations tracking table if absent."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TRACKING_TABLE_SQL)
    conn.commit()


def fetch_applied(conn):
    """Return the set of filenames already recorded in schema_migrations."""
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def record_applied(conn, filename, checksum):
    """Record a successfully-applied migration. Caller controls the transaction."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
            (filename, checksum),
        )


def _statement_has_sql(stmt):
    """True if stmt has real SQL (not only comments/whitespace) — psycopg2 rejects an empty query."""
    no_comments = re.sub(r"/\*.*?\*/", "", re.sub(r"--[^\n]*", "", stmt), flags=re.DOTALL)
    return bool(no_comments.strip())


def split_sql_statements(sql):
    """
    Split a SQL script into individual statements, respecting dollar-quoted bodies ($$ / $tag$),
    single-quoted strings, and -- / /* */ comments. psycopg2 sends a multi-statement string as ONE
    implicit transaction block — in which CONCURRENTLY statements cannot run — so each statement
    must be executed on its own (the connection is in autocommit, so each is its own transaction).
    """
    statements, buf, i, n = [], [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "-" and i + 1 < n and sql[i + 1] == "-":            # line comment
            j = sql.find("\n", i)
            j = n if j == -1 else j
            buf.append(sql[i:j]); i = j; continue
        if c == "/" and i + 1 < n and sql[i + 1] == "*":            # block comment
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            buf.append(sql[i:j]); i = j; continue
        if c == "'":                                                # single-quoted string
            buf.append(c); i += 1
            while i < n:
                buf.append(sql[i])
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":             # '' escape
                        buf.append(sql[i + 1]); i += 2; continue
                    i += 1; break
                i += 1
            continue
        if c == "$":                                                # dollar-quoted body ($$ / $tag$)
            m = re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                end = sql.find(tag, i + len(tag))
                end = n if end == -1 else end + len(tag)
                buf.append(sql[i:end]); i = end; continue
        if c == ";":                                                # statement terminator
            stmt = "".join(buf).strip()
            if _statement_has_sql(stmt):
                statements.append(stmt)
            buf = []; i += 1; continue
        buf.append(c); i += 1
    tail = "".join(buf).strip()
    if _statement_has_sql(tail):
        statements.append(tail)
    return statements


def apply_one(conn, filename, filepath):
    """
    Apply a single migration file and record it on success. The connection is in AUTOCOMMIT (see
    main) and the file is split into individual statements so CONCURRENTLY statements run alone.
    Migrations are idempotent, so a partial failure is safe to re-run: the file is recorded only
    after EVERY statement succeeds. Re-raises on failure so the caller can abort.
    """
    with open(filepath, "r") as f:
        sql = f.read()
    checksum = compute_checksum(sql)
    with conn.cursor() as cur:
        for statement in split_sql_statements(sql):
            cur.execute(statement)
    record_applied(conn, filename, checksum)
    return True


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(conn, ratified_set):
    """
    Apply all PENDING migrations in order, honoring the ratification gate.

    Returns 0 on success (or nothing-to-do), 1 if a migration failed. Gated,
    un-ratified migrations are SKIPPED (the run continues) — they do not fail.
    """
    ensure_tracking_table(conn)
    applied = fetch_applied(conn)
    pending = filter_pending(discover_migrations(), applied)

    if not pending:
        print("Nothing to apply — schema is up to date.")
        return 0

    for filename, filepath in pending:
        if needs_ratification(filename) and not is_ratified(filename, ratified_set):
            print(
                f"-- {filename}: SKIPPED (needs ratification: "
                f"pass --apply-ratified {filename})"
            )
            continue

        if not os.path.exists(filepath):
            print(f"!! {filename}: file not found at {filepath} — aborting.")
            return 1

        label = "RATIFIED" if needs_ratification(filename) else "applying"
        print(f"-- {filename}: {label} ...")
        try:
            apply_one(conn, filename, filepath)
            print(f"   {filename}: OK")
        except Exception as e:
            print(f"!! {filename}: FAILED — {e}")
            print(f"   aborting; {filename} was NOT recorded.")
            return 1

    print("Migration run complete.")
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Apply Remixa DB migrations with a tracked schema_migrations ledger."
    )
    parser.add_argument(
        "--apply-ratified",
        action="append",
        default=[],
        metavar="FILENAME",
        help=(
            "Explicitly authorize a money/Type-1 (RATIFIED_REQUIRED) migration to "
            "be applied, e.g. --apply-ratified 006_clerk_auth.sql. Repeatable."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    ratified_set = resolve_ratified_set(
        cli_apply_ratified=args.apply_ratified,
        env_value=os.getenv("REMIXA_RATIFIED_MIGRATIONS"),
    )

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        return 1

    conn = None
    try:
        conn = psycopg2.connect(database_url)
        # Autocommit for the whole run: some migrations use CREATE INDEX / REFRESH MATVIEW
        # CONCURRENTLY, which cannot run inside a transaction block. Migrations are idempotent,
        # so a partial failure is safe to re-run (the failed file is just not recorded).
        conn.autocommit = True
        return run(conn, ratified_set)
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
