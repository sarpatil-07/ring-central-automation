"""RingCX Chrome session — separate profile from MAX / work Chrome."""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from rc_autologin import config
from rc_autologin.browser_cleanup import (
    cleanup_stale_browser,
    close_rcx_browser_completely,
    cdp_healthy,
    clear_profile_locks,
    find_rcx_chrome_pids,
    kill_rcx_chrome_processes,
)

_LOCK_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")
_PLAYWRIGHT_LOCK = threading.Lock()
_GLOBAL_PW: Playwright | None = None


def _find_chrome_binary() -> str | None:
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac).exists():
        return mac
    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        path = shutil.which(name)
        if path:
            return path
    return None


def _cdp_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _clear_locks(profile_dir: Path) -> None:
    clear_profile_locks(profile_dir)


def _find_chrome_pids() -> list[int]:
    return find_rcx_chrome_pids()


def _start_playwright() -> Playwright:
    global _GLOBAL_PW
    with _PLAYWRIGHT_LOCK:
        if _GLOBAL_PW is not None:
            try:
                _ = _GLOBAL_PW.chromium
                return _GLOBAL_PW
            except Exception:
                _GLOBAL_PW = None
        _GLOBAL_PW = sync_playwright().start()
        return _GLOBAL_PW


def _stop_playwright() -> None:
    global _GLOBAL_PW
    with _PLAYWRIGHT_LOCK:
        if _GLOBAL_PW is None:
            return
        try:
            _GLOBAL_PW.stop()
        except Exception:
            pass
        _GLOBAL_PW = None
    # Playwright uses a Node child process; brief wait avoids EPIPE after shell returns.
    time.sleep(0.15)


class RcxBrowserSession:
    """Dedicated RingCX Chrome window — reused across scheduled jobs."""

    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._agent_page: Page | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _is_ringcentral_url(url: str) -> bool:
        return "ringcentral.com" in url.lower()

    @staticmethod
    def _is_rcx_url(url: str) -> bool:
        u = url.lower()
        return "app.ringcentral.com" in u and "ring_cx" in u

    def remember_page(self, page: Page) -> None:
        self._agent_page = page

    def forget_page(self) -> None:
        self._agent_page = None

    def _context_alive(self) -> bool:
        if self._context is None:
            return False
        try:
            _ = self._context.pages
            return True
        except Exception:
            return False

    def _on_new_page(self, page: Page) -> None:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            if self._is_ringcentral_url(page.url):
                self.remember_page(page)
        except Exception:
            pass

    def _attach_cdp(self) -> bool:
        if self._context is not None and self._context_alive():
            return True

        pw = _start_playwright()
        try:
            browser = pw.chromium.connect_over_cdp(config.RCX_CDP_URL)
            self._browser = browser
            self._context = browser.contexts[0] if browser.contexts else browser.new_context()
            try:
                self._context.on("page", self._on_new_page)
            except Exception:
                pass
            self.forget_page()
            print("  Connected to RingCX Chrome (CDP).")
            return True
        except Exception:
            self._browser = None
            self._context = None
            return False

    def _release_playwright_handles(self, *, close_browser: bool = False) -> None:
        self.forget_page()
        ctx = self._context
        browser = self._browser
        self._context = None
        self._browser = None
        if close_browser:
            if ctx:
                try:
                    ctx.close()
                except Exception:
                    pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            for pid in _find_chrome_pids():
                subprocess.run(["kill", "-TERM", str(pid)], check=False)
            kill_rcx_chrome_processes(wait_s=0.5)

    def _spawn_chrome(self) -> None:
        chrome = _find_chrome_binary()
        if not chrome:
            raise RuntimeError(
                "Google Chrome not found. Install Chrome or set CHROME path in PATH."
            )
        profile = config.CHROME_RCX_PROFILE_DIR.resolve()
        profile.mkdir(parents=True, exist_ok=True)
        port = config.CHROME_RCX_CDP_PORT
        print("  Opening RingCX Chrome (RCAutoLogin profile)")
        print(f"  Profile: {profile}")
        print("  Your work Chrome is not used.")
        subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={profile}",
                f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                "--disable-sync",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-translate",
                "--disable-features=TranslateUI",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(50):
            if _cdp_ready(port):
                time.sleep(0.2)
                return
            time.sleep(0.2)
        raise RuntimeError(f"Chrome did not start on CDP port {port}")

    def _launch(self) -> BrowserContext:
        """Fallback: Playwright-owned launch (browser may close on detach)."""
        pw = _start_playwright()
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(config.CHROME_RCX_PROFILE_DIR),
            channel="chrome",
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=[
                f"--remote-debugging-port={config.CHROME_RCX_CDP_PORT}",
                "--remote-allow-origins=*",
                "--start-maximized",
                "--disable-sync",
                "--disable-background-networking",
                "--disable-component-update",
            ],
        )
        self._context = ctx
        try:
            ctx.on("page", self._on_new_page)
        except Exception:
            pass
        return ctx

    def start(self) -> BrowserContext:
        with self._lock:
            if self._context is not None and self._context_alive():
                return self._context

            config.CHROME_RCX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

            # Reconnect when RingCX Chrome is still running.
            if cdp_healthy() and self._attach_cdp():
                return self._context

            # User closed Chrome abruptly or CDP died — clean before relaunch.
            cleanup_stale_browser(force=True)
            self._release_playwright_handles(close_browser=False)

            try:
                self._spawn_chrome()
                if self._attach_cdp():
                    return self._context
            except Exception as exc:
                print(f"  CDP launch note: {exc} — trying Playwright launch…")

            try:
                return self._launch()
            except Exception as exc:
                if "singleton" not in str(exc).lower() and "lock" not in str(exc).lower():
                    raise
                cleanup_stale_browser(force=True, quiet=True)
                if self._attach_cdp():
                    return self._context
                kill_rcx_chrome_processes()
                _clear_locks(config.CHROME_RCX_PROFILE_DIR)
                return self._launch()

    def _pick_live_page(self) -> Page | None:
        ctx = self._context
        if ctx is None:
            return None
        for page in reversed(ctx.pages):
            try:
                if page.is_closed():
                    continue
                if self._is_ringcentral_url(page.url):
                    self.remember_page(page)
                    return page
            except Exception:
                continue
        for page in reversed(ctx.pages):
            try:
                if not page.is_closed():
                    self.remember_page(page)
                    return page
            except Exception:
                continue
        return None

    def find_agent_page(self) -> Page | None:
        if self._agent_page is not None:
            try:
                if not self._agent_page.is_closed() and self._is_ringcentral_url(self._agent_page.url):
                    return self._agent_page
            except Exception:
                self.forget_page()

        self.start()
        page = self._pick_live_page()
        if page is not None and self._is_rcx_url(page.url):
            return page
        return page if page is not None and self._is_ringcentral_url(page.url) else None

    def get_agent_page(self, *, focus: bool = True) -> Page:
        page = self.find_agent_page()
        if page is not None:
            if focus:
                try:
                    page.bring_to_front()
                except Exception:
                    pass
            return page

        ctx = self.start()
        page = self._pick_live_page()
        if page is not None:
            if focus:
                try:
                    page.bring_to_front()
                except Exception:
                    pass
            return page

        page = ctx.new_page()
        self.remember_page(page)
        if focus:
            try:
                page.bring_to_front()
            except Exception:
                pass
        return page

    def refresh_page(self, page: Page | None = None) -> Page:
        """Return a live RingCX page after SSO navigation."""
        if page is not None:
            try:
                if not page.is_closed() and self._is_ringcentral_url(page.url):
                    return page
            except Exception:
                pass
        self.forget_page()
        if self._context is not None and self._context_alive():
            live = self._pick_live_page()
            if live is not None:
                return live
        self._release_playwright_handles(close_browser=False)
        return self.get_agent_page(focus=True)

    def detach(self, *, keep_browser: bool = True) -> None:
        """Release Playwright handles. By default leaves RingCX Chrome open."""
        with self._lock:
            self._release_playwright_handles(close_browser=not keep_browser)
            if keep_browser:
                print("  ✓ RingCX Chrome left open")

    def shutdown_for_day(self) -> None:
        print("\n  End of shift — closing RingCX browser until next job.\n")
        with self._lock:
            self._release_playwright_handles(close_browser=True)
            close_rcx_browser_completely()
            self._context = None
            self._browser = None

    def close_browser(self) -> None:
        """Close RingCX Chrome and release Playwright (fast next launch)."""
        with self._lock:
            self._release_playwright_handles(close_browser=True)
            close_rcx_browser_completely()
            self._context = None
            self._browser = None

    def close(self) -> None:
        if self._context and config.CLOSE_BROWSER_AFTER_RUN:
            self.shutdown_for_day()
        else:
            self.detach()
