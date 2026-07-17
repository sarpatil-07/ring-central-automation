"""Linux systemd user service for RCAutoLogin scheduler."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rc_autologin import config

SERVICE_NAME = "rcautologin-scheduler.service"
LOG_DIR = config.BASE_DIR / "logs"


def _python_bin() -> Path:
    venv = config.BASE_DIR / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def _run_py() -> Path:
    return config.BASE_DIR / "rc_autologin_run.py"


def service_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME


def plist_path() -> Path:
    return service_path()


def _unit_text() -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return f"""[Unit]
Description=RCAutoLogin RingCX scheduler
After=network.target graphical-session.target

[Service]
Type=simple
WorkingDirectory={config.BASE_DIR}
ExecStart={_python_bin()} {_run_py()} schedule
Restart=always
RestartSec=10
StandardOutput=append:{LOG_DIR}/rc-autologin-scheduler.log
StandardError=append:{LOG_DIR}/rc-autologin-scheduler.err.log

[Install]
WantedBy=default.target
"""


def _run_systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def restart() -> str:
    if not service_path().exists():
        return "Not installed."
    result = _run_systemctl("restart", SERVICE_NAME)
    if result.returncode != 0:
        return f"Restart failed: {result.stderr or result.stdout}"
    return "Background scheduler restarted (picked up new schedule)."


def install() -> str:
    path = service_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_unit_text(), encoding="utf-8")
    _run_systemctl("daemon-reload")
    _run_systemctl("enable", "--now", SERVICE_NAME)
    return (
        f"Installed {config.APP_NAME} background scheduler (systemd user service).\n"
        f"  Runs daily on your saved schedule — GUI can be closed.\n"
        f"  Plist:  {path}\n"
        f"  Logs:  {LOG_DIR}/rc-autologin-scheduler.log\n"
        f"  Tip:   run 'loginctl enable-linger $USER' so it keeps running after logout."
    )


def uninstall() -> str:
    from rc_autologin.scheduler_core import mark_scheduler_stopped

    path = service_path()
    _run_systemctl("disable", "--now", SERVICE_NAME)
    if path.exists():
        path.unlink()
    _run_systemctl("daemon-reload")
    mark_scheduler_stopped()
    return f"{config.APP_NAME} background scheduler stopped."


def status() -> str:
    path = service_path()
    if not path.exists():
        return "Not installed. Run: .venv/bin/python rc_autologin_run.py install-service"
    result = _run_systemctl("status", SERVICE_NAME)
    lines = (result.stdout or result.stderr or "").strip()
    return f"Installed: {path}\n{lines or 'Running.'}"
