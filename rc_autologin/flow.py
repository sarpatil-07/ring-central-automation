"""RCAutoLogin flows — RingCX web agent."""

from __future__ import annotations

import time

from playwright.sync_api import Page

from rc_autologin import config
from rc_autologin import ui_actions as ui
from rc_autologin.browser_session import RcxBrowserSession


def _on_agent_url(page: Page) -> bool:
    try:
        u = page.url.lower()
        return "app.ringcentral.com" in u and "ring_cx" in u and "agent" in u
    except Exception:
        return False


def _refresh_page(session: RcxBrowserSession, page: Page | None = None) -> Page:
    page = session.refresh_page(page)
    session.remember_page(page)
    return page


def _with_page_recovery(session: RcxBrowserSession, page: Page, fn) -> Page:
    """Run UI step; reconnect if SSO navigation closed the tab."""
    try:
        fn(page)
        return page
    except Exception as exc:
        if not ui.is_target_closed_error(exc):
            raise
        page = _refresh_page(session, page)
        fn(page)
        return page


def _open_agent_page(session: RcxBrowserSession, *, focus: bool = True) -> Page:
    page = session.find_agent_page()
    if (
        page is not None
        and _on_agent_url(page)
        and ui.agent_ready(page, timeout_ms=1500)
    ):
        print("  ✓ RingCX agent view already open")
        if focus:
            try:
                page.bring_to_front()
            except Exception:
                pass
        session.remember_page(page)
        return page

    page = session.get_agent_page(focus=focus)

    if ui.agent_ready(page, timeout_ms=1500) and _on_agent_url(page):
        print("  ✓ Session active — RingCX agent UI ready")
        session.remember_page(page)
        return page

    if not _on_agent_url(page):
        print(f"  Navigating to {config.RCX_AGENT_URL}")
        try:
            page.goto(
                config.RCX_AGENT_URL,
                wait_until="domcontentloaded",
                timeout=45_000,
            )
        except Exception as exc:
            if ui.is_target_closed_error(exc):
                page = _refresh_page(session, page)
            elif not ui.is_transient_error(exc):
                raise
            else:
                print("  Page still loading…")
        time.sleep(0.2)
    else:
        print("  On agent URL — waiting for login if needed…")

    deadline = time.time() + config.MANUAL_LOGIN_WAIT_SECONDS
    page = ui.wait_for_login(
        page,
        deadline=deadline,
        refresh=lambda: _refresh_page(session, page),
    )
    session.remember_page(page)
    return page


def morning() -> None:
    run_action("morning")


def lunch() -> None:
    run_action("lunch")


def lunch_end() -> None:
    run_action("lunch-end")


def break_status() -> None:
    run_action("break")


def logout() -> None:
    run_action("logout")


def run_action(action: str, session: RcxBrowserSession | None = None) -> None:
    """Run action. When session is None, routes via browser worker (GUI/CLI-safe)."""
    if session is None:
        from rc_autologin.browser_worker import run_action as worker_run_action

        worker_run_action(action if action != "login" else "morning")
        return

    _run_action_impl(action if action != "login" else "morning", session)


def _run_action_impl(action: str, session: RcxBrowserSession) -> None:
    if action == "login":
        action = "morning"
    quiet = config.QUIET_STATUS_JOBS and action in ("lunch", "lunch-end", "break")

    try:
        if action in ("morning", "login"):
            session.start()
            page = _open_agent_page(session, focus=True)
            page = _with_page_recovery(
                session,
                page,
                lambda p: ui.prepare_agent_session(p, required=True),
            )
            if not ui.is_available(page):
                raise RuntimeError(
                    "Morning login did not reach AVAILABLE — scheduler will retry on catch-up."
                )
            session.remember_page(page)
        elif action == "lunch":
            session.start()
            page = _open_agent_page(session, focus=not quiet)
            page = _with_page_recovery(session, page, ui.go_agent_tab)
            page = _with_page_recovery(session, page, ui.set_lunch)
        elif action == "break":
            session.start()
            page = _open_agent_page(session, focus=not quiet)
            page = _with_page_recovery(session, page, ui.go_agent_tab)
            page = _with_page_recovery(session, page, ui.set_break)
        elif action == "lunch-end":
            session.start()
            page = _open_agent_page(session, focus=not quiet)
            page = _with_page_recovery(session, page, ui.go_agent_tab)
            if not ui.is_available(page):
                page = _with_page_recovery(
                    session,
                    page,
                    lambda p: ui.ensure_available(p, required=True),
                )
        elif action == "logout":
            session.start()
            page = _open_agent_page(session, focus=True)
            page = _with_page_recovery(session, page, ui.go_agent_tab)
            try:
                ui.stop_session(page)
            except Exception as exc:
                if not ui.is_target_closed_error(exc) and not ui.is_transient_error(exc):
                    raise
            session.shutdown_for_day()
            return
        else:
            raise ValueError(f"Unknown action: {action}")

        # Keep Playwright CDP connected for the next GUI click (do NOT detach here).
        session.remember_page(page)
        print("\nDone. RingCX Chrome stays open.")
    except Exception:
        session.forget_page()
        raise
