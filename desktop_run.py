#!/usr/bin/env python3
"""RingCentralAutoSet-Desktop — RingCentral.app via macOS Accessibility."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rc_desktop import ax_ui, config
from rc_desktop.flow import run_action
from rc_desktop.labels import app_process, load_labels

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def cmd_test_access(_: argparse.Namespace) -> None:
    print("Step 1: Checking macOS Accessibility permission…")
    ax_ui.verify_accessibility_permission()
    print("  ✓ Accessibility OK")

    preferred = app_process(load_labels())
    print(f"Step 2: Finding RingCentral process (configured: {preferred})…")
    proc = ax_ui.resolve_process_name(preferred)
    print(f"  ✓ Using process: {proc}")

    ax_ui.activate_app(proc)
    print(f"\nOK — ready to automate RingCentral ({proc})")


def cmd_discover(_: argparse.Namespace) -> None:
    print("Checking Accessibility…")
    try:
        ax_ui.verify_accessibility_permission()
    except ax_ui.AccessibilityDeniedError as exc:
        print(exc)
        return

    print("\nRunning processes matching RingCentral:")
    matches = ax_ui.list_matching_processes("ring", "RingCentral", "RingEX")
    if not matches:
        print("  (none found — open RingCentral.app first)")
        print("\nTry: open -a RingCentral")
        return
    for name in matches:
        print(f"  - {name}")

    best = ax_ui.pick_best_process(matches)
    print(f"\nRecommended RC_APP_PROCESS={best}")
    print(f"Add to .env:  RC_APP_PROCESS={best}")


def cmd_open_accessibility_settings(_: argparse.Namespace) -> None:
    ax_ui.open_accessibility_settings()
    print(ax_ui.accessibility_help())


def cmd_search(args: argparse.Namespace) -> None:
    preferred = app_process(load_labels())
    proc = ax_ui.resolve_process_name(preferred)
    query = args.query
    print(f"Searching '{query}' in {proc}…\n")
    ax_ui.activate_app(proc)
    text = ax_ui.search_ui(proc, query)
    if not text.strip():
        print("(no matches — open Agent tab in RingCentral, then try again)")
        return
    print(text)
    out = config.BASE_DIR / "logs" / f"desktop-search-{query.replace(' ', '_')}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\nSaved: {out}")


def cmd_show(_: argparse.Namespace) -> None:
    labels = load_labels()
    print(f"App:         {config.DESKTOP_APP_NAME}")
    print(f"RC process:  {app_process(labels)}")
    print(f"Labels file: {config.LABELS_FILE}")
    print(f"Timezone:    {config.format_timezone()}")
    print(f"Work days:   {config.format_work_days()}")
    print(f"  Start:     {config.WORK_START} — Agent tab → Start working → Available")
    if config.LUNCH_ENABLED:
        print(f"  Lunch:     {config.LUNCH_START} → {config.LUNCH_END}")
    print(f"  End:       {config.WORK_END} — Stop working")
    print(f"Connect wait: {config.CONNECT_WAIT_SECONDS}s")


def cmd_inspect(_: argparse.Namespace) -> None:
    preferred = app_process(load_labels())
    print(f"Resolving process (configured: {preferred})…")
    proc = ax_ui.resolve_process_name(preferred)
    print(f"Inspecting UI for process: {proc}")
    print("Open the Agent tab in RingCentral first, then wait…\n")
    ax_ui.activate_app(proc)
    text = ax_ui.inspect_ui(proc)
    out = config.BASE_DIR / "logs" / "desktop-ui-inspect.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text[:8000])
    if len(text) > 8000:
        print(f"\n… truncated. Full output: {out}")
    else:
        print(f"\nSaved: {out}")
    print("\nEdit rc_desktop/labels.yaml if button names differ from defaults.")


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
        logging.info("Desktop job starting: %s", job_action)
        reason = config.skip_scheduled_job_reason()
        if reason:
            logging.info("Skipped %s — %s", job_action, reason)
            return
        try:
            run_action(job_action)
            logging.info("Desktop job finished: %s", job_action)
        except Exception as exc:
            logging.exception("Desktop job failed: %s — %s", job_action, exc)

    for job in jobs:
        sched.add_job(
            fire,
            CronTrigger(day_of_week=work_days, hour=job.hour, minute=job.minute, timezone=tz),
            args=[job.action],
            id=f"desktop_{job.job_id}",
            name=f"Desktop {job.label}",
        )
        print(f"Scheduled: {job.label}")

    today_code = config.DAY_ORDER[datetime.now(tz).weekday()]
    print(f"\n{config.DESKTOP_APP_NAME} ({config.format_timezone()})")
    print("Uses macOS Accessibility — RingCentral.app must stay open and logged in.")
    print(f"Work days: {config.format_work_days()}")
    if today_code in work_days.split(","):
        print(f"Today: work day — start {config.WORK_START}, end {config.WORK_END}")
    print("Ctrl+C to stop\n")
    try:
        sched.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


def cmd_install_service(_: argparse.Namespace) -> None:
    import rc_desktop.service as svc

    print("\n" + svc.install() + "\n")


def cmd_uninstall_service(_: argparse.Namespace) -> None:
    import rc_desktop.service as svc

    print(svc.uninstall())


def cmd_service_status(_: argparse.Namespace) -> None:
    import rc_desktop.service as svc

    print(svc.status())


def _make_action_cmd(action: str):
    def cmd(_: argparse.Namespace) -> None:
        run_action("morning" if action == "login" else action)

    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"{config.DESKTOP_APP_NAME} — automate RingCentral.app (no API, no browser)",
        epilog="Separate from run.py and rc_run.py. See DESKTOP_SETUP.md",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("test-access", help="Verify Accessibility + RingCentral is running").set_defaults(
        func=cmd_test_access
    )
    sub.add_parser("discover", help="Find RingCentral process name on this Mac").set_defaults(
        func=cmd_discover
    )
    sub.add_parser(
        "open-accessibility-settings",
        help="Open System Settings → Accessibility",
    ).set_defaults(func=cmd_open_accessibility_settings)
    sub.add_parser("show", help="Show schedule and desktop config").set_defaults(func=cmd_show)
    sub.add_parser("inspect", help="Dump UI element names (tune labels.yaml)").set_defaults(func=cmd_inspect)
    search_p = sub.add_parser("search", help="Find UI text (e.g. search agent)")
    search_p.add_argument("query", help="Text to search in UI")
    search_p.set_defaults(func=cmd_search)
    sub.add_parser("schedule", help="Run scheduler in this terminal").set_defaults(func=cmd_schedule)
    sub.add_parser("install-service", help="Background scheduler on Mac login").set_defaults(
        func=cmd_install_service
    )
    sub.add_parser("uninstall-service", help="Remove background scheduler").set_defaults(
        func=cmd_uninstall_service
    )
    sub.add_parser("service-status", help="Check background service").set_defaults(func=cmd_service_status)

    for action, help_text in (
        ("morning", "Agent tab → Start working → Available"),
        ("login", "Same as morning"),
        ("lunch", "Set Unavailable (Lunch)"),
        ("lunch-end", "Set Available"),
        ("logout", "Stop working"),
    ):
        sub.add_parser(action, help=help_text).set_defaults(func=_make_action_cmd(action))

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    try:
        args.func(args)
    except ax_ui.AccessibilityDeniedError as exc:
        print(exc, file=sys.stderr)
        return 1
    except ax_ui.DesktopUIError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
