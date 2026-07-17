"""Build and install RCAutoLogin.app for the Dock / Applications folder."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from rc_autologin import config
from rc_autologin.release import VERSION, _build_mac_app, build_release

APP_NAME = "RCAutoLogin"


def app_source_path() -> Path:
    return config.BASE_DIR / "dist" / f"{APP_NAME}.app"


def installed_app_path() -> Path:
    return Path.home() / "Applications" / f"{APP_NAME}.app"


def _portable_dir() -> Path:
    return config.BASE_DIR / "dist" / f"{APP_NAME}-{VERSION}-portable"


def _bundle_root_for_app() -> Path:
    """Folder that contains .venv and rc_autologin_run.py."""
    portable = _portable_dir()
    if (portable / "rc_autologin_run.py").exists():
        return portable.resolve()
    return config.BASE_DIR.resolve()


def build_app() -> Path:
    if sys.platform != "darwin":
        raise RuntimeError("RCAutoLogin.app is macOS only. Linux users: ./launch-gui.sh")
    portable = _portable_dir()
    if not portable.exists():
        build_release(include_mac_app=True)
    return _build_mac_app(portable)


def install() -> str:
    if sys.platform != "darwin":
        return "Use ./launch-gui.sh on Linux. Run install.sh once if you have not."
    zip_hint = config.BASE_DIR / "dist" / f"{APP_NAME}-{VERSION}-portable.zip"
    if not zip_hint.exists():
        build_release(include_mac_app=True)
    portable = _portable_dir()
    bundle_root = _bundle_root_for_app()
    app_path = _build_mac_app(portable, bundle_root=bundle_root)
    dest = installed_app_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(app_path, dest)
    return (
        f"Installed {dest}\n"
        f"  Points to: {bundle_root}\n"
        f"  Drag to Dock for quick launch.\n"
        f"  Share dist/{APP_NAME}-{VERSION}-portable.zip with others."
    )


def uninstall() -> str:
    dest = installed_app_path()
    if dest.exists():
        shutil.rmtree(dest)
        return f"Removed {dest}"
    return "RCAutoLogin.app was not installed in ~/Applications."


def status() -> str:
    dest = installed_app_path()
    zip_path = config.BASE_DIR / "dist" / f"{APP_NAME}-{VERSION}-portable.zip"
    lines = []
    if dest.exists():
        lines.append(f"Installed: {dest}")
        root_file = dest / "Contents" / "Resources" / "bundle-root.txt"
        if root_file.exists():
            lines.append(f"  Bundle root: {root_file.read_text(encoding='utf-8').strip()}")
    if zip_path.exists():
        lines.append(f"Shareable zip: {zip_path}")
    return "\n".join(lines) if lines else "Run build-release or install-app first."


def open_from_finder() -> None:
    if sys.platform != "darwin":
        raise RuntimeError("Mac only")
    if not installed_app_path().exists():
        install()
    subprocess.run(["open", str(installed_app_path())], check=False)
