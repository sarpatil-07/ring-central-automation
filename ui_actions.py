"""Click helpers using selectors.yaml — waits between each action."""

from __future__ import annotations

import re
import time

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeout

import config


def is_target_closed_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "target page, context or browser has been closed" in msg or "target closed" in msg


def page_alive(page: Page | None) -> bool:
    if page is None:
        return False
    try:
        return not page.is_closed()
    except Exception:
        return False


def wait(page: Page, ms: int | None = None) -> None:
    try:
        page.wait_for_timeout(ms or config.CLICK_WAIT_MS)
    except Exception as exc:
        if is_target_closed_error(exc):
            return
        raise


def _locator(page: Page, step: str) -> Locator:
    spec = config.load_selectors()[step]
    xpath = (spec.get("xpath") or "").strip()
    css = (spec.get("css") or "").strip()
    text = (spec.get("text") or "").strip()
    if xpath:
        return page.locator(f"xpath={xpath}").first
    if css:
        return page.locator(css).first
    if text:
        return page.get_by_text(re.compile(f"^{re.escape(text)}$", re.I)).first
    raise ValueError(f"{step}: empty selector in selectors.yaml")


def click(page: Page, step: str, *, timeout_ms: int = 25_000) -> None:
    _locator(page, step).click(timeout=timeout_ms)
    print(f"  ✓ {step}")
    wait(page)


def click_step(page: Page, step: str, *, timeout_ms: int = 25_000) -> None:
    """Click a configured step, searching MAX page + iframes."""
    spec = config.load_selectors()[step]
    xpath = (spec.get("xpath") or "").strip()
    css = (spec.get("css") or "").strip()
    text = (spec.get("text") or "").strip()

    for scope in _scopes(page):
        try:
            if css:
                loc = scope.locator(css)
            elif xpath:
                loc = scope.locator(f"xpath={xpath}")
            elif text:
                loc = scope.get_by_text(re.compile(f"^{re.escape(text)}$", re.I))
            else:
                continue
            if loc.count() == 0:
                continue
            target = loc.first
            if target.is_visible(timeout=2000):
                target.click(timeout=timeout_ms)
                print(f"  ✓ {step}")
                wait(page)
                return
        except Exception:
            continue

    click(page, step, timeout_ms=timeout_ms)


def is_visible(page: Page, step: str, *, timeout_ms: int = 2000) -> bool:
    try:
        return _locator(page, step).is_visible(timeout=timeout_ms)
    except (PlaywrightTimeout, ValueError, KeyError):
        return False


def app_shell_ready(page: Page, *, timeout_ms: int = 2000) -> bool:
    """True when myprofile app picker / MAX entry is visible (SSO fully done)."""
    return is_visible(page, "switch_application", timeout_ms=timeout_ms) or is_visible(
        page, "max_button", timeout_ms=min(timeout_ms, 1000)
    )


def wait_for_step(page: Page, step: str, deadline: float) -> bool:
    while time.time() < deadline:
        if is_visible(page, step, timeout_ms=2000):
            return True
        wait(page, 3000)
    return False


def _scopes(page: Page) -> list:
    """MAX connect UI is often inside an iframe — search page + all frames."""
    return [page, *page.frames]


def _scope_with_selector(page: Page, selector: str):
    """Prefer the frame where the selector is visible, not just present in DOM."""
    fallback = None
    for scope in _scopes(page):
        try:
            loc = scope.locator(selector)
            if loc.count() == 0:
                continue
            if fallback is None:
                fallback = scope
            if loc.first.is_visible(timeout=300):
                return scope
        except Exception:
            continue
    return fallback or page


def _collect_locators(page: Page, selector: str) -> list[Locator]:
    found: list[Locator] = []
    for scope in _scopes(page):
        try:
            loc = scope.locator(selector)
            for i in range(loc.count()):
                found.append(loc.nth(i))
        except Exception:
            continue
    return found


def _is_agent_leg_control(loc: Locator) -> bool:
    """Agent Leg Connect is separate from station connect — never click it."""
    try:
        cls = loc.get_attribute("class") or ""
        if "toggle-leg-button" in cls:
            return True
        aria = (loc.get_attribute("aria-label") or "").lower()
        if "agent leg" in aria:
            return True
    except Exception:
        pass
    return False


def _click_first_clickable(candidates: list[Locator], label: str) -> bool:
    filtered = [btn for btn in candidates if not _is_agent_leg_control(btn)]
    for btn in filtered:
        try:
            if btn.is_visible(timeout=1000):
                btn.click(timeout=15_000)
                print(f"  ✓ {label}")
                return True
        except Exception:
            continue

    for btn in filtered:
        try:
            btn.click(force=True, timeout=5000)
            print(f"  ✓ {label} (force)")
            return True
        except Exception:
            continue

    for btn in filtered:
        try:
            btn.evaluate("node => node.click()")
            print(f"  ✓ {label} (js)")
            return True
        except Exception:
            continue
    return False


def _safe_click(locator: Locator, label: str, *, timeout_ms: int = 5000) -> bool:
    for suffix, kwargs in (
        ("", {"timeout": timeout_ms}),
        (" (force)", {"timeout": timeout_ms, "force": True}),
    ):
        try:
            locator.click(**kwargs)
            print(f"  ✓ {label}{suffix}")
            return True
        except Exception:
            continue
    try:
        locator.evaluate("node => node.click()")
        print(f"  ✓ {label} (js)")
        return True
    except Exception:
        return False


def _run_station_panel_js(page: Page) -> bool:
    script = """
    () => {
      const radio = document.querySelector('#radioStation');
      if (!radio) return false;
      radio.checked = true;
      radio.dispatchEvent(new Event('input', { bubbles: true }));
      radio.dispatchEvent(new Event('change', { bubbles: true }));
      const label = document.querySelector('label[for="radioStation"]');
      if (label) label.click();
      return true;
    }
    """
    activated = False
    for scope in _scopes(page):
        try:
            if scope.evaluate(script):
                activated = True
        except Exception:
            continue
    if activated:
        print("  ✓ activated Station ID panel (js)")
    return activated


def _reveal_connect_panel(page: Page) -> None:
    """Show station connect dialog controls only (not Agent Leg Connect)."""
    _run_station_panel_js(page)
    wait(page, 1000)
    _click_station_id_label(page, force=True)

    for scope in _scopes(page):
        try:
            panel = scope.locator(
                "label[for='radioStation'], #radioStation, button.button.connect, #stationIdText"
            ).first
            if panel.count() > 0:
                panel.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            continue

    field = _station_field(page)
    try:
        if field.count() > 0:
            field.focus(timeout=2000)
    except Exception:
        pass
    wait(page, 500)


def _js_click_connect(page: Page) -> bool:
    script = """
    () => {
      const btn = document.querySelector('button.button.connect:not(.toggle-leg-button)');
      if (!btn) return false;
      const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
      if (aria.includes('agent leg')) return false;
      btn.click();
      return true;
    }
    """
    for scope in _scopes(page):
        try:
            if scope.evaluate(script):
                print("  ✓ connect_button (frame js)")
                return True
        except Exception:
            continue
    return False


def _click_connect_button(page: Page) -> None:
    _reveal_connect_panel(page)

    candidates: list[Locator] = _collect_locators(page, config.STATION_CONNECT_CSS)

    if _click_first_clickable(candidates, "connect_button"):
        wait(page, config.STATUS_WAIT_MS)
        if _is_connected(page):
            print("  Connected successfully")
        return

    if _js_click_connect(page):
        wait(page, config.STATUS_WAIT_MS)
        if _is_connected(page):
            print("  Connected successfully")
        return

    raise RuntimeError(
        "Connect button found in DOM but not clickable. "
        "In MAX window, click Connect manually once, then retry."
    )


def _scope_field(page: Page, field_id: str):
    return _scope_with_selector(page, f"#{field_id}")


def _is_connected(page: Page) -> bool:
    for scope in _scopes(page):
        try:
            body = scope.locator("body").inner_text(timeout=3000)
            if re.search(r"\bconnected\b", body, re.I) and re.search(r"\bdisconnect\b", body, re.I):
                return True
        except Exception:
            continue
    return False


def is_connected(page: Page) -> bool:
    return _is_connected(page)


def get_current_status(page: Page) -> str:
    """Read agent state from the MAX status label (span.current-state)."""
    for scope in _scopes(page):
        try:
            loc = scope.locator("span.current-state").first
            if loc.count() == 0:
                continue
            if loc.is_visible(timeout=1000):
                text = loc.inner_text(timeout=2000).strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def is_agent_available(page: Page) -> bool:
    status = get_current_status(page).lower()
    if not status:
        return False
    if "unavailable" in status or "logout" in status:
        return False
    return "available" in status


def is_agent_lunch(page: Page) -> bool:
    status = get_current_status(page).lower()
    if not status:
        return False
    return "lunch" in status


def set_available_if_needed(page: Page) -> None:
    """Set Available — skip if user already changed status (e.g. back early from lunch)."""
    current = get_current_status(page)
    if is_agent_available(page):
        label = current or "Available"
        print(f"  ✓ already Available ({label}) — no change needed")
        return
    if current:
        print(f"  Status is '{current}' → setting Available")
    set_available(page)


def set_lunch_unavailable_if_needed(page: Page) -> None:
    """Set Lunch — skip if user already on lunch break."""
    current = get_current_status(page)
    if is_agent_lunch(page):
        label = current or "Lunch"
        print(f"  ✓ already on Lunch ({label}) — no change needed")
        return
    if current:
        print(f"  Status is '{current}' → setting Lunch")
    set_lunch_unavailable(page)


def connect_station_if_needed(page: Page, station_id: str | None = None) -> None:
    """Connect only when not already connected."""
    connect_station(page, station_id)


def _click_station_id_label(page: Page, *, force: bool = False) -> None:
    scope = _scope_with_selector(page, "#radioStation")
    label = scope.locator("label[for='radioStation']")
    radio = scope.locator("#radioStation")

    if radio.count() == 0:
        for s in _scopes(page):
            try:
                opt = s.get_by_text(re.compile(r"set\s*station\s*id", re.I)).first
                if opt.is_visible(timeout=2000) and _safe_click(opt, "Set Station ID (text)", timeout_ms=10_000):
                    wait(page)
                    return
            except PlaywrightTimeout:
                continue
        _run_station_panel_js(page)
        return

    if _safe_click(label, "Set Station ID label", timeout_ms=10_000 if not force else 5000):
        wait(page, 1000)
        return

    try:
        radio.check(force=True)
        print("  ✓ checked #radioStation")
    except Exception:
        _run_station_panel_js(page)
    wait(page, 1000)


def _station_field(page: Page) -> Locator:
    field_scope = _scope_field(page, "stationIdText")
    return field_scope.locator("#stationIdText")


def _ensure_station_id(page: Page, station_id: str) -> None:
    """Set station ID even when the input is hidden (Remember Me / saved profile)."""
    field = _station_field(page)
    field.wait_for(state="attached", timeout=15_000)

    if field.is_visible():
        current = field.input_value().strip()
        if current != station_id:
            field.click()
            field.fill(station_id)
            print(f"  ✓ station id entered: {station_id}")
        else:
            print(f"  ✓ station id already set: {station_id}")
        wait(page)
        return

    # Field exists but hidden — common when Station ID is remembered.
    try:
        current = field.input_value().strip()
    except Exception:
        current = ""

    if current == station_id:
        print(f"  ✓ station id remembered (field hidden): {station_id}")
        wait(page)
        return

    print("  Station field hidden — clicking Set Station ID to reveal…")
    _click_station_id_label(page)
    if field.is_visible():
        field.fill(station_id)
        print(f"  ✓ station id entered: {station_id}")
        wait(page)
        return

    # Last resort: force fill hidden input, then verify value.
    field.fill(station_id, force=True)
    try:
        current = field.input_value().strip()
    except Exception:
        current = station_id
    if current != station_id:
        raise RuntimeError(
            f"Could not set station ID to {station_id} — input stays hidden/empty."
        )
    print(f"  ✓ station id set (hidden field): {station_id}")
    wait(page)


def connect_station(page: Page, station_id: str | None = None) -> None:
    """Always pick Station ID (not Phone ID), fill station, Remember Me, Connect."""
    station_id = station_id or config.STATION_ID
    wait(page, 3000)

    if _is_connected(page):
        print("  Already connected — skipping connect dialog")
        return

    has_radio = bool(_collect_locators(page, "#radioStation"))
    has_connect = bool(_collect_locators(page, config.STATION_CONNECT_CSS))
    if not has_radio and not has_connect:
        print("  No connect dialog found — check MAX window loaded fully")
        return

    print("  Connect dialog found — selecting Station ID (not Phone Number)…")
    _select_station_id(page)
    _ensure_station_id(page, station_id)

    remember_scope = _scope_field(page, "cbRememberMe")
    remember = remember_scope.locator("#cbRememberMe")
    try:
        if remember.count() > 0 and not remember.is_checked():
            if remember.is_visible(timeout=2000):
                remember_scope.locator("label[for='cbRememberMe']").click(timeout=5000)
            else:
                remember.check(force=True)
            print("  ✓ Remember Me checked")
            wait(page)
    except PlaywrightTimeout:
        pass

    _click_connect_button(page)


def _select_station_id(page: Page) -> None:
    scope = _scope_with_selector(page, "#radioStation")
    radio = scope.locator("#radioStation")

    if radio.count() == 0:
        _click_station_id_label(page)
        return

    try:
        if radio.is_checked():
            print("  ✓ Station ID radio already selected")
            return
    except Exception:
        pass

    _click_station_id_label(page)
    try:
        if not radio.is_checked():
            radio.check(force=True)
            print("  ✓ checked #radioStation")
    except Exception:
        _run_station_panel_js(page)
    wait(page, 1000)


def open_status_menu(page: Page) -> None:
    click_step(page, "status_menu")


def set_available(page: Page) -> None:
    open_status_menu(page)
    click_step(page, "status_available")
    wait(page, config.STATUS_WAIT_MS)


def set_lunch_unavailable(page: Page) -> None:
    open_status_menu(page)
    click_step(page, "status_unavailable_lunch")
    wait(page, config.STATUS_WAIT_MS)


def _confirm_logout(page: Page) -> None:
    selectors = (
        "button.confirm-button[title='Log out']",
        "div.dialog-contents button.confirm-button",
        "button.confirm-button",
    )
    candidates: list[Locator] = []
    for selector in selectors:
        candidates.extend(_collect_locators(page, selector))

    for scope in _scopes(page):
        try:
            candidates.append(
                scope.get_by_role("button", name=re.compile(r"^log out$", re.I)).first
            )
        except Exception:
            continue

    if _click_first_clickable(candidates, "logout_confirm"):
        wait(page, config.STATUS_WAIT_MS)
        return

    if is_visible(page, "logout_confirm", timeout_ms=3000):
        click_step(page, "logout_confirm")
        wait(page, config.STATUS_WAIT_MS)
        return

    if not page_alive(page):
        print("  ✓ logout_confirm (MAX closed after logout)")
        return

    raise RuntimeError("Logout confirmation dialog found but Confirm could not be clicked.")


def logout(page: Page) -> None:
    open_status_menu(page)
    click_step(page, "status_logout")
    wait(page, 2000)
    _confirm_logout(page)
