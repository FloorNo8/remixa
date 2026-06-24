"""
Unit tests for the tracked migration runner (apply_migrations.py).

These tests exercise the PURE, DB-free decision logic only — no psycopg2
connection is ever opened, no database is touched. They verify:

  * migration discovery + ordering (database.sql first, then sorted NNN_*.sql),
  * the pending-vs-applied filter,
  * the ratification gate decision (gated files are skipped unless ratified),
  * sha256 checksum computation,
  * the ratified-set resolution from CLI flags + env var.
"""
import os

import apply_migrations as am


# ---------------------------------------------------------------------------
# checksum
# ---------------------------------------------------------------------------
class TestComputeChecksum:
    def test_sha256_of_str_matches_known_value(self):
        # sha256("") = e3b0c442... — anchors the algorithm choice.
        assert am.compute_checksum("") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_str_and_bytes_give_same_digest(self):
        assert am.compute_checksum("CREATE TABLE x();") == am.compute_checksum(
            b"CREATE TABLE x();"
        )

    def test_different_content_differs(self):
        assert am.compute_checksum("a") != am.compute_checksum("b")

    def test_is_deterministic(self):
        content = "SELECT 1;"
        assert am.compute_checksum(content) == am.compute_checksum(content)


# ---------------------------------------------------------------------------
# ratification gate
# ---------------------------------------------------------------------------
class TestRatificationGate:
    def test_money_migrations_need_ratification(self):
        for fn in am.RATIFIED_REQUIRED:
            assert am.needs_ratification(fn) is True

    def test_non_gated_migrations_do_not_need_ratification(self):
        for fn in (
            "database.sql",
            "002_v2_social_features.sql",
            "003_performance_indexes.sql",
            "004_royalty_hardening.sql",
            "005_advanced_features.sql",
            "009_drop_orphaned_payout_fn.sql",
        ):
            assert am.needs_ratification(fn) is False

    def test_gated_set_is_exactly_the_money_migrations(self):
        assert am.RATIFIED_REQUIRED == {
            "006_clerk_auth.sql",
            "007_idempotency_hardening.sql",
            "008_ledger_immutability.sql",
            "010_matview_refresh_out_of_band.sql",
            "011_drop_legacy_distribute_remix_royalties.sql",
            "012_pool_share_sum_constraint.sql",
        }

    def test_is_ratified_true_when_in_set(self):
        assert am.is_ratified("006_clerk_auth.sql", {"006_clerk_auth.sql"}) is True

    def test_is_ratified_false_when_not_in_set(self):
        assert am.is_ratified("006_clerk_auth.sql", {"007_idempotency_hardening.sql"}) is False

    def test_is_ratified_handles_none_set(self):
        assert am.is_ratified("006_clerk_auth.sql", None) is False

    def test_gated_file_skipped_unless_ratified(self):
        # Simulate the run() decision: a gated file with an empty ratified set is skipped.
        fn = "008_ledger_immutability.sql"
        ratified = set()
        should_apply = not (am.needs_ratification(fn) and not am.is_ratified(fn, ratified))
        assert should_apply is False

    def test_gated_file_applied_once_ratified(self):
        fn = "008_ledger_immutability.sql"
        ratified = {"008_ledger_immutability.sql"}
        should_apply = not (am.needs_ratification(fn) and not am.is_ratified(fn, ratified))
        assert should_apply is True

    def test_non_gated_file_always_applied(self):
        fn = "003_performance_indexes.sql"
        ratified = set()
        should_apply = not (am.needs_ratification(fn) and not am.is_ratified(fn, ratified))
        assert should_apply is True


# ---------------------------------------------------------------------------
# resolve_ratified_set (CLI + env)
# ---------------------------------------------------------------------------
class TestResolveRatifiedSet:
    def test_empty_inputs_give_empty_set(self):
        assert am.resolve_ratified_set([], None) == set()

    def test_cli_flag_repeatable(self):
        result = am.resolve_ratified_set(
            ["006_clerk_auth.sql", "007_idempotency_hardening.sql"], None
        )
        assert result == {"006_clerk_auth.sql", "007_idempotency_hardening.sql"}

    def test_env_comma_separated(self):
        result = am.resolve_ratified_set(
            None, "006_clerk_auth.sql, 008_ledger_immutability.sql"
        )
        assert result == {"006_clerk_auth.sql", "008_ledger_immutability.sql"}

    def test_cli_and_env_merge(self):
        result = am.resolve_ratified_set(
            ["006_clerk_auth.sql"], "007_idempotency_hardening.sql"
        )
        assert result == {"006_clerk_auth.sql", "007_idempotency_hardening.sql"}

    def test_whitespace_and_blanks_dropped(self):
        result = am.resolve_ratified_set(["  ", ""], " , 006_clerk_auth.sql ,")
        assert result == {"006_clerk_auth.sql"}


# ---------------------------------------------------------------------------
# discovery + ordering
# ---------------------------------------------------------------------------
class TestDiscoverMigrations:
    def _make_layout(self, tmp_path):
        backend = tmp_path / "backend"
        migrations = backend / "migrations"
        migrations.mkdir(parents=True)
        (backend / "database.sql").write_text("-- base\n")
        # Intentionally created out of order to prove sorting, plus a non-migration
        # doc file that must be ignored.
        (migrations / "010_z.sql").write_text("-- 010\n")
        (migrations / "002_a.sql").write_text("-- 002\n")
        (migrations / "009_y.sql").write_text("-- 009\n")
        (migrations / "APPLY_ORDER.md").write_text("# docs\n")
        (migrations / "notes.txt").write_text("ignore me\n")
        return str(backend), str(migrations)

    def test_database_sql_first(self, tmp_path):
        backend, migrations = self._make_layout(tmp_path)
        discovered = am.discover_migrations(backend, migrations)
        assert discovered[0][0] == "database.sql"

    def test_migrations_sorted_lexically(self, tmp_path):
        backend, migrations = self._make_layout(tmp_path)
        names = [fn for fn, _ in am.discover_migrations(backend, migrations)]
        assert names == ["database.sql", "002_a.sql", "009_y.sql", "010_z.sql"]

    def test_non_sql_and_docs_ignored(self, tmp_path):
        backend, migrations = self._make_layout(tmp_path)
        names = [fn for fn, _ in am.discover_migrations(backend, migrations)]
        assert "APPLY_ORDER.md" not in names
        assert "notes.txt" not in names

    def test_returns_filename_and_existing_path_pairs(self, tmp_path):
        backend, migrations = self._make_layout(tmp_path)
        for fn, fp in am.discover_migrations(backend, migrations):
            assert os.path.basename(fp) == fn
            assert os.path.exists(fp)

    def test_real_repo_layout_orders_correctly(self):
        # Against the actual backend/ dir: database.sql first, then 002..012 in order.
        discovered = am.discover_migrations()
        names = [fn for fn, _ in discovered]
        assert names[0] == "database.sql"
        migration_names = names[1:]
        assert migration_names == sorted(migration_names)
        assert "006_clerk_auth.sql" in migration_names
        assert "012_pool_share_sum_constraint.sql" in migration_names


# ---------------------------------------------------------------------------
# pending-vs-applied filter
# ---------------------------------------------------------------------------
class TestFilterPending:
    def test_drops_applied_keeps_order(self):
        discovered = [
            ("database.sql", "/x/database.sql"),
            ("002_a.sql", "/x/002_a.sql"),
            ("003_b.sql", "/x/003_b.sql"),
        ]
        applied = {"database.sql", "002_a.sql"}
        pending = am.filter_pending(discovered, applied)
        assert pending == [("003_b.sql", "/x/003_b.sql")]

    def test_nothing_applied_returns_all(self):
        discovered = [("database.sql", "/x/database.sql"), ("002_a.sql", "/x/002_a.sql")]
        assert am.filter_pending(discovered, set()) == discovered

    def test_all_applied_returns_empty(self):
        discovered = [("database.sql", "/x/database.sql"), ("002_a.sql", "/x/002_a.sql")]
        assert am.filter_pending(discovered, {"database.sql", "002_a.sql"}) == []

    def test_none_applied_set_treated_as_empty(self):
        discovered = [("database.sql", "/x/database.sql")]
        assert am.filter_pending(discovered, None) == discovered

    def test_idempotent_second_run_applies_nothing(self):
        # Model a second run: everything discovered is already in schema_migrations.
        discovered = am.discover_migrations()
        applied = {fn for fn, _ in discovered}
        assert am.filter_pending(discovered, applied) == []
