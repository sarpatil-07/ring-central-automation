"""RCAutoLogin settings — RingCX web agent (app.ringcentral.com)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from rc_autologin.paths import app_root, user_data_dir

APP_NAME = "RCAutoLogin"

BASE_DIR = app_root()
USER_HOME = user_data_dir()
ENV_FILE = BASE_DIR / ".env"
SELECTORS_FILE = Path(__file__).resolve().parent / "selectors.yaml"
LOG_DIR = Path(os.getenv("RCAUTOLOGIN_LOG_DIR", str(USER_HOME / "logs"))).expanduser()

load_dotenv(ENV_FILE)

RCX_AGENT_URL = os.getenv(
    "RCX_AGENT_URL",
    "https://app.ringcentral.com/ring_cx/agent?env=production",
).strip()

# Keep Chrome profile under ~/.rcautologin (fast local disk — not inside Downloads/iCloud zip folder).
CHROME_RCX_PROFILE_DIR = Path(
    os.getenv("CHROME_RCX_PROFILE_DIR", str(USER_HOME / "chrome-rcx-profile"))
).expanduser()

CHROME_RCX_CDP_PORT = int(os.getenv("CHROME_RCX_CDP_PORT", "9334"))
RCX_CDP_URL = f"http://127.0.0.1:{CHROME_RCX_CDP_PORT}"

CLOSE_BROWSER_AFTER_RUN = os.getenv("RCX_CLOSE_BROWSER_AFTER_RUN", "false").lower() in {
    "1",
    "true",
    "yes",
}

MANUAL_LOGIN_WAIT_SECONDS = int(os.getenv("RCX_MANUAL_LOGIN_WAIT_SECONDS", "600"))
CLICK_WAIT_MS = int(os.getenv("RCX_CLICK_WAIT_MS", "200"))
CONNECT_WAIT_SECONDS = int(os.getenv("RCX_CONNECT_WAIT_SECONDS", "12"))
STATUS_WAIT_MS = int(os.getenv("RCX_STATUS_WAIT_MS", "350"))
LOGIN_POLL_SECONDS = float(os.getenv("RCX_LOGIN_POLL_SECONDS", "0.4"))
LOGIN_STEP_WAIT_MS = int(os.getenv("RCX_LOGIN_STEP_WAIT_MS", "350"))
SELECTOR_SCAN_MS = int(os.getenv("RCX_SELECTOR_SCAN_MS", "500"))

QUIET_STATUS_JOBS = os.getenv("RCX_QUIET_STATUS_JOBS", "true").lower() in {"1", "true", "yes"}

RCX_LOGIN_ID = os.getenv("RCX_LOGIN_ID", "").strip()
RCX_LOGIN_PASSWORD = os.getenv("RCX_LOGIN_PASSWORD", "")
RCX_AUTO_LOGIN_ENABLED = os.getenv("RCX_AUTO_LOGIN_ENABLED", "false").lower() in {"1", "true", "yes"}

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


def reload_schedule() -> None:
    from rc_autologin.schedule_util import reload_schedule as _reload

    _reload()


def get_rcx_schedule_jobs():
    from rc_autologin.schedule_util import get_rcx_schedule_jobs as _jobs

    return _jobs()


def schedule_summary() -> str:
    reload_schedule()
    lunch = (
        f"  Lunch:  {LUNCH_START} → {LUNCH_END}\n"
        if LUNCH_ENABLED
        else "  Lunch:  disabled\n"
    )
    return (
        f"App:        {APP_NAME}\n"
        f"URL:        {RCX_AGENT_URL}\n"
        f"Profile:    {CHROME_RCX_PROFILE_DIR}\n"
        f"Timezone:   {format_timezone()}\n"
        f"Work days:  {format_work_days()}\n"
        f"  Start:    {WORK_START} — Agent → Start session → AVAILABLE\n"
        f"{lunch}"
        f"  End:      {WORK_END} — Stop session + close browser\n"
    )
