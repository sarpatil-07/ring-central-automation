"""Desktop RingCentral.app settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DESKTOP_APP_NAME = "RingCentralAutoSet-Desktop"

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
LABELS_FILE = Path(
    os.getenv("DESKTOP_LABELS_FILE", str(Path(__file__).resolve().parent / "labels.yaml"))
).expanduser()

load_dotenv(ENV_FILE)

RC_APP_PROCESS = os.getenv("RC_APP_PROCESS", "RingCentral").strip()
DESKTOP_SKIP_AGENT_TAB = os.getenv("DESKTOP_SKIP_AGENT_TAB", "false").lower() in {
    "1",
    "true",
    "yes",
}
CONNECT_WAIT_SECONDS = int(os.getenv("DESKTOP_CONNECT_WAIT_SECONDS", "15"))
ACTION_DELAY_SECONDS = float(os.getenv("DESKTOP_ACTION_DELAY_SECONDS", "0.8"))
STATUS_SET_DELAY_SECONDS = float(os.getenv("DESKTOP_STATUS_DELAY_SECONDS", "1.2"))
INSPECT_MAX_LINES = int(os.getenv("DESKTOP_INSPECT_MAX_LINES", "400"))

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
