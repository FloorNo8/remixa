"""Unit tests for the cron scheduler logic (FN8-694). Pure — no DB, no subprocess."""
from datetime import date, datetime, timezone

from scripts import cron_runner


def _schedule():
    return [
        {"name": "fx", "module": "scripts.update_exchange_rates", "hour": 6, "minute": 0},
        {"name": "payouts", "module": "scripts.process_payouts", "hour": 7, "minute": 0},
    ]


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_due_at_scheduled_minute():
    due = cron_runner.due_jobs(_utc(2026, 6, 21, 6, 0), {}, _schedule())
    assert [j["name"] for j in due] == ["fx"]


def test_not_due_off_minute():
    assert cron_runner.due_jobs(_utc(2026, 6, 21, 6, 1), {}, _schedule()) == []


def test_not_due_off_hour():
    assert cron_runner.due_jobs(_utc(2026, 6, 21, 9, 0), {}, _schedule()) == []


def test_not_run_twice_same_day():
    last = {"fx": date(2026, 6, 21)}
    assert cron_runner.due_jobs(_utc(2026, 6, 21, 6, 0), last, _schedule()) == []


def test_runs_again_next_day():
    last = {"fx": date(2026, 6, 21)}
    due = cron_runner.due_jobs(_utc(2026, 6, 22, 6, 0), last, _schedule())
    assert [j["name"] for j in due] == ["fx"]


def test_resolve_schedule_env_override(monkeypatch):
    monkeypatch.setenv("CRON_PROCESS_PAYOUTS_HOUR", "9")
    monkeypatch.setenv("CRON_PROCESS_PAYOUTS_MINUTE", "30")
    sched = {j["name"]: j for j in cron_runner.resolve_schedule()}
    assert (sched["process_payouts"]["hour"], sched["process_payouts"]["minute"]) == (9, 30)


def test_all_jobs_scheduled():
    names = {j["name"] for j in cron_runner.resolve_schedule()}
    assert names == {"update_exchange_rates", "process_payouts", "update_leaderboards", "daily_challenge", "refresh_balances"}
