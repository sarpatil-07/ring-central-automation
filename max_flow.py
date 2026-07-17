"""NICE MAX workflow — launch Chrome directly (no debug port by default)."""

from __future__ import annotations

import time

import config
import ui_actions as ui
from browser_session import MaxBrowserSession
from playwright.sync_api import BrowserContext, Page
from ui_actions import page_alive


def _on_myprofile(url: str) -> bool:
    u = url.lower()
    return "myprofile" in u and "login" not in u


def _session_ready(page: Page) -> bool:
    """Logged in and app menu visible."""
    if not _on_myprofile(page.url):
        return False
    return ui.app_shell_ready(page, timeout_ms=5000)


def _login_deadline() -> float:
    return time.time() + config.MANUAL_LOGIN_WAIT_SECONDS


def _ensure_logged_in(page: Page, deadline: float | None = None) -> None:
    deadline = deadline or _login_deadline()

    if _session_ready(page):
        print("  Session active — myprofile ready")
        return

    print("Opening myprofile…")
    page.goto(config.MYPROFILE_URL, wait_until="domcontentloaded", timeout=90_000)
    ui.wait(page, 3000)

    print("")
    print("  No saved login in MAX profile — complete login in the MAX browser window.")
    print(f"  Waiting up to {config.MANUAL_LOGIN_WAIT_SECONDS // 60} minutes (script will not click or reload).")
    print("")

    while time.time() < deadline:
        if _session_ready(page):
            print("  Login complete — myprofile ready")
            return
        ui.wait(page, 3000)

    raise RuntimeError(
        "Login not finished in time — complete login in MAX browser, then run morning again."
    )


def _open_max(
    page: Page, context: BrowserContext, *, focus: bool = True, deadline: float | None = None
) -> Page:
    deadline = deadline or _login_deadline()
    existing = None
    for p in context.pages:
        try:
            if not p.is_closed() and MaxBrowserSession._is_max_url(p.url):
                existing = p
                break
        except Exception:
            continue

    if existing is not None:
        print(f"  MAX already open: {existing.url[:80]}")
        if focus:
            existing.bring_to_front()
        ui.wait(existing, 2000)
        return existing

    if not ui.app_shell_ready(page, timeout_ms=3000):
        print("  Waiting for Switch application menu (after login)…")
        if not ui.wait_for_step(page, "switch_application", deadline):
            raise RuntimeError(
                "Switch application menu not visible — finish login in MAX browser."
            )

    ui.click_step(page, "switch_application", timeout_ms=30_000)
    main = page
    try:
        with page.expect_popup(timeout=30_000) as popup:
            ui.click_step(page, "max_button", timeout_ms=30_000)
        max_page = popup.value
        max_page.wait_for_load_state("domcontentloaded", timeout=60_000)
    except Exception:
        ui.click_step(page, "max_button", timeout_ms=30_000)
        ui.wait(page, 4000)
        max_page = main
        for p in context.pages:
            if p != main and MaxBrowserSession._is_max_url(p.url):
                max_page = p
                break
    print(f"  MAX window: {max_page.url[:80]}")
    ui.wait(max_page, 3000)
    return max_page


def _resolve_max_page(session: MaxBrowserSession, *, allow_open: bool, focus: bool) -> Page:
    max_page = session.get_max_page(focus=focus)
    if max_page is not None:
        ui.wait(max_page, 2000)
        return max_page

    if not allow_open:
        raise RuntimeError(
            "MAX tab not found. Run morning first, or keep the MAX window open."
        )

    page = session.get_work_page(focus=focus)
    deadline = _login_deadline()
    _ensure_logged_in(page, deadline)
    max_page = _open_max(page, session.context, focus=focus, deadline=deadline)
    session.remember_max_page(max_page)
    return max_page


def _wait_for_max_tab(session: MaxBrowserSession, *, seconds: int = 20) -> Page | None:
    """After connect/reload, wait for the same MAX tab to come back."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        found = session.find_max_page()
        if page_alive(found):
            return found
        time.sleep(1)
    return None


def _fresh_max_page(
    session: MaxBrowserSession,
    work_page: Page | None = None,
    *,
    focus: bool = True,
    deadline: float | None = None,
) -> Page:
    """Re-find MAX tab after connect/reload — never open a second MAX if one exists."""
    session.forget_max_page()
    found = _wait_for_max_tab(session)
    if page_alive(found):
        if focus:
            found.bring_to_front()
        ui.wait(found, 2000)
        session.remember_max_page(found)
        return found

    existing = session.scan_max_pages()
    if existing:
        max_page = existing[-1]
        print(f"  MAX tab found after connect: {max_page.url[:80]}")
        if focus:
            max_page.bring_to_front()
        session.remember_max_page(max_page)
        return max_page

    if work_page is None:
        work_page = session.get_work_page(focus=focus)
    max_page = _open_max(work_page, session.context, focus=focus, deadline=deadline)
    session.remember_max_page(max_page)
    return max_page


def _run_status_action(
    session: MaxBrowserSession,
    action: str,
    max_page: Page,
    *,
    focus: bool,
    deadline: float | None = None,
) -> None:
    work_page = None
    try:
        if action == "lunch":
            ui.set_lunch_unavailable_if_needed(max_page)
        elif action == "lunch-end":
            ui.set_available_if_needed(max_page)
        elif action == "logout":
            ui.logout(max_page)
        else:
            raise ValueError(action)
    except Exception as exc:
        if action == "logout" and ui.is_target_closed_error(exc):
            print("  Logout complete — MAX window closed.")
            return
        if not ui.is_target_closed_error(exc):
            raise
        print("  MAX tab closed — reopening and retrying…")
        work_page = session.get_work_page(focus=True)
        max_page = _fresh_max_page(session, work_page, focus=focus or action == "logout", deadline=deadline)
        if action == "lunch":
            ui.set_lunch_unavailable_if_needed(max_page)
        elif action == "lunch-end":
            ui.set_available_if_needed(max_page)
        elif action == "logout":
            ui.logout(max_page)


def _run_steps(session: MaxBrowserSession, action: str) -> None:
    # Lunch can run in background; logout needs focus so status menu clicks work.
    quiet = config.QUIET_STATUS_JOBS and action in ("lunch", "lunch-end")
    focus = not quiet
    deadline = _login_deadline()

    if action == "morning":
        max_page = session.find_max_page()
        if page_alive(max_page):
            print("  MAX already running — reconnecting on same session")
            if max_page:
                max_page.bring_to_front()
            current = ui.get_current_status(max_page)
            if current:
                print(f"  Current agent status: {current}")
            if ui.is_connected(max_page) and ui.is_agent_available(max_page):
                print("  ✓ already connected and Available — morning step skipped")
                return
            ui.connect_station_if_needed(max_page)
            max_page = _fresh_max_page(session, focus=True, deadline=deadline)
            ui.set_available_if_needed(max_page)
            return

        page = session.get_work_page(focus=True)
        _ensure_logged_in(page, deadline)
        max_page = _open_max(page, session.context, focus=True, deadline=deadline)
        session.remember_max_page(max_page)
        ui.connect_station_if_needed(max_page)
        max_page = _fresh_max_page(session, page, focus=True, deadline=deadline)
        try:
            ui.set_available_if_needed(max_page)
        except Exception as exc:
            if not ui.is_target_closed_error(exc):
                raise
            print("  MAX tab reloaded — waiting for same session…")
            max_page = _fresh_max_page(session, page, focus=True, deadline=deadline)
            ui.set_available_if_needed(max_page)
        return

    max_page = _resolve_max_page(session, allow_open=action != "logout", focus=focus)
    _run_status_action(session, action, max_page, focus=focus, deadline=deadline)


def run_action(action: str, session: MaxBrowserSession | None = None) -> None:
    own_session = session is None
    session = session or MaxBrowserSession()
    ok = False
    try:
        session.start()
        _run_steps(session, action)
        ok = True
        print("\nDone.")
    except Exception as exc:
        print(f"\nFailed: {exc}")
        if own_session:
            print("MAX browser left open — finish login if needed, then run morning again.")
        raise
    finally:
        if own_session and ok:
            session.close()
        elif own_session and not ok:
            session.detach()
