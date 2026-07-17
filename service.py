"""macOS LaunchAgent — run scheduler in background on login."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

import config

LABEL = "com.ringcentralautoset.scheduler"
LEGACY_LABEL = "com.nice-max-automation.scheduler"
PLIST_NAME = f"{LABEL}.plist"
LOG_DIR = config.BASE_DIR / "logs"


def _python_bin() -> Path:
    venv = config.BASE_DIR / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def _run_py() -> Path:
    return config.BASE_DIR / "run.py"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME


def _launchctl(label: str, *args: str) -> subprocess.CompletedProcess[str]:
    uid = os.getuid()
    return subprocess.run(
        ["launchctl", *args, f"gui/{uid}/{label}"],
        capture_output=True,
        text=True,
        check=False,
    )


def _remove_legacy_service() -> None:
    _launchctl(LEGACY_LABEL, "bootout")
    legacy = Path.home() / "Library" / "LaunchAgents" / f"{LEGACY_LABEL}.plist"
    if legacy.exists():
        legacy.unlink()


def build_plist() -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [str(_python_bin()), str(_run_py()), "schedule"],
        "WorkingDirectory": str(config.BASE_DIR),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / "scheduler.log"),
        "StandardErrorPath": str(LOG_DIR / "scheduler.err.log"),
        "EnvironmentVariables": {
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }


def install() -> str:
    if not _run_py().exists():
        raise FileNotFoundError(f"Missing { _run_py() }")
    if not _python_bin().exists():
        raise FileNotFoundError("Missing .venv — run: bash setup.sh")

    _remove_legacy_service()

    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(build_plist(), fh)

    _launchctl(LABEL, "bootout")
    bootstrap = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if bootstrap.returncode != 0 and "already" not in (bootstrap.stderr or "").lower():
        # try kickstart if already loaded
        kick = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LABEL}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if kick.returncode != 0:
            raise RuntimeError(bootstrap.stderr or bootstrap.stdout or "launchctl bootstrap failed")

    return (
        f"Installed {config.APP_NAME} background scheduler.\n"
        f"  Plist: {path}\n"
        f"  Logs:  {LOG_DIR}/scheduler.log\n"
        f"Runs on login, executes jobs from .env, logs out and closes browser at WORK_END.\n"
        f"Change shift times only when they change: python run.py menu"
    )


def uninstall() -> str:
    path = plist_path()
    _launchctl(LABEL, "bootout")
    if path.exists():
        path.unlink()
    _remove_legacy_service()
    return f"{config.APP_NAME} background scheduler removed."


def restart() -> str:
    if not plist_path().exists():
        return "Not installed — nothing to restart."
    result = subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return f"Restart failed: {result.stderr or result.stdout}"
    return f"{config.APP_NAME} background scheduler restarted ( picks up new .env times )."


def status() -> str:
    path = plist_path()
    if not path.exists():
        return "Not installed. Run: python run.py install-service"

    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return f"Plist exists but service not running.\n  {path}\n  Try: python run.py install-service"

    lines = [f"{config.APP_NAME} installed: {path}", f"Logs: {LOG_DIR}/scheduler.log", ""]
    lines.append(result.stdout.strip() or "Running.")
    return "\n".join(lines)
