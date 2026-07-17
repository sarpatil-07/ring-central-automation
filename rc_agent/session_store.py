"""Persist agent session id between scheduled jobs."""

from __future__ import annotations

import json
from pathlib import Path

from rc_agent import config

DEFAULT_PATH = config.SESSION_FILE


def save(session_id: str, *, path: Path | None = None) -> None:
    target = path or DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"session_id": session_id}, indent=2) + "\n", encoding="utf-8")


def load(*, path: Path | None = None) -> str | None:
    target = path or DEFAULT_PATH
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        sid = str(data.get("session_id", "")).strip()
        return sid or None
    except (json.JSONDecodeError, OSError):
        return None


def clear(*, path: Path | None = None) -> None:
    target = path or DEFAULT_PATH
    if target.exists():
        target.unlink()
