"""RingCentral desktop flows — Start working, status, Stop working."""

from __future__ import annotations

import time

from rc_desktop import ax_ui, config
from rc_desktop.labels import app_process, load_labels

_resolved_proc: str | None = None


def _labels() -> dict:
    return load_labels()


def _proc() -> str:
    global _resolved_proc
    if _resolved_proc is None:
        preferred = app_process(_labels())
        _resolved_proc = ax_ui.check_accessibility(preferred)
    return _resolved_proc


def _is_on_agent_tab(proc: str) -> bool:
    """True when Agent tab content is visible (Start/Stop working)."""
    labels = _labels()
    markers = [str(x) for x in labels.get("on_agent_tab_markers", ["Start working", "Stop working"])]
    return ax_ui.any_text_present(proc, markers) is not None


def _go_to_agent_tab() -> None:
    if config.DESKTOP_SKIP_AGENT_TAB:
        print("  (Skipping Agent tab — DESKTOP_SKIP_AGENT_TAB=true)")
        return

    labels = _labels()
    proc = _proc()
    agent_tab = str(labels.get("agent_tab", "Agent"))

    if _is_on_agent_tab(proc):
        print("  ✓ Already on Agent tab — proceeding to connect")
        return

    print(f"  → Switch to Agent tab ({agent_tab})")
    if ax_ui.click_by_name_if_present(proc, agent_tab, exact=True, loose=True):
        time.sleep(config.ACTION_DELAY_SECONDS)
        return
    if ax_ui.click_by_text_if_present(proc, agent_tab, exact=True, loose=True):
        time.sleep(config.ACTION_DELAY_SECONDS)
        return

    raise ax_ui.DesktopUIError(
        f'Could not switch to Agent tab "{agent_tab}".\n'
        "Open RingCentral, then run: .venv/bin/python desktop_run.py search agent"
    )


def _ensure_app() -> None:
    proc = _proc()
    ax_ui.activate_app(proc)
    _go_to_agent_tab()


def _wait_connected() -> None:
    labels = _labels()
    proc = _proc()
    markers = [str(x) for x in labels.get("connected_markers", ["Available", "Stop working"])]
    print(f"  → Waiting to connect (up to {config.CONNECT_WAIT_SECONDS}s)…")
    found = ax_ui.any_named_present(proc, markers)
    if found:
        print(f"  ✓ Already connected ({found})")
        return
    connected = ax_ui.wait_for_any_named(proc, markers, timeout=config.CONNECT_WAIT_SECONDS)
    if connected:
        print(f"  ✓ Connected ({connected} visible)")
        return
    raise ax_ui.DesktopUIError(
        "Timed out waiting for connection. Run desktop_run.py inspect and check labels.yaml."
    )


def _click_first_alias(proc: str, aliases: list[str], *, action: str) -> bool:
    for alias in aliases:
        label = str(alias).strip()
        if not label:
            continue
        if ax_ui.click_by_text_if_present(proc, label, loose=True):
            print(f"  ✓ {action}: {label}")
            return True
    return False


def start_working() -> None:
    labels = _labels()
    proc = _proc()
    aliases = labels.get("start_working_aliases") or [labels.get("start_working", "Start working")]
    print("  → Start working (connect)")
    if _click_first_alias(proc, [str(a) for a in aliases], action="Clicked"):
        time.sleep(config.ACTION_DELAY_SECONDS)
        _wait_connected()
        return
    if ax_ui.any_text_present(
        proc,
        [str(x) for x in labels.get("connected_markers", ["Available", "Stop working"])],
    ):
        print("  ✓ Already connected")
        return
    raise ax_ui.DesktopUIError(
        'Could not find "Start working". Are you on the Agent tab?\n'
        "Run: desktop_run.py search start"
    )


def stop_working() -> None:
    labels = _labels()
    proc = _proc()
    aliases = labels.get("stop_working_aliases") or [labels.get("stop_working", "Stop working")]
    print(f"  → Stop working")
    if _click_first_alias(proc, [str(a) for a in aliases], action="Clicked"):
        time.sleep(config.ACTION_DELAY_SECONDS)
        return
    raise ax_ui.DesktopUIError(
        f'Could not find Stop working. Tried: {aliases}\n'
        "Run: desktop_run.py search stop"
    )


def set_available() -> None:
    labels = _labels()
    proc = _proc()
    available = str(labels.get("available", "Available"))
    if ax_ui.find_named(proc, available):
        print(f"  ✓ Already {available}")
        return
    print(f"  → Set status → {available}")
    ax_ui.set_status_via_menu(
        proc,
        status_button_hint=str(labels.get("unavailable", "Unavailable")),
        menu_path=[available],
    )


def set_lunch() -> None:
    labels = _labels()
    proc = _proc()
    lunch = str(labels.get("lunch", "Lunch"))
    unavailable = str(labels.get("unavailable", "Unavailable"))
    if ax_ui.find_named(proc, lunch):
        print(f"  ✓ Already on {lunch}")
        return
    print(f"  → Set status → {unavailable} → {lunch}")
    # Try direct Lunch first, then Unavailable → Lunch
    ax_ui.activate_app(proc)
    if ax_ui.click_by_text_if_present(proc, unavailable) or ax_ui.click_by_text_if_present(
        proc, str(labels.get("available", "Available")), loose=True
    ):
        time.sleep(config.STATUS_SET_DELAY_SECONDS)
        if ax_ui.click_by_text_if_present(proc, lunch, loose=True):
            return
        ax_ui.click_menu_item(proc, lunch)
        return
    ax_ui.set_status_via_menu(
        proc,
        status_button_hint=str(labels.get("available", "Available")),
        menu_path=[unavailable, lunch],
    )


def morning_login() -> None:
    print("RingCentral desktop — morning (Agent → Start working → Available)")
    _ensure_app()
    start_working()
    set_available()


def lunch_start() -> None:
    print("RingCentral desktop — lunch")
    _ensure_app()
    set_lunch()


def lunch_end() -> None:
    print("RingCentral desktop — back from lunch")
    _ensure_app()
    set_available()


def logout() -> None:
    print("RingCentral desktop — end of day (Stop working)")
    _ensure_app()
    stop_working()


def run_action(action: str) -> None:
    actions = {
        "morning": morning_login,
        "login": morning_login,
        "lunch": lunch_start,
        "lunch-end": lunch_end,
        "logout": logout,
    }
    fn = actions.get(action)
    if fn is None:
        raise ValueError(f"Unknown action: {action}")
    fn()
    print("\nDone.")
