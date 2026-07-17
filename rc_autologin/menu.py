"""Interactive menu for RCAutoLogin — schedule, actions, background service."""

from __future__ import annotations

import argparse
from datetime import datetime

import config as parent_config
from rc_autologin import config
from rc_autologin import service as rcx_service
from rc_autologin.browser_session import RcxBrowserSession
from rc_autologin.flow import run_action


def _prompt_time(label: str, current: str) -> str:
    while True:
        value = input(f"{label} [{current}]: ").strip() or current
        try:
            parent_config.parse_time(value, label)
            return value
        except ValueError as exc:
            print(f"  Invalid: {exc}")


def save_schedule(updates: dict[str, str]) -> tuple[bool, str]:
    """Validate, save .env, restart service if installed. Returns (ok, message)."""
    try:
        if "WORK_DAYS" in updates:
            updates["WORK_DAYS"] = parent_config.parse_work_days(updates["WORK_DAYS"])
        merged = {
            "TIMEZONE": config.TIMEZONE,
            "WORK_DAYS": config.WORK_DAYS,
            "WORK_START": config.WORK_START,
            "WORK_END": config.WORK_END,
            "LUNCH_ENABLED": "true" if config.LUNCH_ENABLED else "false",
            "LUNCH_START": config.LUNCH_START,
            "LUNCH_END": config.LUNCH_END,
            "AUTORUN_PAUSED": "true" if config.AUTORUN_PAUSED else "false",
            "LEAVE_DATE": config.LEAVE_DATE,
        }
        merged.update(updates)
        parent_config.get_schedule_jobs(
            work_start=merged["WORK_START"],
            work_end=merged["WORK_END"],
            lunch_start=merged["LUNCH_START"],
            lunch_end=merged["LUNCH_END"],
            lunch_enabled=merged["LUNCH_ENABLED"].lower() in {"1", "true", "yes"},
        )
        parent_config.save_env(updates)
        config.reload_schedule()
        # Changing times must allow the new schedule to fire today.
        from rc_autologin.job_run_state import clear_today_runs

        clear_today_runs()
        msg = "Schedule saved (job run markers cleared for re-test)."
        if rcx_service.plist_path().exists():
            msg += " " + rcx_service.restart()
        else:
            msg += " Start background job to auto-run on these times."
        return True, msg
    except ValueError as exc:
        return False, str(exc)


def _env_safe_value(value: str) -> str:
    if any(c in value for c in '=#"\n\t'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def save_credentials(
    *,
    login_id: str,
    password: str | None,
    auto_login: bool,
) -> tuple[bool, str]:
    """Save RingCentral login credentials to .env (local only)."""
    login_id = login_id.strip()
    if auto_login and not login_id:
        return False, "Login ID (email) is required when auto login is enabled."
    if auto_login and not password and not config.RCX_LOGIN_PASSWORD:
        return False, "Password is required when auto login is enabled."

    updates: dict[str, str] = {
        "RCX_LOGIN_ID": login_id,
        "RCX_AUTO_LOGIN_ENABLED": "true" if auto_login else "false",
    }
    if password:
        updates["RCX_LOGIN_PASSWORD"] = _env_safe_value(password)

    try:
        from rc_autologin.schedule_util import save_env_updates

        save_env_updates(updates)
        msg = "Login saved (one-time per user — stored in local .env)."
        if rcx_service.plist_path().exists():
            msg += " " + rcx_service.restart()
        return True, msg
    except ValueError as exc:
        return False, str(exc)


def _save_and_show(updates: dict[str, str]) -> None:
    ok, msg = save_schedule(updates)
    if ok:
        print(f"\n{msg}\n")
        print(config.schedule_summary())
    else:
        print(f"\nNot saved: {msg}\n")


def change_all_times() -> None:
    print("\n=== Set shift times ===\n")
    print("Example: work 09:00–18:00, lunch 13:00–14:00 (1 hour)\n")
    work_start = _prompt_time("Work start (login) HH:MM", config.WORK_START)
    work_end = _prompt_time("Work end (logout) HH:MM", config.WORK_END)
    lunch_on = input(f"Lunch break? [y/n] ({'y' if config.LUNCH_ENABLED else 'n'}): ").strip().lower()
    lunch_enabled = lunch_on != "n" if lunch_on else config.LUNCH_ENABLED
    updates: dict[str, str] = {
        "WORK_START": work_start,
        "WORK_END": work_end,
        "LUNCH_ENABLED": "true" if lunch_enabled else "false",
    }
    if lunch_enabled:
        updates["LUNCH_START"] = _prompt_time("Lunch start HH:MM", config.LUNCH_START)
        updates["LUNCH_END"] = _prompt_time("Lunch end HH:MM", config.LUNCH_END)
    _save_and_show(updates)


def change_work_start() -> None:
    _save_and_show({"WORK_START": _prompt_time("Work start (login) HH:MM", config.WORK_START)})


def change_work_end() -> None:
    _save_and_show({"WORK_END": _prompt_time("Work end (logout) HH:MM", config.WORK_END)})


def change_lunch_start() -> None:
    _save_and_show({"LUNCH_START": _prompt_time("Lunch start HH:MM", config.LUNCH_START)})


def change_lunch_end() -> None:
    _save_and_show({"LUNCH_END": _prompt_time("Lunch end HH:MM", config.LUNCH_END)})


def toggle_lunch() -> None:
    print(f"\nLunch is: {'ON' if config.LUNCH_ENABLED else 'OFF'}")
    choice = input("Enable lunch automation? [y/n]: ").strip().lower()
    if choice in {"y", "yes"}:
        _save_and_show({"LUNCH_ENABLED": "true"})
    elif choice in {"n", "no"}:
        _save_and_show({"LUNCH_ENABLED": "false"})
    else:
        print("No change.")


def change_timezone() -> None:
    print(f"\nCurrent: {config.format_timezone()}")
    value = input(f"Timezone [{config.TIMEZONE}]: ").strip() or config.TIMEZONE
    try:
        value = parent_config.canonical_timezone(value)
    except ValueError as exc:
        print(f"\nNot saved: {exc}\n")
        return
    _save_and_show({"TIMEZONE": value})


def change_work_days() -> None:
    print(f"\nCurrent: {config.format_work_days()}")
    print("  1) Mon–Fri   2) Mon–Sat   3) Every day   4) Today only   5) Custom")
    choice = input("Choose [1-5]: ").strip()
    presets = {
        "1": "mon,tue,wed,thu,fri",
        "2": "mon,tue,wed,thu,fri,sat",
        "3": "mon,tue,wed,thu,fri,sat,sun",
    }
    if choice in presets:
        _save_and_show({"WORK_DAYS": presets[choice]})
        return
    if choice == "4":
        tz = config.get_tz()
        today = config.DAY_ORDER[datetime.now(tz).weekday()]
        _save_and_show({"WORK_DAYS": today})
        return
    if choice == "5":
        value = input("Days (mon,tue,... or mon-fri): ").strip()
        if value:
            _save_and_show({"WORK_DAYS": value})
        return
    print("No change.")


def pause_autorun() -> None:
    _save_and_show({"AUTORUN_PAUSED": "true"})
    print("Automation paused — no scheduled jobs until resume (u).")


def resume_autorun() -> None:
    _save_and_show({"AUTORUN_PAUSED": "false"})
    print("Automation resumed.")


def mark_leave_today() -> None:
    tz = config.get_tz()
    today = datetime.now(tz).strftime("%Y-%m-%d")
    _save_and_show({"LEAVE_DATE": today, "AUTORUN_PAUSED": "false"})
    print("Logging out now…")
    try:
        run_action("logout")
    except Exception as exc:
        print(f"Logout error (leave still marked): {exc}")


def clear_leave() -> None:
    _save_and_show({"LEAVE_DATE": ""})


def run_menu() -> None:
    while True:
        print("\n" + "=" * 54)
        print(f"  {config.APP_NAME} — RingCX web agent")
        print("=" * 54)
        print(config.schedule_summary())
        if config.LUNCH_ENABLED:
            print(
                f"  Auto: {config.WORK_START} login | "
                f"{config.LUNCH_START}–{config.LUNCH_END} lunch | "
                f"{config.WORK_END} logout"
            )
        print("")
        print("Schedule:")
        print("  1) Show schedule")
        print("  2) Set ALL times (work start/end + lunch start/end)")
        print("  3) Work START (login)")
        print("  4) Work END (logout)")
        print("  5) Lunch START")
        print("  6) Lunch END")
        print("  7) Enable / disable lunch")
        print("  9) Timezone")
        print("  w) Work days")
        print("")
        print("Run now (manual):")
        print("  m) Morning — login + Start session + AVAILABLE")
        print("  l) Lunch")
        print("  b) Back from lunch (AVAILABLE)")
        print("  g) Logout / Stop session")
        print("")
        print("Leave / pause:")
        print("  p) Pause automation")
        print("  u) Resume automation")
        print("  x) Mark today leave + logout")
        print("  c) Clear leave date")
        print("")
        print("Background service:")
        print("  i) Start / install background job (auto on Mac login)")
        print("  o) Stop / uninstall background job")
        print("  t) Background job status")
        print("  s) Test scheduler in this terminal")
        print("  0) Exit")
        print("")

        choice = input("Choose: ").strip().lower()

        if choice == "0":
            print("Bye.")
            return
        if choice == "1":
            print("\n" + config.schedule_summary())
        elif choice == "2":
            change_all_times()
        elif choice == "3":
            change_work_start()
        elif choice == "4":
            change_work_end()
        elif choice == "5":
            change_lunch_start()
        elif choice == "6":
            change_lunch_end()
        elif choice == "7":
            toggle_lunch()
        elif choice == "9":
            change_timezone()
        elif choice == "w":
            change_work_days()
        elif choice == "p":
            pause_autorun()
        elif choice == "u":
            resume_autorun()
        elif choice == "x":
            mark_leave_today()
        elif choice == "c":
            clear_leave()
        elif choice == "m":
            print("\nRunning morning…\n")
            run_action("morning")
        elif choice == "l":
            print("\nRunning lunch…\n")
            run_action("lunch")
        elif choice == "b":
            print("\nRunning back from lunch…\n")
            run_action("lunch-end")
        elif choice == "g":
            print("\nRunning logout…\n")
            run_action("logout")
        elif choice == "i":
            print("\n" + rcx_service.install() + "\n")
        elif choice == "o":
            confirm = input("Stop background service? [y/n]: ").strip().lower()
            if confirm in {"y", "yes"}:
                print("\n" + rcx_service.uninstall() + "\n")
            else:
                print("No change.")
        elif choice == "t":
            print("\n" + rcx_service.status() + "\n")
        elif choice == "s":
            print("\nScheduler in this terminal — Ctrl+C to stop.\n")
            import rc_autologin_run as run_mod

            run_mod.cmd_schedule(argparse.Namespace())
        else:
            print("Invalid option.")
