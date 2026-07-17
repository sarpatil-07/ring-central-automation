"""Schedule helpers — reload .env and RCAutoLogin job labels."""

from __future__ import annotations

import os
from datetime import datetime

import config as parent_config
from config import ScheduleJob
from rc_autologin.job_run_state import job_ran_today


def reload_schedule() -> None:
    """Refresh schedule values from .env (after menu saves)."""
    from dotenv import load_dotenv

    from rc_autologin import config as rcx_config

    load_dotenv(rcx_config.ENV_FILE, override=True)

    parent_config.load_dotenv(override=True)

    rcx_config.TIMEZONE = parent_config.TIMEZONE
    rcx_config.WORK_START = parent_config.WORK_START
    rcx_config.WORK_END = parent_config.WORK_END
    rcx_config.LUNCH_START = parent_config.LUNCH_START
    rcx_config.LUNCH_END = parent_config.LUNCH_END
    rcx_config.LUNCH_ENABLED = parent_config.LUNCH_ENABLED
    rcx_config.WORK_DAYS = parent_config.WORK_DAYS
    rcx_config.AUTORUN_PAUSED = parent_config.AUTORUN_PAUSED
    rcx_config.LEAVE_DATE = parent_config.LEAVE_DATE
    rcx_config.RCX_LOGIN_ID = os.getenv("RCX_LOGIN_ID", "").strip()
    rcx_config.RCX_LOGIN_PASSWORD = os.getenv("RCX_LOGIN_PASSWORD", "")
    rcx_config.RCX_AUTO_LOGIN_ENABLED = os.getenv("RCX_AUTO_LOGIN_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }


def save_env_updates(updates: dict[str, str]) -> None:
    """Write keys to .env and reload in-memory schedule + login settings."""
    parent_config.save_env(updates)
    reload_schedule()


def get_rcx_schedule_jobs() -> list[ScheduleJob]:
    reload_schedule()
    raw = parent_config.get_schedule_jobs()
    labels = {
        "morning": f"{parent_config.WORK_START} login + Start session + AVAILABLE",
        "lunch": f"{parent_config.LUNCH_START} Lunch/Dinner",
        "lunch-end": f"{parent_config.LUNCH_END} Back (AVAILABLE)",
        "logout": f"{parent_config.WORK_END} Stop session",
    }
    out: list[ScheduleJob] = []
    for job in raw:
        out.append(
            ScheduleJob(
                job.job_id,
                labels.get(job.action, job.label),
                job.hour,
                job.minute,
                job.action,
            )
        )
    return out


def job_run_note(job: ScheduleJob, *, tz, work_days: str, now: datetime | None = None) -> str:
    now = now or datetime.now(tz)
    today_code = parent_config.DAY_ORDER[now.weekday()]
    if today_code not in work_days.split(","):
        return "next work day"
    run_at = now.replace(hour=job.hour, minute=job.minute, second=0, microsecond=0)
    if run_at <= now:
        slot = f"{job.hour:02d}:{job.minute:02d}"
        if not job_ran_today(job.action, scheduled_time=slot):
            return f"passed {slot} — catch-up may still run today"
        return f"done today ({slot})"
    return f"runs today at {job.hour:02d}:{job.minute:02d}"


def print_schedule_warnings(jobs: list[ScheduleJob], *, tz, work_days: str) -> None:
    now = datetime.now(tz)
    today_code = parent_config.DAY_ORDER[now.weekday()]
    if today_code not in work_days.split(","):
        print("Note: today is not a configured work day — jobs wait for the next work day.")
        return

    passed = []
    upcoming = []
    for job in jobs:
        run_at = now.replace(hour=job.hour, minute=job.minute, second=0, microsecond=0)
        if run_at <= now:
            passed.append(job)
        else:
            upcoming.append(job)

    if passed and not upcoming:
        print("")
        print("⚠ All job times already passed today.")
        print("  Catch-up runs missed jobs when you log in (if still within work hours).")
        print("  Or run manually: menu → m (login), l (lunch), g (logout)")
        print("")
        for job in passed:
            print(f"    passed: {job.label}")
    elif passed:
        print("")
        print("⚠ Some jobs already passed — catch-up runs them if still in today's window:")
        for job in passed:
            print(f"    {job.hour:02d}:{job.minute:02d} — {job.action}")
        print("  Upcoming today:")
        for job in upcoming:
            print(f"    {job.hour:02d}:{job.minute:02d} — {job.action}")
        print("")
