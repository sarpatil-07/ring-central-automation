"""Recover stuck MAX Chrome profile locks (hidden/crashed processes)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import config

_LOCK_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")


def _profile_path() -> str:
    return str(config.CHROME_MAX_PROFILE_DIR.resolve())


def find_max_chrome_pids() -> list[int]:
    profile = _profile_path()
    result = subprocess.run(
        ["pgrep", "-f", profile],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pids.append(int(line.split()[0]))
        except ValueError:
            continue
    return sorted(set(pids))


def clear_profile_locks(profile_dir: Path | None = None) -> None:
    root = profile_dir or config.CHROME_MAX_PROFILE_DIR
    for name in _LOCK_FILES:
        path = root / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass


def kill_max_chrome(force: bool = False) -> list[int]:
    pids = find_max_chrome_pids()
    if not pids:
        clear_profile_locks()
        return []

    signal = "-9" if force else "-TERM"
    for pid in pids:
        subprocess.run(["kill", signal, str(pid)], check=False)
    time.sleep(1.5)

    remaining = find_max_chrome_pids()
    if remaining and not force:
        for pid in remaining:
            subprocess.run(["kill", "-9", str(pid)], check=False)
        time.sleep(0.5)
        remaining = find_max_chrome_pids()

    if not remaining:
        clear_profile_locks()
    return pids


def reset_max_browser(*, force: bool = False) -> str:
    """Stop MAX Chrome and clear profile locks. Does NOT log out or delete saved SSO."""
    pids = kill_max_chrome(force=force)
    if pids:
        return (
            f"Stopped MAX Chrome (PIDs: {', '.join(map(str, pids))}). Locks cleared. "
            "Saved login kept — use menu k to force OTP next run."
        )
    clear_profile_locks()
    return (
        "No MAX Chrome process found. Cleared stale locks. "
        "Saved login kept — use menu k to force OTP next run."
    )


def clear_saved_login() -> str:
    """Remove MAX profile data so the next run requires SSO/OTP again."""
    import shutil

    kill_max_chrome(force=True)
    profile = config.CHROME_MAX_PROFILE_DIR
    if profile.exists():
        shutil.rmtree(profile)
    return f"Cleared saved login at {profile}. Next run will require OTP in MAX Chrome."


def is_profile_lock_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "processsingleton" in msg or "profile is already in use" in msg or "singleton" in msg


def max_chrome_running() -> bool:
    return bool(find_max_chrome_pids())


def try_attach_max_cdp(pw) -> BrowserContext | None:
    from playwright.sync_api import BrowserContext

    url = f"http://127.0.0.1:{config.CHROME_MAX_CDP_PORT}"
    try:
        browser = pw.chromium.connect_over_cdp(url)
        if browser.contexts:
            return browser.contexts[0]
        return browser.new_context()
    except Exception:
        return None
