"""macOS Accessibility automation for RingCentral.app (AppleScript / System Events)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Iterable

from rc_desktop import config


class DesktopUIError(RuntimeError):
    pass


class AccessibilityDeniedError(DesktopUIError):
    pass


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def accessibility_help() -> str:
    term = os.environ.get("TERM_PROGRAM", "").strip()
    term_hint = {
        "Apple_Terminal": "Terminal",
        "iTerm.app": "iTerm",
        "vscode": "Cursor",  # Cursor reports as vscode
    }.get(term, term or "Terminal (or iTerm / Cursor)")
    python_bin = sys.executable
    lines = [
        "macOS Accessibility permission is required.",
        "",
        "1. Open: System Settings → Privacy & Security → Accessibility",
        "   Or run: desktop_run.py open-accessibility-settings",
        "",
        f"2. Enable: {term_hint}",
        f"3. Also add this Python if listed: {python_bin}",
        "",
        "4. Quit and reopen Terminal/Cursor after toggling.",
        "5. Run again: desktop_run.py test-access",
    ]
    return "\n".join(lines)


def open_accessibility_settings() -> None:
    subprocess.run(
        [
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        ],
        check=False,
    )


def run_applescript(script: str, *, timeout: int = 90) -> str:
    import tempfile

    script = script.strip()
    tmp_path: str | None = None
    result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="no script")
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".applescript",
            delete=False,
            encoding="utf-8",
        ) as fh:
            fh.write(script)
            tmp_path = fh.name
        result = subprocess.run(
            ["osascript", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        lower = stderr.lower()
        if (
            "assistive access" in lower
            or "not allowed assistive" in lower
            or "accessibility" in lower
            or "(-1719)" in stderr
            or "(-25211)" in stderr
        ):
            raise AccessibilityDeniedError(accessibility_help())
        raise DesktopUIError(stderr or "AppleScript failed")
    return (result.stdout or "").strip()


def verify_accessibility_permission() -> None:
    """Probe System Events — fails fast if Accessibility is not granted."""
    run_applescript(
        '''
        tell application "System Events"
            set _n to count of processes
        end tell
        return "ok"
        '''
    )


def list_matching_processes(*needles: str) -> list[str]:
    """Return running process names containing any needle (case-insensitive)."""
    if not needles:
        needles = ("ring",)
    names: set[str] = set()
    try:
        for pattern in ("RingCentral", "ringcentral", "RingEX"):
            pgrep = subprocess.run(
                ["pgrep", "-ifl", pattern],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            for line in pgrep.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) >= 2:
                    names.add(parts[1].split("/")[-1].split()[0])
    except Exception:
        pass

    if not names:
        try:
            result = subprocess.run(
                ["ps", "-ax", "-o", "comm="],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            for line in result.stdout.splitlines():
                base = line.strip().split("/")[-1]
                if not base:
                    continue
                lower = base.lower()
                if any(n.lower() in lower for n in needles):
                    names.add(base)
        except Exception:
            pass

    if names:
        return sorted(names)

    needle_expr = " or ".join(f'n contains "{_escape(n)}"' for n in needles)
    script = f'''
    set out to ""
    tell application "System Events"
        repeat with p in every process
            try
                set n to name of p as text
                if {needle_expr} then
                    set out to out & n & linefeed
                end if
            end try
        end repeat
    end tell
    return out
    '''
    try:
        raw = run_applescript(script)
    except AccessibilityDeniedError:
        raise
    except DesktopUIError:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def pick_best_process(matches: list[str]) -> str:
    non_helper = [m for m in matches if "helper" not in m.lower()]
    pool = non_helper or matches
    for pick in pool:
        if pick.lower() in {"ringcentral", "ringex"}:
            return pick
    for pick in pool:
        if "ringcentral" in pick.lower():
            return pick
    return pool[0]


def launch_ringcentral_app() -> None:
    app_name = os.getenv("RC_APP_BUNDLE", "RingCentral").strip()
    for candidate in (app_name, "RingCentral", "RingCentral Phone", "RingEX"):
        result = subprocess.run(
            ["open", "-a", candidate],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"  Launched: {candidate}")
            time.sleep(3)
            return
    raise DesktopUIError(
        f"Could not open RingCentral. Tried: {app_name}, RingCentral, RingCentral Phone.\n"
        "Open the app manually, then run desktop_run.py discover"
    )


def resolve_process_name(preferred: str | None = None) -> str:
    """Find the live System Events process name for RingCentral."""
    preferred = (preferred or config.RC_APP_PROCESS).strip()
    verify_accessibility_permission()

    if preferred:
        script = f'''
        tell application "System Events"
            if exists process "{_escape(preferred)}" then
                return "{_escape(preferred)}"
            end if
        end tell
        return ""
        '''
        found = run_applescript(script)
        if found:
            return found

    matches = list_matching_processes("ring", "RingCentral", "RingEX", "nice")
    if matches:
        return pick_best_process(matches)

    launch_ringcentral_app()
    time.sleep(2)
    matches = list_matching_processes("ring", "RingCentral", "RingEX")
    if matches:
        return pick_best_process(matches)

    raise DesktopUIError(
        "RingCentral is not running and could not be detected.\n"
        "1. Open RingCentral.app manually\n"
        "2. Run: .venv/bin/python desktop_run.py discover\n"
        "3. Set RC_APP_PROCESS in .env to the name shown"
    )


def check_accessibility(process_name: str | None = None) -> str:
    """Verify Accessibility + RingCentral process. Returns resolved process name."""
    proc = resolve_process_name(process_name)
    script = f'''
    tell application "System Events"
        tell process "{_escape(proc)}"
            set _n to count of windows
        end tell
    end tell
    return "ok"
    '''
    run_applescript(script)
    return proc


def activate_app(process_name: str) -> None:
    # Application name may differ from process name — try both patterns.
    script = f'''
    try
        tell application "{_escape(process_name)}" to activate
    end try
    delay {config.ACTION_DELAY_SECONDS}
    tell application "System Events"
        tell process "{_escape(process_name)}"
            set frontmost to true
        end tell
    end tell
    '''
    run_applescript(script)


def _element_text_block(var_name: str = "e") -> str:
    """AppleScript snippet: searchable text from name + description."""
    return f'''
                        set elText to (name of {var_name}) as text
                        try
                            set elDesc to description of {var_name}
                            if elDesc is not missing value then
                                set elText to elText & " " & (elDesc as text)
                            end if
                        end try
    '''


def _has_text(var: str = "elText") -> str:
    return f"(length of {var}) > 0"


def _compare_op(exact: bool) -> str:
    return "=" if exact else "contains"


def _role_click_block(loose: bool, *, return_prefix: str = "clicked:") -> str:
    """AppleScript body to click element `e` after a text match."""
    if loose:
        return f'''
                                    try
                                        click e
                                        return "{return_prefix}" & n
                                    on error
                                        try
                                            perform action "AXPress" of e
                                            return "pressed:" & n
                                        end try
                                    end try'''
    roles = (
        'r contains "button" or r contains "radio" or r contains "tab" '
        'or r contains "menu" or r contains "pop up" or r contains "link" '
        'or r contains "group" or r contains "static" or r contains "image" '
        'or r contains "list" or r contains "row"'
    )
    return f'''
                                set r to role of e as text
                                if {roles} then
                                    try
                                        click e
                                        return "{return_prefix}" & n
                                    on error
                                        try
                                            perform action "AXPress" of e
                                            return "pressed:" & n
                                        end try
                                    end try
                                end if'''


def _role_click_block_eltext(loose: bool) -> str:
    if loose:
        return '''
                                    try
                                        click e
                                        return "clicked:" & elText
                                    on error
                                        try
                                            perform action "AXPress" of e
                                            return "pressed:" & elText
                                        end try
                                    end try'''
    roles = (
        'r contains "button" or r contains "radio" or r contains "tab" '
        'or r contains "menu" or r contains "pop up" or r contains "link" '
        'or r contains "group" or r contains "static" or r contains "image" '
        'or r contains "list" or r contains "row"'
    )
    return f'''
                                set r to role of e as text
                                if {roles} then
                                    try
                                        click e
                                        return "clicked:" & elText
                                    on error
                                        try
                                            perform action "AXPress" of e
                                            return "pressed:" & elText
                                        end try
                                    end try
                                end if'''


def click_by_name(
    process_name: str,
    search_text: str,
    *,
    exact: bool = True,
    loose: bool = True,
) -> str:
    """Click element by accessibility name only (best for sidebar tabs like Agent)."""
    needle = _escape(search_text)
    op = _compare_op(exact)
    click_body = _role_click_block(loose)
    script = f'''
    tell application "System Events"
        tell process "{_escape(process_name)}"
            set frontmost to true
            repeat with w in windows
                repeat with e in entire contents of w
                    try
                        set n to name of e as text
                        ignoring case
                            if n {op} "{needle}" then
{click_body}
                            end if
                        end ignoring
                    end try
                end repeat
            end repeat
        end tell
    end tell
    error "Not found: {needle}"
    '''
    return run_applescript(script)


def click_by_name_if_present(
    process_name: str,
    search_text: str,
    *,
    exact: bool = True,
    loose: bool = True,
) -> bool:
    try:
        click_by_name(process_name, search_text, exact=exact, loose=loose)
        return True
    except DesktopUIError:
        return False


def find_by_name(process_name: str, search_text: str, *, exact: bool = True) -> bool:
    needle = _escape(search_text)
    op = _compare_op(exact)
    script = f'''
    tell application "System Events"
        tell process "{_escape(process_name)}"
            repeat with w in windows
                repeat with e in entire contents of w
                    try
                        set n to name of e as text
                        ignoring case
                            if n {op} "{needle}" then
                                return "yes"
                            end if
                        end ignoring
                    end try
                end repeat
            end repeat
        end tell
    end tell
    return "no"
    '''
    return run_applescript(script) == "yes"


def click_by_text(
    process_name: str,
    search_text: str,
    *,
    exact: bool = False,
    loose: bool = False,
) -> str:
    """Click element whose name/description/title matches search_text."""
    needle = _escape(search_text)
    op = _compare_op(exact)
    text_block = _element_text_block("e")
    click_body = _role_click_block_eltext(loose)
    script = f'''
    tell application "System Events"
        tell process "{_escape(process_name)}"
            set frontmost to true
            repeat with w in windows
                repeat with e in entire contents of w
                    try
{text_block}
                        ignoring case
                            if elText {op} "{needle}" then
{click_body}
                            end if
                        end ignoring
                    end try
                end repeat
            end repeat
        end tell
    end tell
    error "Not found: {needle}"
    '''
    return run_applescript(script)


def click_by_text_if_present(
    process_name: str,
    search_text: str,
    *,
    exact: bool = False,
    loose: bool = False,
) -> bool:
    try:
        click_by_text(process_name, search_text, exact=exact, loose=loose)
        return True
    except DesktopUIError:
        return False


def find_by_text(process_name: str, search_text: str, *, exact: bool = False) -> bool:
    needle = _escape(search_text)
    op = _compare_op(exact)
    text_block = _element_text_block("e")
    script = f'''
    tell application "System Events"
        tell process "{_escape(process_name)}"
            repeat with w in windows
                repeat with e in entire contents of w
                    try
{text_block}
                        ignoring case
                            if elText {op} "{needle}" then
                                return "yes"
                            end if
                        end ignoring
                    end try
                end repeat
            end repeat
        end tell
    end tell
    return "no"
    '''
    return run_applescript(script) == "yes"


def any_text_present(process_name: str, names: Iterable[str]) -> str | None:
    for name in names:
        if name and find_by_text(process_name, str(name)):
            return str(name)
    return None


def search_ui(process_name: str, query: str, *, max_lines: int = 80) -> str:
    needle = _escape(query)
    text_block = _element_text_block("e")
    limit_test = f"lineCount > {max_lines - 1}"
    script = f'''
set out to ""
set lineCount to 0
tell application "System Events"
    tell process "{_escape(process_name)}"
        repeat with w in windows
            repeat with e in entire contents of w
                try
{text_block}
                    ignoring case
                        if elText contains "{needle}" and {_has_text("elText")} then
                            set r to (role of e) as text
                            set out to out & r & " | " & elText & linefeed
                            set lineCount to lineCount + 1
                            if {limit_test} then exit repeat
                        end if
                    end ignoring
                end try
            end repeat
        end repeat
    end tell
end tell
return out
'''
    return run_applescript(script, timeout=120)


def click_named(process_name: str, search_text: str, *, exact: bool = False, loose: bool = False) -> str:
    return click_by_text(process_name, search_text, exact=exact, loose=loose)


def click_named_if_present(
    process_name: str,
    search_text: str,
    *,
    exact: bool = False,
    loose: bool = False,
) -> bool:
    return click_by_text_if_present(process_name, search_text, exact=exact, loose=loose)


def wait_for_any_named(
    process_name: str,
    names: Iterable[str],
    *,
    timeout: float | None = None,
    poll: float = 0.5,
) -> str | None:
    deadline = time.time() + (timeout if timeout is not None else config.CONNECT_WAIT_SECONDS)
    names_list = list(names)
    while time.time() < deadline:
        found = any_named_present(process_name, names_list)
        if found:
            return found
        time.sleep(poll)
    return None


def find_named(process_name: str, search_text: str, *, exact: bool = False) -> bool:
    return find_by_text(process_name, search_text, exact=exact)


def any_named_present(process_name: str, names: Iterable[str]) -> str | None:
    return any_text_present(process_name, names)


def click_menu_item(process_name: str, item_text: str) -> str:
    needle = _escape(item_text)
    script = f'''
    tell application "System Events"
        tell process "{_escape(process_name)}"
            set frontmost to true
            repeat with w in windows
                repeat with m in menus of menu bar 1
                    repeat with mi in menu items of m
                        try
                            if name of mi as text contains "{needle}" then
                                click mi
                                return "clicked-menu:" & (name of mi as text)
                            end if
                        end try
                    end repeat
                end repeat
                repeat with e in entire contents of w
                    try
                        if role of e as text contains "menu" then
                            repeat with mi in menu items of e
                                try
                                    if name of mi as text contains "{needle}" then
                                        click mi
                                        return "clicked-popup:" & (name of mi as text)
                                    end if
                                end try
                            end repeat
                        end if
                    end try
                end repeat
            end repeat
        end tell
    end tell
    error "Menu item not found: {needle}"
    '''
    return run_applescript(script)


def set_status_via_menu(
    process_name: str,
    *,
    status_button_hint: str,
    menu_path: list[str],
) -> None:
    """Click status control, then each menu level (e.g. Unavailable → Lunch)."""
    activate_app(process_name)
    if not click_named_if_present(process_name, status_button_hint):
        click_named(process_name, status_button_hint)
    time.sleep(config.STATUS_SET_DELAY_SECONDS)
    for item in menu_path:
        click_menu_item(process_name, item)
        time.sleep(config.STATUS_SET_DELAY_SECONDS)


def inspect_ui(process_name: str, *, max_lines: int | None = None) -> str:
    limit = max_lines if max_lines is not None else config.INSPECT_MAX_LINES
    text_block = _element_text_block("e")
    limit_test = f"lineCount > {limit - 1}"
    script = f'''
set out to ""
set lineCount to 0
tell application "System Events"
    tell process "{_escape(process_name)}"
        repeat with w in windows
            set out to out & "WINDOW: " & ((name of w) as text) & linefeed
            repeat with e in entire contents of w
                try
{text_block}
                    if {_has_text("elText")} then
                        set r to (role of e) as text
                        set out to out & r & " | " & elText & linefeed
                        set lineCount to lineCount + 1
                        if {limit_test} then exit repeat
                    end if
                end try
            end repeat
        end repeat
    end tell
end tell
return out
'''
    return run_applescript(script, timeout=120)
