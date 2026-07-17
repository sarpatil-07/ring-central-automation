"""Kill stale RingCX Chrome / clear profile locks before a fresh launch."""

from __future__ import annotations

import signal
import subprocess
import time
from pathlib import Path

from rc_autologin import config

_LOCK_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")


def cdp_healthy() -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{config.CHROME_RCX_CDP_PORT}/json/version",
            timeout=1.2,
        ) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def find_rcx_chrome_pids() -> list[int]:
    profile = str(config.CHROME_RCX_PROFILE_DIR.resolve())
    port = str(config.CHROME_RCX_CDP_PORT)
    pids: set[int] = set()
    for pattern in (profile, f"remote-debugging-port={port}"):
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            try:
                pids.add(int(line.strip().split()[0]))
            except ValueError:
                continue
    return sorted(pids)


def clear_profile_locks(profile_dir: Path | None = None) -> None:
    root = profile_dir or config.CHROME_RCX_PROFILE_DIR
    for name in _LOCK_FILES:
        path = root / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass


def kill_rcx_chrome_processes(*, wait_s: float = 1.0) -> int:
    """SIGTERM then SIGKILL remaining RCX Chrome PIDs. Returns count killed."""
    pids = find_rcx_chrome_pids()
    if not pids:
        return 0
    for pid in pids:
        try:
            import os

            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    time.sleep(wait_s)
    remaining = find_rcx_chrome_pids()
    for pid in remaining:
        try:
            import os

            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    time.sleep(0.2)
    return len(pids)


def cleanup_stale_browser(*, force: bool = False, quiet: bool = False) -> bool:
    """
    Remove orphaned RingCX Chrome and profile locks when CDP is dead or force=True.
    Returns True if cleanup ran.
    """
    healthy = cdp_healthy()
    pids = find_rcx_chrome_pids()
    if not force and healthy and not pids:
        return False
    if not force and healthy:
        return False

    if not quiet:
        if pids:
            print("  Cleaning up stale RingCX Chrome…")
        elif not healthy:
            print("  Clearing stale Chrome profile locks…")

    if pids:
        kill_rcx_chrome_processes()

    try:
        from rc_autologin.browser_session import _stop_playwright

        _stop_playwright()
    except Exception:
        pass

    clear_profile_locks()
    return True


def close_rcx_browser_completely() -> None:
    """User-initiated or logout — kill Chrome and release Playwright."""
    cleanup_stale_browser(force=True, quiet=True)
    kill_rcx_chrome_processes()
    clear_profile_locks()
    try:
        from rc_autologin.browser_session import _stop_playwright

        _stop_playwright()
    except Exception:
        pass
    print("  ✓ RingCX Chrome closed")
