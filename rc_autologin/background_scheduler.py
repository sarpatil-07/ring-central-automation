"""In-process scheduler for the GUI — LaunchAgent preferred; GUI fallback only."""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from rc_autologin import config
from rc_autologin.browser_worker import get_worker
from rc_autologin.scheduler_core import (
    autorun_enabled,
    ensure_persistent_scheduler,
    make_fire,
    mark_scheduler_started,
    mark_scheduler_stopped,
    print_scheduler_banner,
    register_jobs,
    scheduler_status,
    user_stopped_scheduler,
)

_log = logging.getLogger(__name__)


def _launchagent_active() -> bool:
    from rc_autologin import service as rcx_service

    if user_stopped_scheduler():
        return False
    return hasattr(rcx_service, "is_running") and rcx_service.is_running()


class GuiBackgroundScheduler:
    """Scheduler control — persistent LaunchAgent when available."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sched: BackgroundScheduler | None = None
        self._gui_fallback = False

    @property
    def running(self) -> bool:
        if user_stopped_scheduler():
            return False
        if _launchagent_active():
            return True
        with self._lock:
            return self._sched is not None and self._gui_fallback

    def start(self) -> str:
        status = scheduler_status()
        ok, persist = ensure_persistent_scheduler()
        if ok:
            mark_scheduler_started()
            _log.info("Using LaunchAgent background scheduler")
            msg = "Background scheduler running (LaunchAgent)."
            if status["upcoming_today"]:
                msg += f" Next today: {', '.join(status['upcoming_today'])}."
            msg += " Safe to close the GUI or terminal — jobs keep running."
            if status["note"]:
                msg += f" ({status['note']})"
            return msg

        # LaunchAgent unavailable — run scheduler inside GUI process (must keep GUI open).
        with self._lock:
            if self._sched is not None:
                self.reload()
                return "Scheduler already running in GUI (keep this window open)."

            config.reload_schedule()
            tz = config.get_tz()
            now = datetime.now(tz)
            print(
                f"\n[GUI scheduler fallback] {now.strftime('%Y-%m-%d %H:%M:%S')} "
                f"({config.format_timezone()})"
            )
            if status["note"]:
                print(f"⚠ {status['note']}")
            print(f"Note: LaunchAgent not active ({persist}). Keep GUI open for scheduled jobs.")

            get_worker()
            fire = make_fire()
            self._sched = BackgroundScheduler(
                timezone=tz,
                job_defaults={"misfire_grace_time": 3600, "coalesce": True},
            )
            tz, jobs = register_jobs(self._sched, fire=fire)
            print_scheduler_banner(tz, jobs)
            self._sched.start()
            self._gui_fallback = True
            mark_scheduler_started()
            _log.info("GUI fallback scheduler started")

            msg = "Scheduler running inside GUI — keep this app open."
            if status["upcoming_today"]:
                msg += f" Next today: {', '.join(status['upcoming_today'])}."
            return msg

    def detach(self) -> None:
        """GUI closing — stop in-process fallback only; LaunchAgent keeps running."""
        with self._lock:
            if self._sched is not None:
                aps_log = logging.getLogger("apscheduler.scheduler")
                old_level = aps_log.level
                aps_log.setLevel(logging.ERROR)
                try:
                    self._sched.shutdown(wait=False)
                except Exception:
                    pass
                finally:
                    aps_log.setLevel(old_level)
                self._sched = None
            self._gui_fallback = False
            _log.info("GUI fallback scheduler detached")

    def stop(self) -> None:
        """User clicked Stop — disable LaunchAgent and any GUI fallback."""
        with self._lock:
            if self._sched is not None:
                try:
                    self._sched.shutdown(wait=False)
                except Exception:
                    pass
                self._sched = None
            self._gui_fallback = False
        mark_scheduler_stopped()
        _log.info("Scheduler stopped by user")

    def reload(self) -> None:
        if _launchagent_active():
            from rc_autologin import service as rcx_service

            if rcx_service.plist_path().exists():
                rcx_service.restart()
            return
        with self._lock:
            if self._sched is None:
                return
            config.reload_schedule()
            register_jobs(self._sched, fire=make_fire())
            _log.info("GUI fallback scheduler reloaded")

    def ensure_started_if_enabled(self) -> None:
        if user_stopped_scheduler():
            return
        if autorun_enabled() or _launchagent_active():
            try:
                msg = self.start()
                _log.info(msg)
            except Exception as exc:
                _log.exception("Could not start scheduler: %s", exc)


_instance: GuiBackgroundScheduler | None = None
_instance_lock = threading.Lock()


def get_background_scheduler() -> GuiBackgroundScheduler:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = GuiBackgroundScheduler()
        return _instance
