#!/usr/bin/env python3
"""RingCentralAutoSet — configure once, runs on schedule."""

from __future__ import annotations

import argparse
import logging
import sys

import config
from browser_session import MaxBrowserSession
from max_flow import run_action

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def cmd_configure(_: argparse.Namespace) -> None:
    from schedule_menu import change_all_times

    print("\n=== Setup / change shift times ===\n")
    station = input(f"Station ID [{config.STATION_ID}]: ").strip() or config.STATION_ID
    config.save_env({"STATION_ID": station})
    change_all_times()


def cmd_show(_: argparse.Namespace) -> None:
    print(config.schedule_summary())


def cmd_menu(_: argparse.Namespace) -> None:
    from schedule_menu import run_menu

    run_menu()


def cmd_reset_browser(_: argparse.Namespace) -> None:
    from browser_recovery import reset_max_browser

    print(reset_max_browser(force=True))


def cmd_clear_session(_: argparse.Namespace) -> None:
    from browser_recovery import clear_saved_login

    print(clear_saved_login())
    print("Next morning run will ask for OTP in MAX Chrome.")


def cmd_install_service(_: argparse.Namespace) -> None:
    import service

    print("\n" + service.install() + "\n")


def cmd_uninstall_service(_: argparse.Namespace) -> None:
    import service

    print(service.uninstall())


def cmd_service_status(_: argparse.Namespace) -> None:
    import service

    print(service.status())


def cmd_schedule(_: argparse.Namespace) -> None:
    from datetime import datetime

    from apscheduler.executors.debug import DebugExecutor
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    import ui_actions as ui

    tz = config.get_tz()
    work_days = config.get_work_days_cron()
    jobs = config.get_schedule_jobs()
    sched = BlockingScheduler(
        timezone=tz,
        executors={"default": DebugExecutor()},
        job_defaults={"misfire_grace_time": 3600, "coalesce": True},
    )
    session = MaxBrowserSession()

    def fire(job_action: str) -> None:
        logging.info("Scheduled job starting: %s", job_action)
        reason = config.skip_scheduled_job_reason()
        if reason:
            logging.info("Skipped %s — %s", job_action, reason)
            return
        try:
            run_action(job_action, session=session)
            if job_action == "logout":
                session.shutdown_for_day()
                logging.info(
                    "Shift complete — browser closed. Next work start: %s (%s)",
                    config.WORK_START,
                    config.format_work_days(),
                )
            else:
                logging.info("Scheduled job finished: %s (MAX browser kept open)", job_action)
        except Exception as exc:
            if job_action == "logout" and ui.is_target_closed_error(exc):
                logging.info("Logout completed — MAX closed during confirm.")
                session.shutdown_for_day()
                return
            logging.exception("Job failed: %s — %s", job_action, exc)

    for job in jobs:
        sched.add_job(
            fire,
            CronTrigger(day_of_week=work_days, hour=job.hour, minute=job.minute, timezone=tz),
            args=[job.action],
            id=job.job_id,
            name=job.label,
        )
        print(f"Scheduled: {job.label}")

    today_code = config.DAY_ORDER[datetime.now(tz).weekday()]
    today_is_work_day = today_code in work_days.split(",")

    print(f"\n{config.APP_NAME} scheduler running ({config.format_timezone()}). Mac must be awake.")
    print(f"Work days: {config.format_work_days()}")
    print(f"  {config.WORK_START} — connect + Available (OTP if needed)")
    if config.LUNCH_ENABLED:
        print(f"  {config.LUNCH_START} — Lunch   {config.LUNCH_END} — Available")
    print(f"  {config.WORK_END} — Logout + close browser")
    if today_is_work_day:
        print(f"Today is a work day — MAX browser opens at {config.WORK_START}.")
    else:
        print(
            f"Note: today ({config.DAY_LABELS[today_code]}) is not a work day — "
            "idle until the next configured day."
        )
    print("Install once for auto-start on login: python run.py install-service")
    print("Change shift times when they change: python run.py menu\n")
    try:
        sched.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped (MAX browser left open).")
        session.detach()


def _make_action_cmd(action: str):
    def cmd(_: argparse.Namespace) -> None:
        run_action(action)

    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"{config.APP_NAME} — Ring Central / NICE MAX automation",
        epilog="Run without arguments to open the interactive menu.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("menu", help="Interactive menu — change work/lunch times any day").set_defaults(
        func=cmd_menu
    )
    sub.add_parser("configure", help="Set station ID and shift times").set_defaults(func=cmd_configure)
    sub.add_parser("show", help="Show current schedule").set_defaults(func=cmd_show)
    sub.add_parser(
        "reset-browser",
        help="Stop stuck MAX Chrome (keeps saved login)",
    ).set_defaults(func=cmd_reset_browser)
    sub.add_parser(
        "clear-session",
        help="Delete saved SSO session — OTP required next run",
    ).set_defaults(func=cmd_clear_session)
    sub.add_parser("schedule", help="Run scheduler on configured work days").set_defaults(func=cmd_schedule)
    sub.add_parser(
        "install-service",
        help="Install background scheduler (auto-start on Mac login)",
    ).set_defaults(func=cmd_install_service)
    sub.add_parser(
        "uninstall-service",
        help="Remove background scheduler",
    ).set_defaults(func=cmd_uninstall_service)
    sub.add_parser("service-status", help="Show background scheduler status").set_defaults(
        func=cmd_service_status
    )

    for action in ("morning", "lunch", "lunch-end", "logout"):
        sub.add_parser(action, help=f"Run {action} now").set_defaults(func=_make_action_cmd(action))

    args = parser.parse_args()
    if args.command is None:
        cmd_menu(argparse.Namespace())
        return 0

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
