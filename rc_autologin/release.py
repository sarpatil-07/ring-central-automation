"""Build portable RCAutoLogin bundles to share (Mac + Linux)."""

from __future__ import annotations

import plistlib
import shutil
import stat
import sys
import zipfile
from pathlib import Path

from rc_autologin import config

VERSION = "1.1.0"
APP_NAME = "RCAutoLogin"
BUNDLE_ID = "com.rcautologin.gui"

# Paths relative to project root included in shareable zip.
INCLUDE = (
    "rc_autologin",
    "rc_autologin_run.py",
    "rc_autologin.sh",
    "config.py",
    "requirements.txt",
    "README.md",
    "RC_AUTOLOGIN_SETUP.md",
    "SHARE.md",
    "BUILD_AND_SHARE.md",
    "RCAutoLogin_COMPLETE_GUIDE.txt",
    "RCAutoLogin_DEMO_SCRIPT.txt",
    "RCAutoLogin_TEAM_DEMO.md",
    "packaging/install.sh",
    "packaging/pick_python.sh",
    "packaging/launch-gui.sh",
    "packaging/Launch RCAutoLogin.command",
    "packaging/RCAutoLogin.desktop",
)

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".venv",
    ".git",
    "logs",
    "dist",
    "chrome-rcx-profile",
    "chrome-max-profile",
    "chrome-debug-profile",
    "screenshots",
    "node_modules",
    ".cursor",
}
EXCLUDE_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.backup",
    ".DS_Store",
    ".gitignore",
}
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".log", ".pem", ".key", ".sqlite", ".db")


def excluded_user_data_note() -> str:
    return """NOT included in the zip (each user creates their own):
  - .env                 (schedule, login ID/password)
  - chrome-rcx-profile/  (Chrome login session / cookies)
  - .venv/               (Python env — created by install.sh)
  - logs/                (runtime logs)
"""


def _should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    for part in rel.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.name.startswith(".env."):
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def _copy_tree(src: Path, dst: Path) -> None:
    for item in src.rglob("*"):
        if _should_skip(item, src):
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _chmod_scripts(root: Path) -> None:
    for pattern in ("install.sh", "launch-gui.sh", "Launch RCAutoLogin.command", "rc_autologin.sh"):
        for path in root.rglob(pattern):
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _mac_app_launcher() -> str:
    return """#!/bin/bash
set -euo pipefail
APP_MACOS="$(cd "$(dirname "$0")" && pwd)"
RESOURCES="$APP_MACOS/../Resources"
if [[ -f "$RESOURCES/bundle-root.txt" ]]; then
  ROOT="$(cat "$RESOURCES/bundle-root.txt")"
else
  # RCAutoLogin.app lives next to rc_autologin_run.py inside the portable folder
  ROOT="$(cd "$APP_MACOS/../../.." && pwd)"
fi
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  osascript -e 'display dialog "First-time setup — run install.sh in the RCAutoLogin folder, then open the app again." buttons {"OK"} default button 1' || true
  if [[ -x "$ROOT/install.sh" ]]; then
    "$ROOT/install.sh"
  else
    exit 1
  fi
fi
# Fast path — same speed as Launch RCAutoLogin.command (no launch-gui.sh nohup loop).
exec "$PYTHON" rc_autologin_run.py
"""


def _build_mac_app(portable_root: Path, *, bundle_root: Path | None = None) -> Path:
    app_path = portable_root / f"{APP_NAME}.app"
    if app_path.exists():
        shutil.rmtree(app_path)
    macos = app_path / "Contents" / "MacOS"
    resources = app_path / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True, exist_ok=True)
    launcher = macos / APP_NAME
    launcher.write_text(_mac_app_launcher(), encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if bundle_root is not None:
        (resources / "bundle-root.txt").write_text(
            str(bundle_root.resolve()) + "\n",
            encoding="utf-8",
        )
    plist = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    }
    with (app_path / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    return app_path


def _write_share_readme(root: Path) -> None:
    readme = root / "README-FIRST.txt"
    readme.write_text(
        f"""RCAutoLogin {VERSION} — portable bundle (Mac + Linux)
================================================

PREREQUISITES
-------------
  - Python 3.12+ (use 3.12 or 3.13; 3.14+ not supported yet)
  - Google Chrome (or Chromium)
  - Desktop session (Mac/Linux GUI)

QUICK START
-----------
1. Unzip this folder anywhere (e.g. ~/RCAutoLogin)

2. First time only — open Terminal in this folder:
     cd RCAutoLogin-{VERSION}-portable
     chmod +x install.sh launch-gui.sh "Launch RCAutoLogin.command"
     ./install.sh

3. Launch GUI:

   === macOS ===
     ./launch-gui.sh
     # or double-click:  Launch RCAutoLogin.command
     # or:  open RCAutoLogin.app
     # or:  .venv/bin/python rc_autologin_run.py

   === Linux ===
     ./launch-gui.sh
     # or:  .venv/bin/python rc_autologin_run.py

   Browser opens at http://127.0.0.1:8765/

   Tip: Keep the unzipped folder on local disk (e.g. ~/RCAutoLogin),
   not in Downloads/iCloud — faster Python + Chrome startup.

4. One-time setup in the browser (Setup tab):
   - Save your RingCentral login (email + password)
   - Schedule tab → set work/lunch times → Save
   - Today tab → Start auto job

YOUR DATA STAYS ON YOUR MACHINE
-------------------------------
This zip does NOT contain anyone else's login or schedule.
install.sh creates a fresh .env for you.
Chrome profile + logs live in ~/.rcautologin (fast local disk).

Releases: https://github.com/sarpatil-07/ring-central-automation/releases

See BUILD_AND_SHARE.md and SHARE.md for details.
""",
        encoding="utf-8",
    )


def _zip_dir(folder: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in folder.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(folder.parent))


def build_release(*, include_mac_app: bool | None = None) -> Path:
    """Create dist/RCAutoLogin-{version}-portable.zip ready to share."""
    if include_mac_app is None:
        include_mac_app = sys.platform == "darwin"

    project = config.BASE_DIR.resolve()
    dist_dir = project / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    bundle_name = f"{APP_NAME}-{VERSION}-portable"
    staging = dist_dir / bundle_name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    for rel in INCLUDE:
        src = project / rel
        if not src.exists():
            continue
        dst = staging / rel
        if src.is_dir():
            _copy_tree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Flatten launch scripts to bundle root for easy use.
    for name in ("install.sh", "launch-gui.sh", "Launch RCAutoLogin.command"):
        src = staging / "packaging" / name
        if src.exists():
            shutil.copy2(src, staging / name)

    _write_share_readme(staging)
    _chmod_scripts(staging)

    if include_mac_app:
        _build_mac_app(staging)

    zip_path = dist_dir / f"{bundle_name}.zip"
    _zip_dir(staging, zip_path)
    return zip_path


def build_release_message() -> str:
    path = build_release()
    size_mb = path.stat().st_size / (1024 * 1024)
    return (
        f"Shareable bundle ready:\n"
        f"  {path}\n"
        f"  ({size_mb:.1f} MB)\n\n"
        f"Safe to share — user-specific data excluded.\n\n"
        f"{excluded_user_data_note()}\n"
        f"Recipients: unzip → ./install.sh → launch GUI → Setup tab."
    )
