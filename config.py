"""Load settings and UI selectors."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "RingCentralAutoSet"
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
SELECTORS_FILE = Path(os.getenv("SELECTORS_FILE", str(BASE_DIR / "selectors.yaml")))

CXONE_AUTH_URL = os.getenv(
    "CXONE_AUTH_URL",
    "https://cxone.niceincontact.com/auth/authorize"
    "?scope=openid&response_type=code"
    "&client_id=0b697ebb-4ea2-4052-b12b-d3cf12a53eca"
    "&redirect_uri=https%3A%2F%2Fcxone.niceincontact.com%2Fua%2Fv1%2Fcallback",
)
MYPROFILE_URL = os.getenv(
    "MYPROFILE_URL",
    "https://na1.nice-incontact.com/apps/#/myprofile/",
)
STATION_ID = os.getenv("STATION_ID", "14065216")

# Separate MAX-only Chrome (not your daily work browser)
CHROME_MAX_PROFILE_DIR = Path(
    os.getenv(
        "CHROME_MAX_PROFILE_DIR",
        str(BASE_DIR / "chrome-max-profile"),
    )
).expanduser()

# launch = Playwright opens Chrome (no debug port — recommended)
# debug  = attach to port 9222 (legacy — only if you use start-max-chrome.sh)
BROWSER_MODE = os.getenv("BROWSER_MODE", "launch").strip().lower()
CHROME_DEBUG_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
CDP_URL = f"http://127.0.0.1:{CHROME_DEBUG_PORT}"
# Localhost-only port so scheduler can reconnect to the same MAX window
CHROME_MAX_CDP_PORT = int(os.getenv("CHROME_MAX_CDP_PORT", "9333"))
MAX_CDP_URL = f"http://127.0.0.1:{CHROME_MAX_CDP_PORT}"

CLOSE_BROWSER_AFTER_RUN = os.getenv("CLOSE_BROWSER_AFTER_RUN", "false").lower() in {
    "1",
    "true",
    "yes",
}

# OTP login manual each morning in MAX browser only
MANUAL_LOGIN_WAIT_SECONDS = int(os.getenv("MANUAL_LOGIN_WAIT_SECONDS", "600"))

CLICK_WAIT_MS = int(os.getenv("CLICK_WAIT_MS", "3000"))
STATUS_WAIT_MS = int(os.getenv("STATUS_WAIT_MS", "5000"))

TIMEZONE = os.getenv("TIMEZONE", "IST")

# Short names → IANA timezone (scheduler uses IANA internally)
TIMEZONE_ALIASES: dict[str, str] = {
    "ist": "Asia/Kolkata",
    "india": "Asia/Kolkata",
    "apac": "Asia/Singapore",
    "emea": "Europe/London",
    "latam": "America/Sao_Paulo",
    "na": "America/New_York",
    # NA sub-zones
    "na-eastern": "America/New_York",
    "na-central": "America/Chicago",
    "na-mountain": "America/Denver",
    "na-pacific": "America/Los_Angeles",
    # APAC cities
    "apac-india": "Asia/Kolkata",
    "apac-singapore": "Asia/Singapore",
    "apac-manila": "Asia/Manila",
    "apac-tokyo": "Asia/Tokyo",
    "apac-sydney": "Australia/Sydney",
    # EMEA cities
    "emea-london": "Europe/London",
    "emea-berlin": "Europe/Berlin",
    "emea-paris": "Europe/Paris",
    # LATAM cities
    "latam-saopaulo": "America/Sao_Paulo",
    "latam-mexico": "America/Mexico_City",
    "latam-bogota": "America/Bogota",
}
WORK_START = os.getenv("WORK_START", "09:00")
WORK_END = os.getenv("WORK_END", "18:00")
LUNCH_START = os.getenv("LUNCH_START", "13:00")
LUNCH_END = os.getenv("LUNCH_END", "14:00")
LUNCH_ENABLED = os.getenv("LUNCH_ENABLED", "true").lower() in {"1", "true", "yes"}
AUTORUN_PAUSED = os.getenv("AUTORUN_PAUSED", "false").lower() in {"1", "true", "yes"}
LEAVE_DATE = os.getenv("LEAVE_DATE", "").strip()  # YYYY-MM-DD — skip all jobs that day
QUIET_STATUS_JOBS = os.getenv("QUIET_STATUS_JOBS", "true").lower() in {"1", "true", "yes"}

# Station connect only — never Agent Leg Connect (button.toggle-leg-button)
STATION_CONNECT_CSS = "button.button.connect:not(.toggle-leg-button)"

WORK_DAYS = os.getenv("WORK_DAYS", "mon,tue,wed,thu,fri")
TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")

DAY_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


@dataclass(frozen=True)
class ScheduleJob:
    job_id: str
    label: str
    hour: int
    minute: int
    action: str


def _timezone_token(value: str) -> str:
    """Strip display labels like 'IST (India)' down to 'IST'."""
    raw = value.strip()
    if "(" in raw:
        raw = raw.split("(", 1)[0].strip()
    return raw


def canonical_timezone(value: str) -> str:
    """Return a clean value safe to store in .env."""
    raw = _timezone_token(value)
    if not raw:
        raise ValueError("TIMEZONE cannot be empty")
    resolve_timezone(raw)
    key = raw.lower().replace(" ", "")
    if key in TIMEZONE_ALIASES:
        return key.upper() if key in {"ist", "apac", "emea", "latam", "na"} else raw
    return raw


def resolve_timezone(value: str | None = None) -> str:
    """Map IST/APAC/EMEA/LATAM/NA (or IANA name) to a pytz timezone string."""
    import pytz

    raw = _timezone_token(value if value is not None else TIMEZONE)
    if not raw:
        raise ValueError("TIMEZONE cannot be empty")
    key = raw.lower().replace(" ", "")
    if key in TIMEZONE_ALIASES:
        return TIMEZONE_ALIASES[key]
    try:
        pytz.timezone(raw)
        return raw
    except Exception as exc:
        known = ", ".join(sorted({k.split("-")[0].upper() for k in TIMEZONE_ALIASES}))
        raise ValueError(
            f"Unknown timezone {raw!r}. Use {known}, or an IANA name like Asia/Kolkata."
        ) from exc


def get_tz():
    import pytz

    return pytz.timezone(resolve_timezone())


def format_timezone(value: str | None = None) -> str:
    raw = _timezone_token(value if value is not None else TIMEZONE)
    iana = resolve_timezone(raw)
    key = raw.lower().replace(" ", "")
    if key in TIMEZONE_ALIASES:
        return f"{key.upper()} ({iana})"
    return iana


def load_selectors() -> dict:
    if not SELECTORS_FILE.exists():
        raise FileNotFoundError(f"No selectors file: {SELECTORS_FILE}")
    return yaml.safe_load(SELECTORS_FILE.read_text(encoding="utf-8")) or {}


def parse_time(value: str, field: str) -> tuple[int, int]:
    match = TIME_PATTERN.match(value.strip())
    if not match:
        raise ValueError(f"{field} must be HH:MM (got {value!r})")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"{field} invalid time: {value!r}")
    return hour, minute


def _minutes(h: int, m: int) -> int:
    return h * 60 + m


def parse_work_days(value: str, field: str = "WORK_DAYS") -> str:
    raw = value.strip().lower().replace(" ", "")
    if not raw:
        raise ValueError(f"{field} cannot be empty")

    if "-" in raw and "," not in raw:
        start, end = raw.split("-", 1)
        if start in DAY_ORDER and end in DAY_ORDER:
            si, ei = DAY_ORDER.index(start), DAY_ORDER.index(end)
            if si <= ei:
                return ",".join(DAY_ORDER[si : ei + 1])
        raise ValueError(f"{field} invalid range: {value!r} (use mon-fri or mon,tue,...)")

    picked: list[str] = []
    for part in raw.split(","):
        if not part:
            continue
        if part not in DAY_LABELS:
            raise ValueError(f"{field} invalid day {part!r} — use mon,tue,wed,thu,fri,sat,sun")
        if part not in picked:
            picked.append(part)
    if not picked:
        raise ValueError(f"{field} must include at least one day")
    return ",".join(d for d in DAY_ORDER if d in picked)


def format_work_days(value: str | None = None) -> str:
    days = parse_work_days(value if value is not None else WORK_DAYS).split(",")
    if len(days) == 7:
        return "Every day (Mon–Sun)"
    if days == list(DAY_ORDER[:5]):
        return "Monday – Friday"
    if days == list(DAY_ORDER[:6]):
        return "Monday – Saturday"
    return ", ".join(DAY_LABELS[d] for d in days)


def get_work_days_cron(value: str | None = None) -> str:
    return parse_work_days(value if value is not None else WORK_DAYS)


def get_schedule_jobs(
    *,
    work_start: str | None = None,
    work_end: str | None = None,
    lunch_start: str | None = None,
    lunch_end: str | None = None,
    lunch_enabled: bool | None = None,
) -> list[ScheduleJob]:
    ws = work_start if work_start is not None else WORK_START
    we = work_end if work_end is not None else WORK_END
    ls = lunch_start if lunch_start is not None else LUNCH_START
    le = lunch_end if lunch_end is not None else LUNCH_END
    lunch_on = lunch_enabled if lunch_enabled is not None else LUNCH_ENABLED

    ws_h, ws_m = parse_time(ws, "WORK_START")
    we_h, we_m = parse_time(we, "WORK_END")
    if _minutes(we_h, we_m) <= _minutes(ws_h, ws_m):
        raise ValueError("WORK_END must be after WORK_START")

    jobs = [
        ScheduleJob(
            "work_start",
            f"{ws} MAX connect + Available (after your OTP login)",
            ws_h,
            ws_m,
            "morning",
        ),
    ]

    if lunch_on:
        ls_h, ls_m = parse_time(ls, "LUNCH_START")
        le_h, le_m = parse_time(le, "LUNCH_END")
        if _minutes(le_h, le_m) <= _minutes(ls_h, ls_m):
            raise ValueError("LUNCH_END must be after LUNCH_START")
        if not (_minutes(ws_h, ws_m) < _minutes(ls_h, ls_m) < _minutes(le_h, le_m) < _minutes(we_h, we_m)):
            raise ValueError(f"Lunch must be between work start ({ws}) and work end ({we})")
        jobs.extend(
            [
                ScheduleJob("lunch_start", f"{ls} Unavailable (Lunch)", ls_h, ls_m, "lunch"),
                ScheduleJob("lunch_end", f"{le} Available", le_h, le_m, "lunch-end"),
            ]
        )

    jobs.append(ScheduleJob("work_end", f"{we} Logout", we_h, we_m, "logout"))
    return jobs


def skip_scheduled_job_reason() -> str | None:
    """Return why a scheduled job should be skipped, or None to run."""
    if AUTORUN_PAUSED:
        return "Automation paused / on leave — Resume or Clear leave to run jobs again"
    if LEAVE_DATE:
        from datetime import datetime

        tz = get_tz()
        today = datetime.now(tz).strftime("%Y-%m-%d")
        if today == LEAVE_DATE:
            return f"Leave day ({LEAVE_DATE}) — no jobs today"
    return None


def schedule_summary() -> str:
    lunch = (
        f"  Lunch:  {LUNCH_START} Unavailable (Lunch) → {LUNCH_END} Available\n"
        if LUNCH_ENABLED
        else "  Lunch:  disabled\n"
    )
    flags = []
    if AUTORUN_PAUSED:
        flags.append("Automation: PAUSED / on leave (no jobs until Resume or Clear leave)")
    if LEAVE_DATE:
        flags.append(f"Leave since: {LEAVE_DATE}")
    flag_line = ("\n".join(flags) + "\n") if flags else ""
    return (
        f"App:        {APP_NAME}\n"
        f"Mode:       {BROWSER_MODE} (launch = no debug port)\n"
        f"MAX profile: {CHROME_MAX_PROFILE_DIR}\n"
        f"Timezone:   {format_timezone()}\n"
        f"Station ID: {STATION_ID}\n"
        f"Work days:  {format_work_days()}\n"
        f"{flag_line}"
        f"  Start:    {WORK_START} — MAX browser, connect, Available\n"
        f"{lunch}"
        f"  End:      {WORK_END} — Logout + confirm\n"
        f"  Quiet:    {'yes' if QUIET_STATUS_JOBS else 'no'} (lunch runs in background; logout focuses MAX)\n"
    )


def save_env(updates: dict[str, str]) -> None:
    lines: list[str] = []
    seen: set[str] = set()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key in updates:
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(override=True)

    global STATION_ID, WORK_START, WORK_END, LUNCH_START, LUNCH_END, LUNCH_ENABLED, TIMEZONE, WORK_DAYS
    global AUTORUN_PAUSED, LEAVE_DATE
    if "STATION_ID" in updates:
        STATION_ID = updates["STATION_ID"]
    if "WORK_START" in updates:
        WORK_START = updates["WORK_START"]
    if "WORK_END" in updates:
        WORK_END = updates["WORK_END"]
    if "LUNCH_START" in updates:
        LUNCH_START = updates["LUNCH_START"]
    if "LUNCH_END" in updates:
        LUNCH_END = updates["LUNCH_END"]
    if "LUNCH_ENABLED" in updates:
        LUNCH_ENABLED = updates["LUNCH_ENABLED"].lower() in {"1", "true", "yes"}
    if "TIMEZONE" in updates:
        updates["TIMEZONE"] = canonical_timezone(updates["TIMEZONE"])
        resolve_timezone(updates["TIMEZONE"])
        TIMEZONE = updates["TIMEZONE"]
    if "WORK_DAYS" in updates:
        WORK_DAYS = parse_work_days(updates["WORK_DAYS"])
    if "AUTORUN_PAUSED" in updates:
        AUTORUN_PAUSED = updates["AUTORUN_PAUSED"].lower() in {"1", "true", "yes"}
    if "LEAVE_DATE" in updates:
        LEAVE_DATE = updates["LEAVE_DATE"].strip()
