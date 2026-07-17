"""RC Agent API settings (reads parent .env + RC_* keys)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RC_APP_NAME = "RingCentralAutoSet-API"

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
SESSION_FILE = Path(__file__).resolve().parent / "data" / "session.json"

load_dotenv(ENV_FILE)

# --- API credentials (from CXone Admin → Access Keys + registered app) ---
RC_ACCESS_KEY_ID = os.getenv("RC_ACCESS_KEY_ID", "").strip()
RC_ACCESS_KEY_SECRET = os.getenv("RC_ACCESS_KEY_SECRET", "").strip()
RC_CLIENT_ID = os.getenv("RC_CLIENT_ID", "").strip()
RC_CLIENT_SECRET = os.getenv("RC_CLIENT_SECRET", "").strip()

# Token: oauth_password (legacy) or access_key_json (newer UserHub endpoint)
RC_AUTH_MODE = os.getenv("RC_AUTH_MODE", "oauth_password").strip().lower()
RC_TOKEN_URL = os.getenv(
    "RC_TOKEN_URL",
    "https://cxone.niceincontact.com/auth/token",
).strip()
RC_ACCESS_KEY_TOKEN_URL = os.getenv(
    "RC_ACCESS_KEY_TOKEN_URL",
    "https://na1.nice-incontact.com/authentication/v1/token/access-key",
).strip()

# Agent API base (cluster-specific — e.g. api-na1, api-c31)
RC_API_BASE = os.getenv(
    "RC_API_BASE",
    "https://api-na1.niceincontact.com/inContactAPI/services/v27.0",
).rstrip("/")

RC_API_VERSION = os.getenv("RC_API_VERSION", "v27.0")
RC_STATION_ID = os.getenv("RC_STATION_ID", os.getenv("STATION_ID", "14065216")).strip()
RC_AGENT_ID = os.getenv("RC_AGENT_ID", "").strip()

# Unavailable reason labels (must match codes in your RC/CXone admin)
RC_LUNCH_REASON = os.getenv("RC_LUNCH_REASON", "Lunch").strip()

# Reuse parent schedule / timezone from main config
import config as parent_config  # noqa: E402

TIMEZONE = parent_config.TIMEZONE
WORK_START = parent_config.WORK_START
WORK_END = parent_config.WORK_END
LUNCH_START = parent_config.LUNCH_START
LUNCH_END = parent_config.LUNCH_END
LUNCH_ENABLED = parent_config.LUNCH_ENABLED
WORK_DAYS = parent_config.WORK_DAYS
AUTORUN_PAUSED = parent_config.AUTORUN_PAUSED
LEAVE_DATE = parent_config.LEAVE_DATE
get_tz = parent_config.get_tz
get_schedule_jobs = parent_config.get_schedule_jobs
get_work_days_cron = parent_config.get_work_days_cron
skip_scheduled_job_reason = parent_config.skip_scheduled_job_reason
format_timezone = parent_config.format_timezone
format_work_days = parent_config.format_work_days
DAY_ORDER = parent_config.DAY_ORDER
DAY_LABELS = parent_config.DAY_LABELS


def credentials_configured() -> bool:
    return bool(RC_ACCESS_KEY_ID and RC_ACCESS_KEY_SECRET)


def validate_credentials() -> None:
    if not credentials_configured():
        raise ValueError(
            "RC API credentials missing. Set RC_ACCESS_KEY_ID and RC_ACCESS_KEY_SECRET in .env\n"
            "See RC_API_SETUP.md for how to create Access Keys in CXone Admin."
        )
    if RC_AUTH_MODE == "oauth_password" and (not RC_CLIENT_ID or not RC_CLIENT_SECRET):
        raise ValueError(
            "RC_AUTH_MODE=oauth_password requires RC_CLIENT_ID and RC_CLIENT_SECRET "
            "(from your registered CXone API application)."
        )
