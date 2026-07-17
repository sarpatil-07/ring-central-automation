"""Resolve RCAutoLogin install root (dev, portable zip, or Mac .app bundle)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def app_root() -> Path:
    """Directory containing rc_autologin_run.py and .venv after install."""
    here = Path(__file__).resolve()
    portable_root = here.parent.parent
    if portable_root.name == "Contents" and (portable_root / "MacOS").is_dir():
        return portable_root.parent.parent
    return portable_root


@lru_cache(maxsize=1)
def user_data_dir() -> Path:
    """Fast local data dir (~/.rcautologin) — Chrome profile, logs."""
    root = Path(os.getenv("RCAUTOLOGIN_HOME", "~/.rcautologin")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def migrate_legacy_profile() -> None:
    """One-time copy from old chrome-rcx-profile next to app folder."""
    import shutil

    marker = user_data_dir() / ".profile_migrated"
    if marker.exists():
        return
    legacy = app_root() / "chrome-rcx-profile"
    target = user_data_dir() / "chrome-rcx-profile"
    legacy_str = str(legacy)
    # Skip slow copy from bundle in Downloads/iCloud — profile lives in ~/.rcautologin instead.
    if any(x in legacy_str for x in ("Downloads", "Mobile Documents", "iCloud")):
        marker.touch(exist_ok=True)
        return
    if legacy.exists() and not target.exists():
        try:
            shutil.copytree(legacy, target)
            print(f"  Migrated Chrome profile to {target}")
        except OSError as exc:
            print(f"  Note: could not migrate Chrome profile: {exc}")
    marker.touch(exist_ok=True)
