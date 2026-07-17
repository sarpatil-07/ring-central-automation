"""Chrome session — launch mode (no debug port) or optional debug attach."""

from __future__ import annotations

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

import config
from browser_recovery import is_profile_lock_error, reset_max_browser, try_attach_max_cdp


class MaxBrowserSession:
    """One MAX Chrome window for the workday — reuses tabs across scheduled jobs."""

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._context: BrowserContext | None = None
        self._max_page: Page | None = None

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser not started")
        return self._context

    def remember_max_page(self, page: Page) -> None:
        self._max_page = page

    def forget_max_page(self) -> None:
        self._max_page = None

    def _context_alive(self) -> bool:
        if self._context is None:
            return False
        try:
            _ = self._context.pages
            return True
        except Exception:
            return False

    def _ensure_playwright(self) -> Playwright:
        if self._pw is None:
            self._pw = sync_playwright().start()
        return self._pw

    def _attach_existing_chrome(self) -> bool:
        """Reuse MAX Chrome already running on localhost CDP — do not open a new window."""
        self.forget_max_page()
        pw = self._ensure_playwright()
        attached = try_attach_max_cdp(pw)
        if attached is None:
            return False
        self._context = attached
        print("  Reusing existing MAX Chrome window (CDP).")
        return True

    def _drop_dead_session(self) -> None:
        self.forget_max_page()
        self._context = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def _launch(self) -> BrowserContext:
        pw = self._ensure_playwright()
        return pw.chromium.launch_persistent_context(
            user_data_dir=str(config.CHROME_MAX_PROFILE_DIR),
            channel="chrome",
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=[
                f"--remote-debugging-port={config.CHROME_MAX_CDP_PORT}",
                "--remote-allow-origins=*",
                "--start-maximized",
            ],
        )

    def start(self) -> BrowserContext:
        if self._context is not None and self._context_alive():
            return self._context

        if self._context is not None:
            print("  Playwright link lost — reconnecting to MAX Chrome…")
            self._drop_dead_session()

        config.CHROME_MAX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        if config.BROWSER_MODE == "debug":
            pw = self._ensure_playwright()
            print(f"  Mode: debug attach (port {config.CHROME_DEBUG_PORT})")
            browser = pw.chromium.connect_over_cdp(config.CDP_URL)
            self._context = browser.contexts[0] if browser.contexts else browser.new_context()
            return self._context

        if self._attach_existing_chrome():
            return self._context

        print("  Opening MAX Chrome (first launch this shift)")
        print(f"  MAX profile: {config.CHROME_MAX_PROFILE_DIR}")
        print("  Your normal Chrome / other tabs are not used or closed.")

        try:
            self._context = self._launch()
            return self._context
        except Exception as exc:
            if not is_profile_lock_error(exc):
                raise

            print("  MAX profile locked — attaching to existing window…")
            if self._attach_existing_chrome():
                return self._context

            print(f"  {reset_max_browser()}")
            self._context = self._launch()
            print("  Opened new MAX Chrome window.")
            return self._context

    def close(self) -> None:
        if self._context and config.CLOSE_BROWSER_AFTER_RUN:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None
        self.forget_max_page()

    def detach(self) -> None:
        """Leave MAX Chrome open — drop Playwright only (scheduler still running)."""
        self.forget_max_page()
        self._context = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def shutdown_for_day(self) -> None:
        """After logout: close MAX browser. Scheduler stays running for tomorrow."""
        print("\n  End of shift — closing MAX browser until next scheduled job.\n")
        self.forget_max_page()
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    @staticmethod
    def _is_max_url(url: str) -> bool:
        u = url.lower()
        return "max.niceincontact.com" in u or "max.nice-incontact.com" in u

    @staticmethod
    def _is_work_url(url: str) -> bool:
        u = url.lower()
        if MaxBrowserSession._is_max_url(u):
            return False
        return "nice-incontact.com" in u or "niceincontact.com" in u

    def scan_max_pages(self) -> list[Page]:
        pages: list[Page] = []
        for page in self.context.pages:
            try:
                if page.is_closed():
                    continue
                if self._is_max_url(page.url):
                    pages.append(page)
            except Exception:
                continue
        return pages

    def find_max_page(self) -> Page | None:
        if self._max_page is not None:
            try:
                if self._max_page.is_closed():
                    self.forget_max_page()
                elif self._is_max_url(self._max_page.url):
                    return self._max_page
                else:
                    self.forget_max_page()
            except Exception:
                self.forget_max_page()

        ctx = self.start()
        for page in reversed(ctx.pages):
            try:
                if page.is_closed():
                    continue
                if self._is_max_url(page.url):
                    self.remember_max_page(page)
                    return page
            except Exception:
                continue
        return None

    def get_work_page(self, *, focus: bool = True) -> Page:
        """Reuse myprofile/CXone tab — never treat the MAX agent tab as the work tab."""
        ctx = self.start()
        for page in ctx.pages:
            try:
                if page.is_closed():
                    continue
                if self._is_work_url(page.url):
                    print("  Reusing existing work tab")
                    if focus:
                        page.bring_to_front()
                    return page
            except Exception:
                continue

        for page in ctx.pages:
            try:
                if page.is_closed() or self._is_max_url(page.url):
                    continue
                print("  Reusing browser tab")
                if focus:
                    page.bring_to_front()
                return page
            except Exception:
                continue

        page = ctx.new_page()
        print("  Opened work tab in MAX browser")
        return page

    def get_max_page(self, *, focus: bool = True) -> Page | None:
        """Return existing MAX tab for lunch/logout jobs."""
        page = self.find_max_page()
        if page is not None:
            print("  Reusing existing MAX tab" + ("" if focus else " (background)"))
            if focus:
                page.bring_to_front()
        return page
