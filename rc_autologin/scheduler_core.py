"""Shared APScheduler setup for RCAutoLogin (terminal + GUI background)."""

from __future__ import annotations

import fcntl
import logging
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from rc_autologin import config
from rc_autologin.job_run_state import (
    canonical_action,
    job_ran_today,
    mark_job_ran,
    scheduled_time_for,
)
from rc_autologin.schedule_util import get_rcx_schedule_jobs, job_run_note, print_schedule_warnings

JOB_LOCK_FILE = config.USER_HOME / "schedule-job.lock"
AUTORUN_FLAG = config.USER_HOME / "autorun.enabled"
AUTORUN_DISABLED = config.USER_HOME / "autorun.disabled"

_job_log: Callable[[str], None] | None = None


def set_job_log_callback(callback: Callable[[str], None] | None) -> None:
    global _job_log
    _job_log = callback


def _emit(msg: str) -> None:
    logging.info(msg)
    if _job_log is not None:
        try:
            _job_log(msg)
        except Exception:
            pass


def autorun_enabled() -> bool:
    """True when user turned on background automation."""
    from rc_autologin import service as rcx_service

    if user_stopped_scheduler():
        return False
    return AUTORUN_FLAG.exists() or rcx_service.plist_path().exists()


def user_stopped_scheduler() -> bool:
    return AUTORUN_DISABLED.exists()


def mark_scheduler_stopped() -> None:
    config.USER_HOME.mkdir(parents=True, exist_ok=True)
    AUTORUN_DISABLED.touch()
    set_autorun_enabled(False)


def mark_scheduler_started() -> None:
    config.USER_HOME.mkdir(parents=True, exist_ok=True)
    if AUTORUN_DISABLED.exists():
        AUTORUN_DISABLED.unlink()
    set_autorun_enabled(True)


def ensure_persistent_scheduler() -> tuple[bool, str]:
    """LaunchAgent/systemd scheduler — keeps running after GUI closes."""
    from rc_autologin import service as rcx_service

    if user_stopped_scheduler():
        return False, "Scheduler disabled."
    try:
        if hasattr(rcx_service, "is_running") and rcx_service.is_running():
            return True, "Background scheduler already running."
        if rcx_service.plist_path().exists():
            msg = rcx_service.restart()
        else:
            msg = rcx_service.install()
        ok = (
            rcx_service.is_running()
            if hasattr(rcx_service, "is_running")
            else rcx_service.plist_path().exists()
        )
        summary = msg.strip().split("\n")[0] if msg else "Background scheduler started."
        return ok, summary
    except Exception as exc:
        return False, str(exc)


def set_autorun_enabled(enabled: bool) -> None:
    config.USER_HOME.mkdir(parents=True, exist_ok=True)
    if enabled:
        AUTORUN_FLAG.touch(exist_ok=True)
    elif AUTORUN_FLAG.exists():
        AUTORUN_FLAG.unlink()


def today_is_work_day() -> bool:
    tz = config.get_tz()
    today = config.DAY_ORDER[datetime.now(tz).weekday()]
    return today in config.get_work_days_cron().split(",")


def _job_run_at(job, now: datetime) -> datetime:
    return now.replace(hour=job.hour, minute=job.minute, second=0, microsecond=0)


def _work_bounds(now: datetime) -> tuple[datetime, datetime]:
    import config as parent_config

    ws_h, ws_m = parent_config.parse_time(config.WORK_START, "WORK_START")
    we_h, we_m = parent_config.parse_time(config.WORK_END, "WORK_END")
    work_start = now.replace(hour=ws_h, minute=ws_m, second=0, microsecond=0)
    work_end = now.replace(hour=we_h, minute=we_m, second=0, microsecond=0)
    return work_start, work_end


def _in_catchup_window(job, now: datetime) -> bool:
    """Whether a past-due job should still run today (late login / wake from sleep)."""
    import config as parent_config

    action = canonical_action(job.action)
    work_start, work_end = _work_bounds(now)

    if action == "morning":
        return work_start <= now < work_end
    if action == "lunch" and config.LUNCH_ENABLED:
        ls_h, ls_m = parent_config.parse_time(config.LUNCH_START, "LUNCH_START")
        le_h, le_m = parent_config.parse_time(config.LUNCH_END, "LUNCH_END")
        lunch_start = now.replace(hour=ls_h, minute=ls_m, second=0, microsecond=0)
        lunch_end = now.replace(hour=le_h, minute=le_m, second=0, microsecond=0)
        return lunch_start <= now < lunch_end
    if action == "lunch-end" and config.LUNCH_ENABLED:
        le_h, le_m = parent_config.parse_time(config.LUNCH_END, "LUNCH_END")
        lunch_end = now.replace(hour=le_h, minute=le_m, second=0, microsecond=0)
        return lunch_end <= now < work_end
    if action == "logout":
        return work_end <= now <= work_end + timedelta(hours=3)
    return False


def run_missed_jobs(fire: Callable[[str], None], *, reason: str = "catch-up") -> int:
    """Run today's jobs that were missed (laptop off/asleep or logged in after schedule time)."""
    config.reload_schedule()
    if not today_is_work_day():
        return 0
    if config.skip_scheduled_job_reason():
        return 0

    tz = config.get_tz()
    now = datetime.now(tz)
    jobs = get_rcx_schedule_jobs()
    ran = 0

    for job in jobs:
        action = canonical_action(job.action)
        slot = f"{job.hour:02d}:{job.minute:02d}"
        if job_ran_today(action, scheduled_time=slot):
            continue
        run_at = _job_run_at(job, now)
        if run_at > now:
            continue
        if not _in_catchup_window(job, now):
            continue
        _emit(
            f"→ Missed job {reason}: {action} "
            f"(scheduled {slot}, now {now.strftime('%H:%M')})…"
        )
        fire(job.action)
        ran += 1

    return ran


def scheduler_status() -> dict[str, Any]:
    """Summary for GUI — why jobs may not run today."""
    config.reload_schedule()
    tz = config.get_tz()
    now = datetime.now(tz)
    today = config.DAY_ORDER[now.weekday()]
    work_days = config.get_work_days_cron().split(",")
    active_today = today in work_days
    jobs = get_rcx_schedule_jobs()
    upcoming: list[str] = []
    passed: list[str] = []
    for job in jobs:
        run_at = now.replace(hour=job.hour, minute=job.minute, second=0, microsecond=0)
        label = f"{job.hour:02d}:{job.minute:02d} {job.action}"
        if run_at > now:
            upcoming.append(label)
        else:
            passed.append(label)

    note = ""
    if not active_today:
        note = (
            f"Today is {config.DAY_LABELS[today]} — not in your work days "
            f"({config.format_work_days()}). Jobs will NOT run until the next work day. "
            f"For weekend testing, set Work days to Every day or Today only."
        )
    elif passed:
        catchup_pending = any(
            _job_run_at(job, now) <= now
            and not job_ran_today(job.action, scheduled_time=f"{job.hour:02d}:{job.minute:02d}")
            and _in_catchup_window(job, now)
            for job in jobs
        )
        if catchup_pending:
            note = (
                "Some jobs passed their scheduled time — catch-up will run them automatically "
                "(on Mac login or within a few minutes if the background job is running)."
            )
        elif not upcoming:
            note = "All scheduled times already passed today — next jobs run on the next work day."

    return {
        "today": config.DAY_LABELS[today],
        "today_code": today,
        "today_active": active_today,
        "now": now.strftime("%H:%M"),
        "upcoming_today": upcoming,
        "passed_today": passed,
        "note": note,
    }


@contextmanager
def _job_lock():
    """Prevent two schedulers (LaunchAgent + GUI) from running the same job."""
    config.USER_HOME.mkdir(parents=True, exist_ok=True)
    lock_path = JOB_LOCK_FILE
    with lock_path.open("w") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _emit("Skipped scheduled job — another scheduler instance is already running it.")
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def make_fire() -> Callable[[str], None]:
    """Return APScheduler callback — always routes Playwright via browser_worker thread."""

    def fire(job_action: str) -> None:
        with _job_lock() as acquired:
            if not acquired:
                return
            config.reload_schedule()
            action = "morning" if job_action == "login" else job_action
            slot = scheduled_time_for(action)
            if job_ran_today(action, scheduled_time=slot):
                _emit(f"Skipped {action} — already ran today at schedule {slot}.")
                return
            _emit(f"→ Scheduled job: {action} (schedule {slot})…")
            reason = config.skip_scheduled_job_reason()
            if reason:
                _emit(f"Skipped {action} — {reason}")
                return
            if not today_is_work_day():
                _emit(
                    f"Skipped {action} — today is not a configured work day "
                    f"({config.format_work_days()})."
                )
                return
            try:
                from rc_autologin.browser_worker import get_worker, run_action as worker_run_action

                get_worker()  # ensure Playwright worker thread exists
                worker_run_action(action)
                mark_job_ran(action, scheduled_time=slot)
                _emit(f"✓ Scheduled job done: {action}")
            except Exception as exc:
                _emit(f"✗ Scheduled job failed ({action}): {exc}")
                logging.exception("Scheduled job failed: %s", exc)

    return fire


def register_jobs(sched: BaseScheduler, *, fire: Callable[[str], None]) -> tuple[Any, list]:
    config.reload_schedule()
    tz = config.get_tz()
    work_days = config.get_work_days_cron()
    jobs = get_rcx_schedule_jobs()
    now = datetime.now(tz)
    print_schedule_warnings(jobs, tz=tz, work_days=work_days)
    status = scheduler_status()
    if status["note"]:
        print(f"⚠ {status['note']}")

    for job in jobs:
        sched.add_job(
            fire,
            CronTrigger(day_of_week=work_days, hour=job.hour, minute=job.minute, timezone=tz),
            args=[job.action],
            id=f"rcx_{job.job_id}",
            name=f"RCAutoLogin {job.label}",
            replace_existing=True,
        )
        note = job_run_note(job, tz=tz, work_days=work_days, now=now)
        print(f"Scheduled: {job.label}  ({note})")

    missed = run_missed_jobs(fire, reason="on startup")
    if missed:
        print(f"Catch-up: started {missed} missed job(s) for today.")

    sched.add_job(
        lambda: run_missed_jobs(fire, reason="delayed startup"),
        DateTrigger(run_date=now + timedelta(seconds=45), timezone=tz),
        id="rcx_delayed_catchup",
        name="RCAutoLogin delayed catch-up",
        replace_existing=True,
    )

    sched.add_job(
        lambda: run_missed_jobs(fire, reason="watchdog"),
        IntervalTrigger(minutes=2, timezone=tz),
        id="rcx_missed_job_watchdog",
        name="RCAutoLogin missed-job watchdog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    print("Missed-job watchdog: checks every 2 minutes (late login / wake from sleep).")

    return tz, jobs


def print_scheduler_banner(tz, jobs: list) -> None:
    today = config.DAY_ORDER[datetime.now(tz).weekday()]
    work_days = config.get_work_days_cron()
    print(f"\n{config.APP_NAME} ({config.format_timezone()})")
    print(f"URL: {config.RCX_AGENT_URL}")
    print(f"Work days: {config.format_work_days()}")
    print(f"Times: start {config.WORK_START}, end {config.WORK_END}", end="")
    if config.LUNCH_ENABLED:
        print(f", lunch {config.LUNCH_START}–{config.LUNCH_END}")
    else:
        print()
    if today in work_days.split(","):
        print("Waiting for next scheduled job (missed jobs catch up on login / every 2 min)…")
    else:
        print(f"Note: {config.DAY_LABELS[today]} is not a work day — no jobs until next work day.")
    print("Scheduled jobs continue after you close the GUI (LaunchAgent background job).")
    print("")
