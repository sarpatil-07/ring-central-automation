"""Track which scheduled jobs already ran today (catch-up + dedupe).

State is keyed by action + scheduled HH:MM. Changing WORK_START (etc.)
clears the old slot so a new test time can fire the same day.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from rc_autologin import config

STATE_FILE = config.USER_HOME / "job-last-run.json"


def canonical_action(action: str) -> str:
    return "morning" if action == "login" else action


def _today_key() -> str:
    return datetime.now(config.get_tz()).strftime("%Y-%m-%d")


def scheduled_time_for(action: str) -> str:
    """Current configured HH:MM for this action (from .env)."""
    action = canonical_action(action)
    config.reload_schedule()
    if action == "morning":
        return config.WORK_START
    if action == "lunch":
        return config.LUNCH_START
    if action == "lunch-end":
        return config.LUNCH_END
    if action == "logout":
        return config.WORK_END
    return ""


def _load() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _save(data: dict[str, Any]) -> None:
    config.USER_HOME.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _normalize_entry(value: Any) -> dict[str, str] | None:
    """Accept legacy 'YYYY-MM-DD' string or {'date','time'} object."""
    if isinstance(value, str):
        return {"date": value, "time": ""}
    if isinstance(value, dict):
        date = str(value.get("date") or "")
        time = str(value.get("time") or "")
        if date:
            return {"date": date, "time": time}
    return None


def job_ran_today(action: str, *, scheduled_time: str | None = None) -> bool:
    """True only if this action already ran today for the same schedule slot."""
    action = canonical_action(action)
    slot = scheduled_time if scheduled_time is not None else scheduled_time_for(action)
    entry = _normalize_entry(_load().get(action))
    if entry is None:
        return False
    if entry["date"] != _today_key():
        return False
    # Legacy entries (date only) or mismatched schedule time → allow re-run.
    if not entry["time"] or not slot:
        return False
    return entry["time"] == slot


def mark_job_ran(action: str, *, scheduled_time: str | None = None) -> None:
    action = canonical_action(action)
    slot = scheduled_time if scheduled_time is not None else scheduled_time_for(action)
    data = _load()
    data[action] = {"date": _today_key(), "time": slot}
    _save(data)


def clear_job_ran(action: str) -> None:
    action = canonical_action(action)
    data = _load()
    if action in data:
        del data[action]
        _save(data)


def clear_today_runs() -> None:
    """Clear all job-ran markers (call when schedule times change)."""
    if STATE_FILE.exists():
        try:
            STATE_FILE.unlink()
        except OSError:
            _save({})


def today_run_summary() -> dict[str, Any]:
    data = _load()
    today = _today_key()
    ran: list[str] = []
    for action, value in data.items():
        entry = _normalize_entry(value)
        if entry and entry["date"] == today:
            label = action if not entry["time"] else f"{action}@{entry['time']}"
            ran.append(label)
    return {"date": today, "ran": sorted(ran)}
