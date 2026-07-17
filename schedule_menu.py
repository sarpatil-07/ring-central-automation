"""Interactive menu — change work/lunch times any day (rotating shifts)."""

from __future__ import annotations

import config


def _prompt_time(label: str, current: str) -> str:
    while True:
        value = input(f"{label} [{current}]: ").strip() or current
        try:
            config.parse_time(value, label)
            return value
        except ValueError as exc:
            print(f"  Invalid: {exc}")


def _save_and_show(updates: dict[str, str]) -> None:
    try:
        if "WORK_DAYS" in updates:
            updates["WORK_DAYS"] = config.parse_work_days(updates["WORK_DAYS"])
        merged = {
            "STATION_ID": config.STATION_ID,
            "TIMEZONE": config.TIMEZONE,
            "WORK_DAYS": config.WORK_DAYS,
            "WORK_START": config.WORK_START,
            "WORK_END": config.WORK_END,
            "LUNCH_ENABLED": "true" if config.LUNCH_ENABLED else "false",
            "LUNCH_START": config.LUNCH_START,
            "LUNCH_END": config.LUNCH_END,
        }
        merged.update(updates)
        config.parse_time(merged["WORK_START"], "WORK_START")
        config.parse_time(merged["WORK_END"], "WORK_END")
        if merged["LUNCH_ENABLED"].lower() in {"1", "true", "yes"}:
            config.parse_time(merged["LUNCH_START"], "LUNCH_START")
            config.parse_time(merged["LUNCH_END"], "LUNCH_END")
        config.get_schedule_jobs(
            work_start=merged["WORK_START"],
            work_end=merged["WORK_END"],
            lunch_start=merged["LUNCH_START"],
            lunch_end=merged["LUNCH_END"],
            lunch_enabled=merged["LUNCH_ENABLED"].lower() in {"1", "true", "yes"},
        )
        config.save_env(updates)
        print("\nSaved.", end="")
        try:
            import service

            if service.plist_path().exists():
                print(" " + service.restart())
            else:
                print(" Restart scheduler if it is already running.")
        except Exception:
            print(" Restart scheduler if it is already running.")
        print()
        print(config.schedule_summary())
    except ValueError as exc:
        print(f"\nNot saved: {exc}\n")


def change_work_start() -> None:
    _save_and_show({"WORK_START": _prompt_time("Work start (login) HH:MM", config.WORK_START)})


def change_work_end() -> None:
    _save_and_show({"WORK_END": _prompt_time("Work end (logout) HH:MM", config.WORK_END)})


def change_lunch_start() -> None:
    _save_and_show({"LUNCH_START": _prompt_time("Lunch start HH:MM", config.LUNCH_START)})


def change_lunch_end() -> None:
    _save_and_show({"LUNCH_END": _prompt_time("Lunch end HH:MM", config.LUNCH_END)})


def toggle_lunch() -> None:
    print(f"\nLunch break is currently: {'ON' if config.LUNCH_ENABLED else 'OFF'}")
    choice = input("Enable lunch automation? [y/n]: ").strip().lower()
    if choice in {"y", "yes"}:
        _save_and_show({"LUNCH_ENABLED": "true"})
    elif choice in {"n", "no"}:
        _save_and_show({"LUNCH_ENABLED": "false"})
    else:
        print("No change.")


def change_station_id() -> None:
    value = input(f"Station ID [{config.STATION_ID}]: ").strip() or config.STATION_ID
    _save_and_show({"STATION_ID": value})


def change_timezone() -> None:
    print("\n=== Timezone ===")
    print(f"Current: {config.format_timezone()}")
    print("Default: IST (India). You can also use APAC, EMEA, LATAM, NA, or IANA names.")
    print("Examples: IST | India | na-eastern | Asia/Dubai | Europe/London")
    print("(Do not type the full label — e.g. use IST, not 'IST (India)')")
    value = input(f"Timezone [{config.TIMEZONE}]: ").strip() or config.TIMEZONE
    try:
        value = config.canonical_timezone(value)
    except ValueError as exc:
        print(f"\nNot saved: {exc}\n")
        return
    _save_and_show({"TIMEZONE": value})


def change_work_days() -> None:
    from datetime import datetime

    print("\n=== Work days ===")
    print(f"Current: {config.format_work_days()}")
    print("")
    print("Presets:")
    print("  1) Mon–Fri")
    print("  2) Mon–Sat")
    print("  3) Every day (Mon–Sun)")
    print("  4) Today only (good for testing)")
    print("  5) Custom (e.g. mon,wed,fri  or  sat,sun)")
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
        print(f"Setting work day to today only: {config.DAY_LABELS[today]}")
        _save_and_show({"WORK_DAYS": today})
        return
    if choice == "5":
        value = input(
            "Days (mon,tue,wed,thu,fri,sat,sun or mon-fri): "
        ).strip()
        if value:
            _save_and_show({"WORK_DAYS": value})
        else:
            print("No change.")
        return
    print("No change.")


def change_all_times() -> None:
    print("\n=== Set today's shift times ===\n")
    work_start = _prompt_time("Work start (login) HH:MM", config.WORK_START)
    work_end = _prompt_time("Work end (logout) HH:MM", config.WORK_END)
    lunch_on = input(f"Lunch break today? [y/n] ({'y' if config.LUNCH_ENABLED else 'n'}): ").strip().lower()
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


def pause_autorun() -> None:
    print("\nAutomation paused — no scheduled jobs until you resume (option u).\n")
    _save_and_show({"AUTORUN_PAUSED": "true"})


def resume_autorun() -> None:
    print("\nAutomation resumed.\n")
    _save_and_show({"AUTORUN_PAUSED": "false"})


def mark_leave_today() -> None:
    from datetime import datetime

    from browser_session import MaxBrowserSession
    from max_flow import run_action

    tz = config.get_tz()
    today = datetime.now(tz).strftime("%Y-%m-%d")
    print(f"\nMarking leave for {today} — no more jobs today.")
    _save_and_show({"LEAVE_DATE": today, "AUTORUN_PAUSED": "false"})

    print("Logging out from MAX now…")
    session = MaxBrowserSession()
    try:
        run_action("logout", session=session)
        session.shutdown_for_day()
        print("Leave marked and logged out.")
    except Exception as exc:
        session.shutdown_for_day()
        print(f"Leave marked. Logout failed — close MAX manually if needed: {exc}")


def clear_leave() -> None:
    _save_and_show({"LEAVE_DATE": ""})


def run_menu() -> None:
    while True:
        print("\n" + "=" * 54)
        print(f"  {config.APP_NAME} — schedule & actions")
        print("=" * 54)
        print(config.schedule_summary())
        print("Change times (for rotating shifts — update any day):")
        print("  1) Show schedule")
        print("  2) Set ALL times for today (work + lunch)")
        print("  3) Change work START only")
        print("  4) Change work END only")
        print("  5) Change lunch START only")
        print("  6) Change lunch END only")
        print("  7) Enable / disable lunch break")
        print("  8) Change station ID")
        print("  9) Change timezone (default IST — India)")
        print("  w) Change work days (Mon–Fri, weekends, today only, custom)")
        print("")
        print("Leave / pause:")
        print("  p) Pause automation (vacation — no jobs until resumed)")
        print("  u) Resume automation")
        print("  x) Mark TODAY as leave (logout now + skip rest of day)")
        print("  c) Clear leave date")
        print("")
        print("  r) Reset stuck MAX browser (keeps saved login)")
        print("  k) Clear saved login (force OTP on next run)")
        print("  i) Install auto-start background service (set once)")
        print("  o) Stop / uninstall background service")
        print("  t) Background service status")
        print("  s) Start scheduler in this terminal (manual test)")
        print("  0) Exit")
        print("")

        choice = input("Choose option: ").strip().lower()

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
        elif choice == "8":
            change_station_id()
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
        elif choice == "r":
            from browser_recovery import reset_max_browser

            print(f"\n{reset_max_browser(force=True)}\n")
        elif choice == "k":
            from browser_recovery import clear_saved_login

            confirm = input("Clear saved SSO/login in MAX profile? [y/n]: ").strip().lower()
            if confirm in {"y", "yes"}:
                print(f"\n{clear_saved_login()}\n")
            else:
                print("No change.")
        elif choice == "i":
            import service

            print("\n" + service.install() + "\n")
        elif choice == "o":
            import service

            confirm = input("Stop background service (no auto-run on login)? [y/n]: ").strip().lower()
            if confirm in {"y", "yes"}:
                print("\n" + service.uninstall() + "\n")
            else:
                print("No change.")
        elif choice == "t":
            import service

            print("\n" + service.status() + "\n")
        elif choice == "s":
            print("\nStarting scheduler — Ctrl+C to stop.\n")
            import argparse
            import run as run_module

            run_module.cmd_schedule(argparse.Namespace())
        else:
            print("Invalid option.")
