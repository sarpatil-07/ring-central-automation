"""macOS LaunchAgent for RCAutoLogin scheduler."""

from __future__ import annotations

import os
import plistlib
import signal
import subprocess
import sys
import time
from pathlib import Path

from rc_autologin import config

LABEL = "com.rcautologin.scheduler"
PLIST_NAME = f"{LABEL}.plist"
LOG_DIR = config.BASE_DIR / "logs"


def _python_bin() -> Path:
    venv = config.BASE_DIR / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def _run_py() -> Path:
    return config.BASE_DIR / "rc_autologin_run.py"


def service_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME


def plist_path() -> Path:
    return service_path()


def build_plist() -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [str(_python_bin()), str(_run_py()), "schedule"],
        "WorkingDirectory": str(config.BASE_DIR),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / "rc-autologin-scheduler.log"),
        "StandardErrorPath": str(LOG_DIR / "rc-autologin-scheduler.err.log"),
        "EnvironmentVariables": {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }


def is_running() -> bool:
    """True when launchctl reports the scheduler job is loaded."""
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def restart() -> str:
    if not service_path().exists():
        return "Not installed."
    if not is_running():
        uid = os.getuid()
        path = service_path()
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(path)], check=False)
        if is_running():
            return "Background scheduler started (picked up new schedule)."
        return "Plist exists but scheduler is not running — try Stop then Start auto job again."
    result = subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return f"Restart failed: {result.stderr or result.stdout}"
    return "Background scheduler restarted (picked up new schedule)."


def install() -> str:
    from rc_autologin.scheduler_core import mark_scheduler_started

    path = service_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(build_plist(), fh)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], check=False)
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    mark_scheduler_started()
    if result.returncode != 0 and not is_running():
        err = (result.stderr or result.stdout or "unknown error").strip()
        return (
            f"LaunchAgent could not start (GUI scheduler will still run while app is open).\n"
            f"  launchctl: {err}\n"
            f"  Plist was written to: {path}\n"
            f"  Logs: {LOG_DIR}/rc-autologin-scheduler.log"
        )
    return (
        f"Installed {config.APP_NAME} background scheduler (macOS LaunchAgent).\n"
        f"  Runs daily on your saved schedule — GUI can be closed.\n"
        f"  Restarts automatically on Mac login.\n"
        f"  Plist: {path}\n"
        f"  Logs:  {LOG_DIR}/rc-autologin-scheduler.log"
    )


def _kill_orphan_schedule_processes() -> None:
    """Stop leftover `rc_autologin_run.py schedule` if launchctl bootout missed it."""
    run_py = str(_run_py().resolve())
    result = subprocess.run(
        ["pgrep", "-f", f"{run_py} schedule"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        try:
            os.kill(int(line.strip()), signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            continue
    time.sleep(0.3)


def uninstall() -> str:
    from rc_autologin.scheduler_core import mark_scheduler_stopped

    uid = os.getuid()
    path = service_path()
    domain = f"gui/{uid}"
    # Try both bootout forms (macOS versions differ).
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=False)
    if path.exists():
        subprocess.run(["launchctl", "bootout", domain, str(path)], check=False)
    _kill_orphan_schedule_processes()
    if path.exists():
        path.unlink()
    mark_scheduler_stopped()
    if is_running():
        _kill_orphan_schedule_processes()
        time.sleep(0.5)
    if is_running():
        return (
            f"{config.APP_NAME} LaunchAgent plist removed but a scheduler process may still be running.\n"
            f"  Quit and reopen RCAutoLogin, or run:\n"
            f"  launchctl bootout gui/{uid}/{LABEL}"
        )
    return f"{config.APP_NAME} background scheduler stopped."


def status() -> str:
    path = service_path()
    if not path.exists():
        return "Not installed. Run: .venv/bin/python rc_autologin_run.py install-service"
    if not is_running():
        return f"Plist exists but not running.\n  Try Stop auto job, then Start auto job again.\n  {path}"
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return f"Installed and running: {path}\n{result.stdout.strip() or 'Running.'}"
