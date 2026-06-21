"""
scripts.cron_runner — entrypoint for the Fly `cron` process (fly.toml [processes] cron).

FN8-694: fly.toml runs `python -m scripts.cron_runner`, but the module didn't exist, so the
cron machine crash-looped and the scheduled jobs never ran. This is that module.

Each job is a standalone module with a `main()`, invoked via `python -m scripts.<name>` in a
subprocess so a failure is isolated (a crashing job must not kill the scheduler). Daily
cadence by default; override per job via env, e.g. CRON_PROCESS_PAYOUTS_HOUR / _MINUTE (UTC).

Run modes:
  python -m scripts.cron_runner          # long-running scheduler loop (the Fly cron process)
  python -m scripts.cron_runner --once   # run every job once and exit (manual / smoke)
  python -m scripts.cron_runner --list   # print the resolved schedule and exit
"""
import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s cron_runner %(levelname)s %(message)s",
)
log = logging.getLogger("cron_runner")

# Default daily schedule (UTC). FX before payouts so payout conversions use fresh rates.
JOBS = [
    {"name": "update_exchange_rates", "module": "scripts.update_exchange_rates", "hour": 6, "minute": 0},
    {"name": "process_payouts",       "module": "scripts.process_payouts",       "hour": 7, "minute": 0},
    {"name": "update_leaderboards",   "module": "scripts.update_leaderboards",   "hour": 5, "minute": 0},
    {"name": "daily_challenge",       "module": "scripts.daily_challenge",       "hour": 0, "minute": 5},
]

POLL_SECONDS = 30
JOB_TIMEOUT_SECONDS = 600


def _app_dir():
    """App root (parent of scripts/), so `python -m scripts.<name>` resolves."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resolve_schedule():
    """Build the schedule, applying per-job env overrides (CRON_<NAME>_HOUR / _MINUTE)."""
    schedule = []
    for job in JOBS:
        key = job["name"].upper()
        schedule.append({
            "name": job["name"],
            "module": job["module"],
            "hour": int(os.getenv(f"CRON_{key}_HOUR", job["hour"])),
            "minute": int(os.getenv(f"CRON_{key}_MINUTE", job["minute"])),
        })
    return schedule


def due_jobs(now, last_run, schedule):
    """
    Pure: jobs whose (hour, minute) matches `now` (a UTC datetime) and that have not already
    run today. `last_run` maps job name -> the date it last ran. No side effects.
    """
    today = now.date()
    return [
        job for job in schedule
        if now.hour == job["hour"]
        and now.minute == job["minute"]
        and last_run.get(job["name"]) != today
    ]


def run_job(job):
    """Run a job as `python -m <module>` in a subprocess. Never raises — returns an exit code."""
    log.info("running job %s (%s)", job["name"], job["module"])
    try:
        result = subprocess.run(
            [sys.executable, "-m", job["module"]],
            cwd=_app_dir(),
            timeout=JOB_TIMEOUT_SECONDS,
        )
        log.info("job %s exited %s", job["name"], result.returncode)
        return result.returncode
    except Exception as exc:  # isolate: a failing job must not stop the scheduler
        log.error("job %s crashed: %s", job["name"], exc)
        return -1


def run_once(schedule=None):
    for job in (schedule or resolve_schedule()):
        run_job(job)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    schedule = resolve_schedule()

    if "--list" in argv:
        for job in schedule:
            print(f"{job['name']:24} {job['hour']:02d}:{job['minute']:02d} UTC  ({job['module']})")
        return 0

    if "--once" in argv:
        run_once(schedule)
        return 0

    log.info(
        "cron_runner starting; schedule: %s",
        ", ".join(f"{j['name']}@{j['hour']:02d}:{j['minute']:02d}" for j in schedule),
    )
    last_run = {}
    while True:
        now = datetime.now(timezone.utc)
        for job in due_jobs(now, last_run, schedule):
            run_job(job)
            last_run[job["name"]] = now.date()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
