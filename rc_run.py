#!/usr/bin/env python3
"""RingCentralAutoSet-API — RC desktop agent via official Agent API (no Playwright)."""

from __future__ import annotations

import argparse
import logging
import sys

from rc_agent import config
from rc_agent.flow import run_action

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def cmd_test_auth(_: argparse.Namespace) -> None:
    from rc_agent.auth import fetch_token

    config.validate_credentials()
    token = fetch_token(force=True)
    print(f"OK — access token received (expires in ~{int(token.expires_at - __import__('time').time())}s)")


def cmd_show(_: argparse.Namespace) -> None:
    print(f"App:        {config.RC_APP_NAME}")
    print(f"API base:   {config.RC_API_BASE}")
    print(f"Station ID: {config.RC_STATION_ID}")
    print(f"Timezone:   {config.format_timezone()}")
    print(f"Work days:  {config.format_work_days()}")
    print(f"  Start:    {config.WORK_START} — login + Available")
    if config.LUNCH_ENABLED:
        print(f"  Lunch:    {config.LUNCH_START} → {config.LUNCH_END}")
    print(f"  End:      {config.WORK_END} — logout")
    print(f"Credentials: {'configured' if config.credentials_configured() else 'MISSING — see RC_API_SETUP.md'}")


def cmd_status(_: argparse.Namespace) -> None:
    from rc_agent import api_client
    from rc_agent.session_store import load

    sid = load()
    if not sid:
        print("No saved API session. Run: rc_run.py morning")
        return
    state = api_client.get_session_state(sid)
    print(f"Session: {sid}")
    print(f"State:   {api_client.state_label(state)}")


def cmd_schedule(_: argparse.Namespace) -> None:
    from datetime import datetime

    from apscheduler.executors.debug import DebugExecutor
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    tz = config.get_tz()
    work_days = config.get_work_days_cron()
    jobs = config.get_schedule_jobs()

    sched = BlockingScheduler(
        timezone=tz,
        executors={"default": DebugExecutor()},
        job_defaults={"misfire_grace_time": 3600, "coalesce": True},
    )

    def fire(job_action: str) -> None:
        logging.info("RC API job starting: %s", job_action)
        reason = config.skip_scheduled_job_reason()
        if reason:
            logging.info("Skipped %s — %s", job_action, reason)
            return
        try:
            run_action(job_action)
            logging.info("RC API job finished: %s", job_action)
        except Exception as exc:
            logging.exception("RC API job failed: %s — %s", job_action, exc)

    for job in jobs:
        sched.add_job(
            fire,
            CronTrigger(day_of_week=work_days, hour=job.hour, minute=job.minute, timezone=tz),
            args=[job.action],
            id=f"rc_{job.job_id}",
            name=f"RC {job.label}",
        )
        print(f"Scheduled: {job.label}")

    today_code = config.DAY_ORDER[datetime.now(tz).weekday()]
    print(f"\n{config.RC_APP_NAME} scheduler ({config.format_timezone()})")
    print(f"Uses official Agent API — desktop MAX app stays open for calls.")
    print(f"Work days: {config.format_work_days()}")
    if today_code in work_days.split(","):
        print(f"Today: work day — login at {config.WORK_START}, logout at {config.WORK_END}")
    print("Ctrl+C to stop\n")
    try:
        sched.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


def cmd_install_service(_: argparse.Namespace) -> None:
    import rc_agent.service as svc

    print("\n" + svc.install() + "\n")


def cmd_uninstall_service(_: argparse.Namespace) -> None:
    import rc_agent.service as svc

    print(svc.uninstall())


def cmd_service_status(_: argparse.Namespace) -> None:
    import rc_agent.service as svc

    print(svc.status())


def _make_action_cmd(action: str):
    def cmd(_: argparse.Namespace) -> None:
        run_action("morning" if action == "login" else action)

    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"{config.RC_APP_NAME} — RC desktop agent via official API",
        epilog="Separate from run.py (Playwright/Chrome). See RC_API_SETUP.md",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("test-auth", help="Verify API credentials").set_defaults(func=cmd_test_auth)
    sub.add_parser("show", help="Show schedule and API config").set_defaults(func=cmd_show)
    sub.add_parser("status", help="Show current API session state").set_defaults(func=cmd_status)
    sub.add_parser("schedule", help="Run scheduler (login/logout on work times)").set_defaults(func=cmd_schedule)
    sub.add_parser("install-service", help="Background scheduler on Mac login").set_defaults(func=cmd_install_service)
    sub.add_parser("uninstall-service", help="Remove background scheduler").set_defaults(func=cmd_uninstall_service)
    sub.add_parser("service-status", help="Background service status").set_defaults(func=cmd_service_status)

    for action, help_text in (
        ("morning", "Login + Available (work start)"),
        ("login", "Same as morning"),
        ("lunch", "Unavailable (Lunch)"),
        ("lunch-end", "Available after lunch"),
        ("logout", "End agent session (work end)"),
    ):
        sub.add_parser(action, help=help_text).set_defaults(func=_make_action_cmd(action))

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
