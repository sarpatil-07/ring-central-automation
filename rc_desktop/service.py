"""macOS LaunchAgent for RingCentral desktop UI scheduler."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from rc_desktop import config

LABEL = "com.ringcentralautoset.desktop.scheduler"
PLIST_NAME = f"{LABEL}.plist"
LOG_DIR = config.BASE_DIR / "logs"


def _python_bin() -> Path:
    venv = config.BASE_DIR / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def _run_py() -> Path:
    return config.BASE_DIR / "desktop_run.py"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME


def build_plist() -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [str(_python_bin()), str(_run_py()), "schedule"],
        "WorkingDirectory": str(config.BASE_DIR),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / "desktop-scheduler.log"),
        "StandardErrorPath": str(LOG_DIR / "desktop-scheduler.err.log"),
        "EnvironmentVariables": {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }


def install() -> str:
    if not _run_py().exists():
        raise FileNotFoundError(f"Missing {_run_py()}")
    path = plist_path()
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
    if result.returncode != 0 and "already" not in (result.stderr or "").lower():
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"], check=False)
    return (
        f"Installed {config.DESKTOP_APP_NAME} background scheduler.\n"
        f"  Plist: {path}\n"
        f"  Logs:  {LOG_DIR}/desktop-scheduler.log\n"
        f"Keep RingCentral.app open and logged in."
    )


def uninstall() -> str:
    path = plist_path()
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], check=False)
    if path.exists():
        path.unlink()
    return f"{config.DESKTOP_APP_NAME} background scheduler removed."


def status() -> str:
    path = plist_path()
    if not path.exists():
        return "Not installed. Run: .venv/bin/python desktop_run.py install-service"
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return f"Plist exists but not running.\n  {path}"
    return f"Installed: {path}\n{result.stdout.strip() or 'Running.'}"
