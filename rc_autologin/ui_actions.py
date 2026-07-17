"""Playwright helpers for RingCX web agent UI."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import yaml
from playwright.sync_api import Locator, Page

from rc_autologin import config


@lru_cache(maxsize=1)
def _load_selectors() -> dict[str, Any]:
    return yaml.safe_load(config.SELECTORS_FILE.read_text(encoding="utf-8")) or {}


def is_target_closed_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "target page, context or browser has been closed" in msg or "target closed" in msg


def is_transient_error(exc: BaseException) -> bool:
    """Navigation / SSO — frames detach; treat as not-ready, not fatal."""
    msg = str(exc).lower()
    return is_target_closed_error(exc) or any(
        x in msg
        for x in (
            "frame was detached",
            "frame has been detached",
            "execution context was destroyed",
            "cannot find context",
            "navigating",
            "navigation",
            "interrupted",
            "detached",
        )
    )


def _safe_scopes(page: Page) -> list:
    """Page + live frames only (skip detached SSO iframes)."""
    scopes: list = [page]
    try:
        for frame in page.frames:
            if frame is page.main_frame:
                continue
            try:
                if not frame.is_detached():
                    scopes.append(frame)
            except Exception:
                continue
    except Exception:
        pass
    return scopes


def page_alive(page: Page | None) -> bool:
    if page is None:
        return False
    try:
        return not page.is_closed()
    except Exception:
        return False


def wait(page: Page, ms: int | None = None) -> None:
    delay = ms if ms is not None else config.CLICK_WAIT_MS
    if delay <= 0:
        return
    try:
        page.wait_for_timeout(delay)
    except Exception as exc:
        if is_target_closed_error(exc):
            return
        raise


def _loc(page: Page, key: str) -> Locator:
    spec = _load_selectors()[key]
    css = (spec.get("css") or "").strip()
    xpath = (spec.get("xpath") or "").strip()
    text = (spec.get("text") or "").strip()
    if css:
        return page.locator(css).first
    if xpath:
        return page.locator(f"xpath={xpath}").first
    if text:
        return page.get_by_text(re.compile(f"^{re.escape(text)}$", re.I)).first
    raise ValueError(f"{key}: no selector")


def _scopes(page: Page) -> list:
    return _safe_scopes(page)


def click_key(page: Page, key: str, *, timeout_ms: int = 15_000) -> None:
    spec = _load_selectors()[key]
    css = (spec.get("css") or "").strip()
    xpath = (spec.get("xpath") or "").strip()
    text = (spec.get("text") or "").strip()
    scan_ms = min(config.SELECTOR_SCAN_MS, timeout_ms)
    last_error: Exception | None = None
    for scope in _safe_scopes(page):
        try:
            if css:
                loc = scope.locator(css)
            elif xpath:
                loc = scope.locator(f"xpath={xpath}")
            elif text:
                loc = scope.get_by_text(re.compile(f"^{re.escape(text)}$", re.I))
            else:
                continue
            target = loc.first
            if target.is_visible(timeout=scan_ms):
                click_loc(page, target, label=key, timeout_ms=timeout_ms)
                return
        except Exception as exc:
            if not is_transient_error(exc):
                last_error = exc
            continue
    if key == "available_menu":
        for scope in _safe_scopes(page):
            try:
                loc = scope.locator('[data-test-automation-id^="rcx-presence-menu-item-"]').filter(
                    has_text=re.compile(r"^AVAILABLE$", re.I)
                )
                target = loc.first
                if target.is_visible(timeout=2000):
                    click_loc(page, target, label=key, timeout_ms=timeout_ms)
                    return
            except Exception:
                continue
    if key == "break_menu":
        for scope in _safe_scopes(page):
            try:
                loc = scope.locator('[data-test-automation-id^="rcx-presence-menu-item-"]').filter(
                    has_text=re.compile(r"^ON-?BREAK$", re.I)
                )
                target = loc.first
                if target.is_visible(timeout=2000):
                    click_loc(page, target, label=key, timeout_ms=timeout_ms)
                    return
            except Exception:
                continue
        for scope in _safe_scopes(page):
            try:
                loc = scope.locator('div[aria-label*="ON-BREAK"]')
                target = loc.first
                if target.is_visible(timeout=2000):
                    click_loc(page, target, label=key, timeout_ms=timeout_ms)
                    return
            except Exception:
                continue
    if last_error and not is_transient_error(last_error):
        raise last_error
    click_loc(page, _loc(page, key), label=key, timeout_ms=timeout_ms)


def click_loc(page: Page, loc: Locator, *, label: str, timeout_ms: int = 25_000) -> None:
    try:
        loc.click(timeout=timeout_ms)
    except Exception as exc:
        if is_target_closed_error(exc):
            raise
        raise
    print(f"  ✓ {label}")
    wait(page)


def fill_key(page: Page, key: str, value: str, *, timeout_ms: int = 12_000) -> None:
    spec = _load_selectors()[key]
    css = (spec.get("css") or "").strip()
    xpath = (spec.get("xpath") or "").strip()
    if not css and not xpath:
        raise ValueError(f"{key}: no selector")
    scan_ms = min(config.SELECTOR_SCAN_MS, timeout_ms)
    last_error: Exception | None = None
    for scope in _safe_scopes(page):
        try:
            loc = scope.locator(css if css else f"xpath={xpath}").first
            if loc.is_visible(timeout=scan_ms):
                loc.fill(value, timeout=timeout_ms)
                print(f"  ✓ {key}")
                wait(page, min(config.CLICK_WAIT_MS, 250))
                return
        except Exception as exc:
            if not is_transient_error(exc):
                last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError(f"Could not fill {key}")


def ensure_checked_key(page: Page, key: str) -> None:
    spec = _load_selectors()[key]
    css = (spec.get("css") or "").strip()
    if not css:
        return
    for scope in _safe_scopes(page):
        try:
            loc = scope.locator(css).first
            if loc.is_visible(timeout=2000):
                if not loc.is_checked():
                    loc.check()
                    print(f"  ✓ {key} (checked)")
                else:
                    print(f"  ✓ {key} (already checked)")
                return
        except Exception:
            continue


def auto_login_configured() -> bool:
    return bool(
        config.RCX_AUTO_LOGIN_ENABLED
        and config.RCX_LOGIN_ID
        and config.RCX_LOGIN_PASSWORD
    )


def rc_authenticated(page: Page) -> bool:
    """True when RingCentral SSO finished (app loaded, not on login/oauth)."""
    if not page_alive(page):
        return False
    url = page.url.lower()
    if "app.ringcentral.com" not in url:
        return False
    if any(x in url for x in ("login", "signin", "sign-in", "oauth", "authorize")):
        return False
    if any(
        is_visible_key(page, k, timeout_ms=500)
        for k in ("login_sign_in", "login_credential", "login_password")
    ):
        return False
    return True


def on_login_screen(page: Page) -> bool:
    if rc_authenticated(page):
        return False
    return any(
        is_visible_key(page, k, timeout_ms=1200)
        for k in ("login_sign_in", "login_credential", "login_password")
    )


def _login_scopes(page: Page) -> list:
    """Prefer main frame, then iframes — RingCentral SSO may use either."""
    return _safe_scopes(page)


def _wait_page_settled(page: Page, *, timeout_ms: int = 12_000) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception:
        pass


def _find_visible_locator(page: Page, selectors: list[str], *, timeout_ms: int = 8000):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for scope in _login_scopes(page):
            for sel in selectors:
                try:
                    loc = scope.locator(sel).first
                    if loc.is_visible(timeout=400):
                        return loc
                except Exception:
                    continue
        time.sleep(0.25)
    return None


def _find_clickable_locator(page: Page, selectors: list[str], *, timeout_ms: int = 20_000):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for scope in _login_scopes(page):
            for sel in selectors:
                try:
                    loc = scope.locator(sel).first
                    if not loc.is_visible(timeout=400):
                        continue
                    if loc.is_enabled():
                        return loc
                except Exception:
                    continue
        time.sleep(0.3)
    return None


_CREDENTIAL_SELECTORS = (
    'input#credential[name="credential"]',
    'input[name="credential"]',
    'input[type="email"]',
    'input[data-test-automation-id="loginCredential"]',
)

_CREDENTIAL_NEXT_SELECTORS = (
    '[data-test-automation-id="loginCredentialNext"]',
    'button[data-test-automation-id="loginCredentialNext"]',
    'input[data-test-automation-id="loginCredentialNext"]',
    'button:has-text("Next")',
    'input[type="submit"][value="Next"]',
    'button[type="submit"]:has-text("Next")',
)

_PASSWORD_SELECTORS = (
    'input#password[name="Password"]',
    'input[name="Password"]',
    'input[type="password"]',
)

_SIGNIN_SELECTORS = (
    '[data-test-automation-id="signInBtn"]',
    'button[data-test-automation-id="signInBtn"]',
    'input[data-test-automation-id="signInBtn"]',
    'button:has-text("Sign in")',
    'button:has-text("Sign In")',
)


def _fill_login_field(page: Page, selectors: tuple[str, ...], value: str, *, label: str) -> bool:
    loc = _find_visible_locator(page, list(selectors), timeout_ms=8000)
    if loc is None:
        return False
    try:
        loc.click(timeout=5000)
        loc.fill("", timeout=5000)
        loc.fill(value, timeout=8000)
        try:
            loc.dispatch_event("input")
            loc.dispatch_event("change")
        except Exception:
            pass
        print(f"  ✓ {label}")
        wait(page, config.LOGIN_STEP_WAIT_MS)
        return True
    except Exception as exc:
        if is_transient_error(exc):
            return False
        raise


def _submit_login_step(
    page: Page,
    *,
    field_selectors: tuple[str, ...],
    button_selectors: tuple[str, ...],
    label: str,
) -> bool:
    """Press Enter on the active field, then try Next/Sign-in buttons."""
    for scope in _login_scopes(page):
        for sel in field_selectors:
            try:
                loc = scope.locator(sel).first
                if loc.is_visible(timeout=800):
                    loc.press("Enter")
                    print(f"  ✓ {label} (Enter)")
                    wait(page, config.LOGIN_STEP_WAIT_MS + 300)
                    return True
            except Exception:
                continue

    btn = _find_clickable_locator(page, list(button_selectors), timeout_ms=22_000)
    if btn is None:
        return False
    try:
        btn.click(timeout=12_000)
        print(f"  ✓ {label}")
        wait(page, config.LOGIN_STEP_WAIT_MS + 300)
        return True
    except Exception as exc:
        if is_transient_error(exc):
            return False
        raise


def try_auto_login(page: Page) -> bool:
    """Run RingCentral sign-in steps when credentials are configured."""
    if not auto_login_configured():
        return False
    if rc_authenticated(page):
        return True

    print("  Attempting automatic RingCentral login…")
    _wait_page_settled(page)

    try:
        if is_visible_key(page, "login_sign_in", timeout_ms=2000):
            click_key(page, "login_sign_in", timeout_ms=20_000)
            wait(page, config.LOGIN_STEP_WAIT_MS)
            _wait_page_settled(page)

        if is_visible_key(page, "login_credential", timeout_ms=4000) or _find_visible_locator(
            page, list(_CREDENTIAL_SELECTORS), timeout_ms=3000
        ):
            if not _fill_login_field(page, _CREDENTIAL_SELECTORS, config.RCX_LOGIN_ID, label="login_credential"):
                fill_key(page, "login_credential", config.RCX_LOGIN_ID)
            if not _submit_login_step(
                page,
                field_selectors=_CREDENTIAL_SELECTORS,
                button_selectors=_CREDENTIAL_NEXT_SELECTORS,
                label="login_credential_next",
            ):
                print("  Next button not ready — press Next manually in Chrome if shown")

        _wait_page_settled(page)

        if is_visible_key(page, "login_password", timeout_ms=5000) or _find_visible_locator(
            page, list(_PASSWORD_SELECTORS), timeout_ms=4000
        ):
            if not _fill_login_field(page, _PASSWORD_SELECTORS, config.RCX_LOGIN_PASSWORD, label="login_password"):
                fill_key(page, "login_password", config.RCX_LOGIN_PASSWORD)
            ensure_checked_key(page, "login_stay_signed_in")
            if not _submit_login_step(
                page,
                field_selectors=_PASSWORD_SELECTORS,
                button_selectors=_SIGNIN_SELECTORS,
                label="login_sign_in_submit",
            ):
                click_key(page, "login_sign_in_submit", timeout_ms=20_000)
    except Exception as exc:
        if is_target_closed_error(exc):
            raise
        print(f"  Auto-login step issue: {exc}")
        print("  Complete remaining steps manually in RingCX Chrome…")

    return rc_authenticated(page)


def is_visible_key(page: Page, key: str, *, timeout_ms: int = 2000) -> bool:
    if not page_alive(page):
        return False
    try:
        spec = _load_selectors()[key]
    except KeyError:
        return False
    css = (spec.get("css") or "").strip()
    xpath = (spec.get("xpath") or "").strip()
    if not css and not xpath:
        return False
    per_scope_ms = min(max(timeout_ms // 4, 120), config.SELECTOR_SCAN_MS)
    # Main page first — faster during login (skip detached iframes until needed)
    try:
        loc = page.locator(css if css else f"xpath={xpath}").first
        if loc.is_visible(timeout=per_scope_ms):
            return True
    except Exception as exc:
        if not is_transient_error(exc):
            pass
    if per_scope_ms >= timeout_ms:
        return False
    for scope in _safe_scopes(page):
        if scope is page:
            continue
        try:
            loc = scope.locator(css if css else f"xpath={xpath}").first
            if loc.is_visible(timeout=per_scope_ms):
                return True
        except Exception:
            continue
    return False


def agent_ready(page: Page, *, timeout_ms: int = 3000) -> bool:
    try:
        url = page.url.lower()
        on_agent = "ring_cx" in url and "agent" in url
    except Exception:
        on_agent = False
    if is_visible_key(page, "presence_pill", timeout_ms=timeout_ms):
        return True
    if on_agent and is_visible_key(page, "agent_tab", timeout_ms=min(timeout_ms, 1200)):
        return True
    return False


def logged_in(page: Page) -> bool:
    """True when RingCX agent page is ready (not just SSO landing page)."""
    if not page_alive(page):
        return False
    url = page.url.lower()
    if "app.ringcentral.com" not in url:
        return False
    if any(x in url for x in ("login", "signin", "sign-in", "oauth", "authorize")):
        return False
    return agent_ready(page, timeout_ms=1200)


def _presence_pill(page: Page):
    return page.locator('[data-test-automation-id="rcx-presence-pill"]').first


def _pill_state(page: Page) -> tuple[str, str, str]:
    """Return (inner_text, aria_label, connectstate) for presence pill."""
    try:
        pill = _presence_pill(page)
        if not pill.is_visible(timeout=800):
            return "", "", ""
        text = (pill.inner_text(timeout=1500) or "").upper()
        aria = (pill.get_attribute("aria-label") or "").upper()
        connect = (
            pill.get_attribute("connectstate")
            or pill.get_attribute("data-connectstate")
            or pill.get_attribute("data-connect-state")
            or ""
        ).lower()
        return text, aria, connect
    except Exception:
        return "", "", ""


def is_connected(page: Page) -> bool:
    if is_visible_key(page, "connected_pill", timeout_ms=600):
        return True
    text, aria, connect = _pill_state(page)
    if connect == "connected":
        return True
    if any(k in text for k in ("AVAILABLE", "LUNCH", "BUSY", "AWAY", "MEETING", "BREAK", "ON-BREAK", "ON BREAK")):
        return True
    if any(k in aria for k in ("AVAILABLE", "LUNCH", "STATUS", "ON-BREAK", "ON BREAK", "BREAK")):
        return True
    if "START SESSION" in text or "DISCONNECTED" in text or connect == "disconnected":
        return False
    if "START" in text:
        return False
    return False


def is_available(page: Page) -> bool:
    if is_visible_key(page, "available_label", timeout_ms=500):
        return True
    text, aria, _ = _pill_state(page)
    if "AVAILABLE" in text or "AVAILABLE" in aria:
        return True
    if not is_connected(page):
        return False
    try:
        pill = _loc(page, "connected_pill")
        label = pill.locator('p.rcx-pill-label[title="AVAILABLE"]').first
        if label.is_visible(timeout=800):
            return True
    except Exception:
        pass
    try:
        pill = _presence_pill(page)
        if pill.get_by_text(re.compile(r"^AVAILABLE$", re.I)).first.is_visible(timeout=800):
            return True
    except Exception:
        pass
    return False


def wait_for_login(
    page: Page,
    *,
    deadline: float,
    refresh: Callable[[], Page] | None = None,
) -> Page:
    """Wait up to deadline for login. Auto-fills credentials when configured."""
    if rc_authenticated(page):
        print("  ✓ Already logged in — proceeding")
        return page

    auto_tried = False
    manual_hint = False

    if not auto_login_configured():
        print("")
        print("  Complete RingCentral login in the RingCX Chrome window.")
        print(f"  Waiting up to {config.MANUAL_LOGIN_WAIT_SECONDS // 60} minutes…")
        print("  Tip: add login ID/password in the GUI to enable auto sign-in.")
        print("")

    while time.time() < deadline:
        try:
            if not page_alive(page):
                if refresh:
                    print("  Page changed — reconnecting to RingCX Chrome…")
                    page = refresh()
                    continue
                raise RuntimeError("RingCX browser closed during login wait")
            if rc_authenticated(page):
                print("  ✓ Login complete — proceeding")
                return page

            if auto_login_configured() and on_login_screen(page):
                try:
                    try_auto_login(page)
                except Exception as exc:
                    if is_target_closed_error(exc):
                        if refresh:
                            print("  Browser tab changed — reconnecting…")
                            page = refresh()
                            continue
                        raise RuntimeError("RingCX browser closed during login wait") from exc
                    if not is_transient_error(exc):
                        print(f"  Auto-login: {exc}")
                        print("  Continue sign-in in RingCX Chrome…")
                auto_tried = True
                if rc_authenticated(page):
                    print("  ✓ Auto login complete — proceeding")
                    return page
            elif auto_login_configured() and auto_tried and not manual_hint:
                print("  Complete MFA/OTP in RingCX Chrome if prompted…")
                manual_hint = True
        except Exception as exc:
            if is_target_closed_error(exc):
                if refresh:
                    print("  Browser tab changed — reconnecting…")
                    page = refresh()
                    continue
                raise RuntimeError("RingCX browser closed during login wait") from exc
            if not is_transient_error(exc):
                raise
        time.sleep(config.LOGIN_POLL_SECONDS)

    if auto_login_configured() and auto_tried:
        raise RuntimeError(
            "Auto login did not finish (MFA/OTP may be required). "
            "Complete login in RingCX Chrome, then run Login again."
        )

    raise RuntimeError(
        f"Login not finished within {config.MANUAL_LOGIN_WAIT_SECONDS // 60} minutes. "
        "Complete login in RingCX Chrome, then run morning again."
    )


def wait_for_connected(page: Page, *, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if is_connected(page):
                return True
        except Exception as exc:
            if not is_transient_error(exc):
                raise
        time.sleep(0.4)
    return False


def wait_for_available(page: Page, *, timeout: float | None = None) -> bool:
    deadline = time.time() + (timeout if timeout is not None else config.CONNECT_WAIT_SECONDS)
    while time.time() < deadline:
        try:
            if is_available(page):
                return True
            if is_connected(page):
                time.sleep(0.4)
                if is_available(page):
                    return True
        except Exception as exc:
            if not is_transient_error(exc):
                raise
        time.sleep(0.35)
    return False


def _click_available_menu(page: Page) -> None:
    open_presence_menu(page)
    wait(page, min(config.STATUS_WAIT_MS, 500))
    click_key(page, "available_menu")
    wait(page, min(config.STATUS_WAIT_MS, 500))


def _click_start_session(page: Page) -> None:
    if is_visible_key(page, "start_session", timeout_ms=1500):
        click_key(page, "start_session")
        wait(page, 500)
        return
    text, _, connect = _pill_state(page)
    needs_start = connect == "disconnected" or "START" in text or not is_connected(page)
    if is_visible_key(page, "presence_start_session", timeout_ms=800):
        click_key(page, "presence_start_session")
        wait(page, 500)
        return
    if needs_start:
        _open_presence_menu(page)
        wait(page, 500)
        if is_visible_key(page, "presence_start_session", timeout_ms=2500):
            click_key(page, "presence_start_session")
            wait(page, 500)
            return
        for scope in _safe_scopes(page):
            try:
                loc = scope.get_by_text(re.compile(r"start\s*session", re.I)).first
                if loc.is_visible(timeout=1500):
                    click_loc(page, loc, label="Start session")
                    wait(page, 500)
                    return
            except Exception:
                continue
        if is_visible_key(page, "start_session", timeout_ms=1500):
            click_key(page, "start_session")
            wait(page, 500)


def _presence_menu_open(page: Page) -> bool:
    return is_visible_key(page, "presence_menu", timeout_ms=500)


def _dismiss_presence_menu(page: Page) -> None:
    if not _presence_menu_open(page):
        return
    try:
        page.keyboard.press("Escape")
        wait(page, 250)
    except Exception:
        pass


def _open_presence_menu(page: Page) -> None:
    if _presence_menu_open(page):
        return
    try:
        click_key(page, "presence_pill")
    except Exception as exc:
        msg = str(exc).lower()
        if "intercepts pointer" in msg or "timeout" in msg:
            _dismiss_presence_menu(page)
            click_key(page, "presence_pill")
        else:
            raise
    wait(page, min(config.STATUS_WAIT_MS, 400))


def _presence_menu_root(page: Page) -> Locator:
    return page.locator('[data-test-automation-id="rcx-presence-menu"]')


def _click_loc_menu(page: Page, loc: Locator, *, label: str, timeout_ms: int = 15_000) -> None:
    try:
        loc.click(timeout=timeout_ms)
    except Exception as exc:
        msg = str(exc).lower()
        if "intercepts pointer" in msg or "not stable" in msg:
            loc.click(force=True, timeout=timeout_ms)
        elif is_target_closed_error(exc):
            raise
        else:
            raise
    print(f"  ✓ {label}")
    wait(page)


def _click_presence_menu_item(
    page: Page,
    *,
    menu_key: str,
    status_label: str,
    display: str,
) -> bool:
    _open_presence_menu(page)
    wait(page, min(config.STATUS_WAIT_MS, 400))
    menu = _presence_menu_root(page)

    try:
        spec = _load_selectors()[menu_key]
    except KeyError:
        spec = {}

    for sel in (spec.get("css") or "").split(","):
        sel = sel.strip()
        if not sel:
            continue
        try:
            loc = menu.locator(sel).first
            if loc.is_visible(timeout=1500):
                _click_loc_menu(page, loc, label=display)
                return True
        except Exception:
            continue

    xpath = (spec.get("xpath") or "").strip()
    if xpath:
        try:
            loc = menu.locator(f"xpath={xpath}").first
            if loc.is_visible(timeout=1500):
                _click_loc_menu(page, loc, label=display)
                return True
        except Exception:
            pass

    text_patterns = [re.compile(rf"^{re.escape(status_label)}$", re.I)]
    if status_label.upper().replace("-", "") == "ONBREAK":
        text_patterns.append(re.compile(r"^ON-?BREAK$", re.I))

    for pattern in text_patterns:
        try:
            loc = menu.locator('[data-test-automation-id^="rcx-presence-menu-item-"]').filter(
                has_text=pattern
            ).first
            if loc.is_visible(timeout=1500):
                _click_loc_menu(page, loc, label=display)
                return True
        except Exception:
            continue
        try:
            loc = menu.get_by_text(pattern).first
            if loc.is_visible(timeout=1500):
                _click_loc_menu(page, loc, label=display)
                return True
        except Exception:
            continue

    return False


def _set_available_via_menu(page: Page) -> None:
    _open_presence_menu(page)
    if is_visible_key(page, "available_menu", timeout_ms=2000):
        click_key(page, "available_menu")
        return
    for scope in _safe_scopes(page):
        try:
            loc = scope.get_by_text(re.compile(r"^AVAILABLE$", re.I)).first
            if loc.is_visible(timeout=1500):
                click_loc(page, loc, label="AVAILABLE")
                return
        except Exception:
            continue
    click_key(page, "available_menu")


def open_agent_view(page: Page) -> None:
    """Open RingCX agent URL and wait for agent UI."""
    try:
        url = page.url.lower()
        if "ring_cx" in url and "agent" in url and agent_ready(page, timeout_ms=1500):
            return
    except Exception:
        pass
    print(f"  Opening agent view…")
    try:
        page.goto(
            config.RCX_AGENT_URL,
            wait_until="domcontentloaded",
            timeout=45_000,
        )
    except Exception as exc:
        if not is_transient_error(exc) and not is_target_closed_error(exc):
            raise
    wait(page, 600)
    deadline = time.time() + 25
    while time.time() < deadline:
        if agent_ready(page, timeout_ms=800):
            print("  ✓ Agent view loaded")
            return
        time.sleep(0.35)
    print("  Agent view still loading…")


def prepare_agent_session(page: Page, *, required: bool = False) -> bool:
    """Agent tab → Start session → AVAILABLE (full morning flow)."""
    open_agent_view(page)
    go_agent_tab(page)
    wait(page, 500)

    if is_available(page):
        print("  ✓ Already AVAILABLE")
        return True

    for attempt in range(1, 4):
        if is_connected(page):
            break
        print(f"  Starting agent session (attempt {attempt}/3)…")
        _click_start_session(page)
        if wait_for_connected(page, timeout=12):
            break
        wait(page, 600)

    if not is_available(page):
        print("  Setting AVAILABLE…")
        _set_available_via_menu(page)
        wait_for_available(page, timeout=18)

    if is_available(page):
        print("  ✓ AVAILABLE")
        return True

    msg = "Finish Start session + AVAILABLE in RingCX Chrome if still needed."
    if required:
        raise RuntimeError(msg)
    print(f"  ⚠ {msg}")
    return False


def ensure_available(page: Page, *, required: bool = False) -> bool:
    """Try to reach AVAILABLE (assumes already on agent view)."""
    if is_available(page):
        print("  ✓ Already AVAILABLE")
        return True

    if not is_connected(page):
        print("  Starting agent session…")
        _click_start_session(page)
        wait_for_connected(page, timeout=18)

    if not is_available(page):
        print("  Setting AVAILABLE…")
        _set_available_via_menu(page)
        wait_for_available(page, timeout=18)

    if is_available(page):
        print("  ✓ AVAILABLE")
        return True

    msg = (
        "Could not confirm AVAILABLE — click Start session then AVAILABLE in RingCX Chrome."
    )
    if required:
        raise RuntimeError(msg)
    print(f"  ⚠ {msg}")
    return False


def go_agent_tab(page: Page) -> None:
    open_agent_view(page)
    try:
        tab = _loc(page, "agent_tab")
        selected = tab.get_attribute("aria-current") == "page"
        if not selected:
            try:
                selected = tab.evaluate(
                    "el => el.classList.contains('Mui-selected') || el.classList.contains('RcListItem-selected')"
                )
            except Exception as exc:
                if not is_transient_error(exc):
                    raise
                selected = False
        if selected:
            print("  ✓ Already on Agent tab")
            return
        click_loc(page, tab, label="Agent tab")
    except Exception as exc:
        if is_transient_error(exc):
            click_key(page, "agent_tab")
            return
        raise


def start_session(page: Page) -> None:
    if is_connected(page):
        print("  ✓ Session already started")
        return
    _click_start_session(page)
    wait(page, 400)


def open_presence_menu(page: Page) -> None:
    _open_presence_menu(page)


def set_lunch(page: Page) -> None:
    _set_presence_status(page, menu_key="lunch_menu", status_label="LUNCH", display="Lunch/Dinner")


def set_break(page: Page) -> None:
    _set_presence_status(page, menu_key="break_menu", status_label="ON-BREAK", display="Break")


def _set_presence_status(
    page: Page,
    *,
    menu_key: str,
    status_label: str,
    display: str,
) -> None:
    if not is_connected(page):
        raise RuntimeError("Not connected — run morning first")
    if _click_presence_menu_item(
        page,
        menu_key=menu_key,
        status_label=status_label,
        display=display,
    ):
        return
    raise RuntimeError(f"Could not find {display} in presence menu — open RingCX and try manually")


def stop_session(page: Page) -> None:
    if is_visible_key(page, "start_session", timeout_ms=1500):
        print("  ✓ Already disconnected")
        return
    if not is_connected(page):
        print("  ✓ No active session")
        return
    open_presence_menu(page)
    wait(page, config.STATUS_WAIT_MS)
    click_key(page, "stop_session")
    print("  ✓ Stop session")
