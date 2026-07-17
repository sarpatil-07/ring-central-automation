#!/usr/bin/env python3
"""RCAutoLogin — RingCX web agent automation (app.ringcentral.com)."""

from __future__ import annotations

import argparse
import logging
import sys

from rc_autologin import config
from rc_autologin.flow import run_action

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def cmd_gui(args: argparse.Namespace) -> None:
    from rc_autologin.gui import run_gui

    run_gui(open_browser=not getattr(args, "no_open_browser", False))


def cmd_install_app(_: argparse.Namespace) -> None:
    from rc_autologin import app_install as app

    print("\n" + app.install() + "\n")


def cmd_uninstall_app(_: argparse.Namespace) -> None:
    from rc_autologin import app_install as app

    print(app.uninstall())


def cmd_app_status(_: argparse.Namespace) -> None:
    from rc_autologin import app_install as app

    print(app.status())


def cmd_build_release(_: argparse.Namespace) -> None:
    from rc_autologin.release import build_release_message

    print("\n" + build_release_message() + "\n")


def cmd_menu(_: argparse.Namespace) -> None:
    from rc_autologin.menu import run_menu

    run_menu()


def cmd_show(_: argparse.Namespace) -> None:
    print(config.schedule_summary())


def cmd_schedule(_: argparse.Namespace) -> None:
    from datetime import datetime

    from apscheduler.schedulers.blocking import BlockingScheduler

    from rc_autologin.browser_worker import get_worker
    from rc_autologin.scheduler_core import make_fire, print_scheduler_banner, register_jobs, set_autorun_enabled

    config.reload_schedule()
    tz = config.get_tz()
    now = datetime.now(tz)
    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({config.format_timezone()})")

    get_worker()
    sched = BlockingScheduler(
        timezone=tz,
        job_defaults={"misfire_grace_time": 3600, "coalesce": True},
    )
    fire = make_fire()
    tz, jobs = register_jobs(sched, fire=fire)
    print_scheduler_banner(tz, jobs)
    set_autorun_enabled(True)
    try:
        sched.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
    finally:
        try:
            get_worker().session.detach(keep_browser=True)
        except Exception:
            pass
        try:
            from rc_autologin.browser_session import _stop_playwright

            _stop_playwright()
        except Exception:
            pass


def cmd_install_service(_: argparse.Namespace) -> None:
    from rc_autologin import service as svc

    print("\n" + svc.install() + "\n")


def cmd_uninstall_service(_: argparse.Namespace) -> None:
    from rc_autologin import service as svc

    print(svc.uninstall())


def cmd_service_status(_: argparse.Namespace) -> None:
    from rc_autologin import service as svc

    print(svc.status())


def _make_action_cmd(action: str):
    def cmd(_: argparse.Namespace) -> None:
        run_action("morning" if action == "login" else action)

    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"{config.APP_NAME} — RingCX web agent at app.ringcentral.com",
        epilog="RCAutoLogin only — RingCX web agent. See RC_AUTOLOGIN_SETUP.md",
    )
    sub = parser.add_subparsers(dest="command")

    gui_parser = sub.add_parser("gui", help="Desktop GUI (default)")
    gui_parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Do not open a browser tab (launch script opens it once)",
    )
    gui_parser.set_defaults(func=cmd_gui)
    sub.add_parser("menu", help="Text menu (CLI)").set_defaults(func=cmd_menu)
    sub.add_parser("show", help="Show schedule").set_defaults(func=cmd_show)
    sub.add_parser("schedule", help="Run scheduler in terminal").set_defaults(func=cmd_schedule)
    sub.add_parser("install-service", help="Start background scheduler (Mac/Linux)").set_defaults(
        func=cmd_install_service
    )
    sub.add_parser("uninstall-service", help="Stop background job").set_defaults(
        func=cmd_uninstall_service
    )
    sub.add_parser("service-status", help="Background job status").set_defaults(
        func=cmd_service_status
    )
    sub.add_parser("install-app", help="Install RCAutoLogin.app in ~/Applications").set_defaults(
        func=cmd_install_app
    )
    sub.add_parser("uninstall-app", help="Remove RCAutoLogin.app from ~/Applications").set_defaults(
        func=cmd_uninstall_app
    )
    sub.add_parser("app-status", help="Dock app install status").set_defaults(func=cmd_app_status)
    sub.add_parser(
        "build-release",
        help="Create shareable zip for Mac/Linux (dist/RCAutoLogin-*-portable.zip)",
    ).set_defaults(func=cmd_build_release)

    for action, help_text in (
        ("morning", "Agent → Start session → AVAILABLE"),
        ("login", "Same as morning"),
        ("lunch", "Set Lunch/Dinner status"),
        ("break", "Set Break status"),
        ("lunch-end", "Set AVAILABLE (back from break or lunch)"),
        ("logout", "Stop session"),
    ):
        sub.add_parser(action, help=help_text).set_defaults(func=_make_action_cmd(action))

    args = parser.parse_args()
    if args.command is None:
        cmd_gui(argparse.Namespace(no_open_browser=False))
        return 0
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
