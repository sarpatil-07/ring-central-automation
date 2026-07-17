"""Single-thread Playwright worker — sync Playwright must run on one thread only."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable, TypeVar

from rc_autologin.browser_session import RcxBrowserSession
from rc_autologin.browser_cleanup import cleanup_stale_browser

T = TypeVar("T")

_SHUTDOWN = object()

_worker_local = threading.local()
_instance: BrowserWorker | None = None
_instance_lock = threading.Lock()


def on_worker_thread() -> bool:
    return getattr(_worker_local, "ready", False)


class BrowserWorker:
    """Runs all browser/Playwright work on one dedicated thread."""

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[Callable[[], Any], queue.Queue]] = queue.Queue()
        self._session = RcxBrowserSession()
        self._thread = threading.Thread(
            target=self._loop,
            name="rcautologin-browser",
            daemon=False,
        )
        self._thread.start()

    @property
    def session(self) -> RcxBrowserSession:
        return self._session

    def call(self, fn: Callable[[], T], *, timeout: float = 600.0) -> T:
        if on_worker_thread():
            return fn()
        result_q: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
        self._queue.put((fn, result_q))
        try:
            ok, payload = result_q.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError(f"Browser action timed out after {timeout:.0f}s") from exc
        if ok:
            return payload
        raise payload

    def reset(self) -> None:
        """Recover after Playwright thread/greenlet errors."""

        def _reset() -> None:
            try:
                self._session.detach(keep_browser=True)
            except Exception:
                pass
            cleanup_stale_browser(force=True, quiet=True)
            self._session = RcxBrowserSession()

        self.call(_reset, timeout=120.0)

    def _loop(self) -> None:
        _worker_local.ready = True
        while True:
            item = self._queue.get()
            if item is _SHUTDOWN:
                break
            fn, result_q = item
            try:
                result_q.put((True, fn()))
            except Exception as exc:
                if _is_thread_error(exc):
                    try:
                        self._session = RcxBrowserSession()
                    except Exception:
                        pass
                result_q.put((False, exc))


def get_worker() -> BrowserWorker:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = BrowserWorker()
        return _instance


def close_browser() -> None:
    """Close RingCX Chrome and clean up stale processes."""
    worker = get_worker()

    def job() -> None:
        worker.session.close_browser()

    worker.call(job, timeout=30.0)


def shutdown(*, keep_browser: bool = True) -> None:
    """Release Playwright cleanly on the worker thread (avoids Node EPIPE on GUI exit)."""
    global _instance
    with _instance_lock:
        worker = _instance
        _instance = None

    if worker is None:
        try:
            from rc_autologin.browser_session import _stop_playwright

            _stop_playwright()
        except Exception:
            pass
        return

    def cleanup() -> None:
        try:
            if keep_browser:
                worker.session.detach(keep_browser=True)
            else:
                worker.session.close_browser()
        except Exception:
            pass
        try:
            from rc_autologin.browser_session import _stop_playwright

            _stop_playwright()
        except Exception:
            pass

    try:
        worker.call(cleanup, timeout=25.0)
    except Exception:
        try:
            from rc_autologin.browser_session import _stop_playwright

            _stop_playwright()
        except Exception:
            pass

    try:
        worker._queue.put(_SHUTDOWN)
    except Exception:
        pass
    worker._thread.join(timeout=5.0)

    if not keep_browser:
        try:
            cleanup_stale_browser(force=True, quiet=True)
        except Exception:
            pass
    else:
        # Let Playwright's Node driver process exit before Python returns to the shell.
        time.sleep(0.2)


def run_action(action: str) -> None:
    """Run a flow action on the browser worker thread."""
    from rc_autologin.flow import _run_action_impl

    worker = get_worker()

    def job() -> None:
        _run_action_impl(action, worker.session)

    try:
        worker.call(job)
    except Exception as exc:
        if _is_thread_error(exc) or _is_browser_closed_error(exc):
            worker.reset()
            worker.call(job)
            return
        raise


def _is_browser_closed_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(
        x in msg
        for x in (
            "target page, context or browser has been closed",
            "target closed",
            "browser has been closed",
            "connection closed",
        )
    )


def _is_thread_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(
        x in msg
        for x in (
            "different thread",
            "greenlet",
            "cannot switch",
            "thread which happens to have exited",
        )
    )
