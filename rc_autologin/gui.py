"""RCAutoLogin — local web GUI (stdlib only; no tkinter required)."""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from rc_autologin.platform_util import open_url
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config as parent_config
from rc_autologin import config
from rc_autologin import service as rcx_service
from rc_autologin.background_scheduler import get_background_scheduler
from rc_autologin.flow import run_action
from rc_autologin.menu import save_credentials, save_schedule
from rc_autologin.scheduler_core import scheduler_status, set_job_log_callback, user_stopped_scheduler

GUI_PORT = 8765
HTML_FILE = Path(__file__).resolve().parent / "gui_page.html"

WORK_DAYS_OPTIONS = {
    "Mon–Fri": "mon,tue,wed,thu,fri",
    "Mon–Sat": "mon,tue,wed,thu,fri,sat",
    "Every day": "mon,tue,wed,thu,fri,sat,sun",
}

TIMEZONE_OPTIONS: list[dict[str, str]] = [
    {"value": "IST", "label": "IST — India (Asia/Kolkata)"},
    {"value": "Asia/Kolkata", "label": "Asia/Kolkata"},
    {"value": "APAC", "label": "APAC — Singapore"},
    {"value": "Asia/Singapore", "label": "Asia/Singapore"},
    {"value": "Asia/Manila", "label": "Asia/Manila"},
    {"value": "Asia/Tokyo", "label": "Asia/Tokyo"},
    {"value": "Australia/Sydney", "label": "Australia/Sydney"},
    {"value": "EMEA", "label": "EMEA — London"},
    {"value": "Europe/London", "label": "Europe/London"},
    {"value": "Europe/Berlin", "label": "Europe/Berlin"},
    {"value": "Europe/Paris", "label": "Europe/Paris"},
    {"value": "NA", "label": "NA — US Eastern"},
    {"value": "NA-Eastern", "label": "NA Eastern (New York)"},
    {"value": "NA-Central", "label": "NA Central (Chicago)"},
    {"value": "NA-Mountain", "label": "NA Mountain (Denver)"},
    {"value": "NA-Pacific", "label": "NA Pacific (Los Angeles)"},
    {"value": "LATAM", "label": "LATAM — São Paulo"},
    {"value": "America/Sao_Paulo", "label": "America/Sao_Paulo"},
    {"value": "America/Mexico_City", "label": "America/Mexico_City"},
]


def work_days_to_env(label: str) -> str:
    if label == "Today only":
        return config.DAY_ORDER[datetime.now(config.get_tz()).weekday()]
    return WORK_DAYS_OPTIONS.get(label, config.WORK_DAYS)


def work_days_from_env(days: str) -> str:
    for label, value in WORK_DAYS_OPTIONS.items():
        if days == value:
            return label
    return "Mon–Fri"


def timezone_options_payload() -> list[dict[str, str]]:
    return list(TIMEZONE_OPTIONS)


def _server_responding(port: int = GUI_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def open_gui_browser(port: int = GUI_PORT) -> None:
    open_url(f"http://127.0.0.1:{port}/")


class _LogBuffer:
    def __init__(self) -> None:
        self._lines: list[str] = []
        self._lock = threading.Lock()

    def add(self, msg: str) -> None:
        with self._lock:
            self._lines.append(msg)
            if len(self._lines) > 200:
                self._lines = self._lines[-200:]

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self._lines)


class _GuiState:
    def __init__(self) -> None:
        self.log = _LogBuffer()
        self._busy = False
        self._busy_message = ""
        self._lock = threading.Lock()

    def set_busy(self, busy: bool, *, message: str = "") -> None:
        with self._lock:
            self._busy = busy
            self._busy_message = message if busy else ""

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    def _scheduler_active(self) -> bool:
        if user_stopped_scheduler():
            return False
        launchagent_running = (
            rcx_service.is_running()
            if hasattr(rcx_service, "is_running")
            else rcx_service.plist_path().exists()
        )
        return launchagent_running or get_background_scheduler().running

    def status_payload(self, *, include_timezone_options: bool = False) -> dict[str, Any]:
        now = time.time()
        if now - getattr(self, "_last_schedule_reload", 0.0) >= 30.0:
            config.reload_schedule()
            self._last_schedule_reload = now
        scheduler_on = self._scheduler_active()
        sched_info = scheduler_status()
        payload: dict[str, Any] = {
            "app": config.APP_NAME,
            "url": config.RCX_AGENT_URL,
            "timezone": config.format_timezone(),
            "timezone_key": config.TIMEZONE,
            "work_days": config.format_work_days(),
            "work_days_key": work_days_from_env(config.WORK_DAYS),
            "work_start": config.WORK_START,
            "work_end": config.WORK_END,
            "lunch_enabled": config.LUNCH_ENABLED,
            "lunch_start": config.LUNCH_START,
            "lunch_end": config.LUNCH_END,
            "paused": config.AUTORUN_PAUSED,
            "leave_date": config.LEAVE_DATE,
            "service_running": scheduler_on,
            "scheduler_running": scheduler_on,
            "scheduler_today_active": sched_info["today_active"],
            "scheduler_note": sched_info["note"],
            "scheduler_upcoming": sched_info["upcoming_today"],
            "busy": self.busy,
            "busy_message": self._busy_message if self.busy else "",
            "rcx_login_id": config.RCX_LOGIN_ID,
            "rcx_auto_login": config.RCX_AUTO_LOGIN_ENABLED,
            "rcx_password_set": bool(config.RCX_LOGIN_PASSWORD),
            "login_configured": bool(
                config.RCX_LOGIN_ID
                and config.RCX_LOGIN_PASSWORD
                and config.RCX_AUTO_LOGIN_ENABLED
            ),
            "background_note": (
                "Scheduled jobs run in the background — safe to close this browser tab or press Ctrl+C in the terminal."
                if scheduler_on
                else "Scheduler stopped — click Start auto job to enable scheduled runs."
            ),
        }
        if include_timezone_options:
            payload["timezone_options"] = timezone_options_payload()
        return payload

    def run_async(self, label: str, fn) -> tuple[bool, str]:
        if self.busy:
            return False, "Another action is running — please wait."
        self.set_busy(True, message=f"{label}…")

        def task() -> None:
            self.log.add(f"→ {label}…")
            try:
                result = fn()
                if result:
                    self.log.add(str(result))
                self.log.add(f"✓ {label} done")
            except Exception as exc:
                self.log.add(f"✗ {label} failed: {exc}")
            finally:
                self.set_busy(False)

        threading.Thread(target=task, daemon=True).start()
        return True, f"{label} started"


STATE = _GuiState()


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def _client_gone(exc: BaseException) -> bool:
    """True when the browser tab closed mid-response (harmless on GUI exit)."""
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {32, 54, 104}:
        return True
    return False


def _send_json(handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    try:
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except Exception as exc:
        if _client_gone(exc):
            return
        raise


class GuiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except Exception as exc:
            if _client_gone(exc):
                return
            raise

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            data = HTML_FILE.read_bytes()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except Exception as exc:
                if _client_gone(exc):
                    return
                raise
            return
        if path == "/api/status":
            _send_json(self, 200, STATE.status_payload())
            return
        if path == "/api/state":
            _send_json(
                self,
                200,
                {
                    "status": STATE.status_payload(),
                    "lines": STATE.log.snapshot(),
                },
            )
            return
        if path == "/api/logs":
            _send_json(self, 200, {"lines": STATE.log.snapshot()})
            return
        if path == "/api/timezones":
            _send_json(self, 200, {"options": timezone_options_payload()})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = _read_json(self)
        except json.JSONDecodeError:
            _send_json(self, 400, {"ok": False, "error": "Invalid JSON"})
            return

        if path == "/api/schedule":
            self._save_schedule(body)
            return
        if path == "/api/action":
            self._run_action(body.get("action", ""))
            return
        if path == "/api/service":
            op = body.get("op", "")
            if op == "install":
                try:
                    launch_msg = rcx_service.install()
                    sched_msg = get_background_scheduler().start()
                    msg = f"{launch_msg}\n{sched_msg}"
                    STATE.log.add("✓ Start auto job")
                    STATE.log.add(msg)
                    _send_json(
                        self,
                        200,
                        {"ok": True, "message": "Background scheduler started.", **STATE.status_payload()},
                    )
                except Exception as exc:
                    _send_json(self, 500, {"ok": False, "error": str(exc)})
            elif op == "uninstall":
                try:
                    get_background_scheduler().stop()
                    msg = rcx_service.uninstall()
                    STATE.log.add("✓ Stop auto job")
                    STATE.log.add(msg)
                    _send_json(
                        self,
                        200,
                        {"ok": True, "message": "Background scheduler stopped.", **STATE.status_payload()},
                    )
                except Exception as exc:
                    _send_json(self, 500, {"ok": False, "error": str(exc)})
            else:
                _send_json(self, 400, {"ok": False, "error": "Unknown service op"})
            return
        if path == "/api/browser":
            self._browser_op(body.get("op", ""))
            return
        if path == "/api/automation":
            self._automation(body.get("op", ""))
            return
        if path == "/api/timezone":
            self._save_timezone(body.get("timezone", ""))
            return
        if path == "/api/credentials":
            self._save_credentials(body)
            return
        self.send_error(404)

    def _save_schedule(self, body: dict[str, Any]) -> None:
        updates: dict[str, str] = {
            "WORK_START": str(body.get("work_start", "")).strip(),
            "WORK_END": str(body.get("work_end", "")).strip(),
            "LUNCH_ENABLED": "true" if body.get("lunch_enabled") else "false",
            "WORK_DAYS": work_days_to_env(str(body.get("work_days_key", "Mon–Fri"))),
        }
        tz = str(body.get("timezone", "")).strip()
        try:
            if tz:
                updates["TIMEZONE"] = parent_config.canonical_timezone(tz)
        except ValueError as exc:
            _send_json(self, 400, {"ok": False, "error": str(exc)})
            return
        if body.get("lunch_enabled"):
            updates["LUNCH_START"] = str(body.get("lunch_start", "")).strip()
            updates["LUNCH_END"] = str(body.get("lunch_end", "")).strip()
        try:
            for field, name in (
                (updates.get("WORK_START"), "WORK_START"),
                (updates.get("WORK_END"), "WORK_END"),
                (updates.get("LUNCH_START"), "LUNCH_START"),
                (updates.get("LUNCH_END"), "LUNCH_END"),
            ):
                if field:
                    parent_config.parse_time(field, name)
        except ValueError as exc:
            _send_json(self, 400, {"ok": False, "error": str(exc)})
            return
        ok, msg = save_schedule(updates)
        if ok:
            sched = get_background_scheduler()
            if sched.running:
                sched.reload()
                msg = f"{msg} Scheduler reloaded with new times."
            else:
                msg = f"{msg} Schedule saved. Click Start auto job to enable scheduled runs."
            STATE.log.add(msg)
            STATE._last_schedule_reload = 0.0
        _send_json(self, 200 if ok else 400, {"ok": ok, "message": msg, **STATE.status_payload()})

    def _run_action(self, action: str) -> None:
        labels = {
            "morning": "Login",
            "lunch": "Lunch/Dinner",
            "break": "Break",
            "lunch-end": "Back",
            "logout": "Logout",
        }
        if action not in labels:
            _send_json(self, 400, {"ok": False, "error": f"Unknown action: {action}"})
            return
        ok, msg = STATE.run_async(labels[action], lambda a=action: run_action(a))
        _send_json(self, 200 if ok else 409, {"ok": ok, "message": msg})

    def _browser_op(self, op: str) -> None:
        if op == "close":
            from rc_autologin.browser_worker import close_browser

            ok, msg = STATE.run_async("Close RingCX Chrome", close_browser)
            _send_json(self, 200 if ok else 409, {"ok": ok, "message": msg})
            return
        _send_json(self, 400, {"ok": False, "error": "Unknown browser op"})

    def _automation(self, op: str) -> None:
        if op == "pause":
            ok, msg = save_schedule({"AUTORUN_PAUSED": "true"})
        elif op == "resume":
            ok, msg = save_schedule({"AUTORUN_PAUSED": "false", "LEAVE_DATE": ""})
        elif op == "leave":
            tz = config.get_tz()
            today = datetime.now(tz).strftime("%Y-%m-%d")
            ok, msg = save_schedule({"LEAVE_DATE": today, "AUTORUN_PAUSED": "false"})
            if ok:
                STATE.run_async("Logout (leave today)", lambda: run_action("logout"))
        elif op == "clear_leave":
            ok, msg = save_schedule({"LEAVE_DATE": ""})
        else:
            _send_json(self, 400, {"ok": False, "error": "Unknown automation op"})
            return
        if ok:
            STATE.log.add(msg)
        _send_json(self, 200 if ok else 400, {"ok": ok, "message": msg, **STATE.status_payload()})

    def _save_credentials(self, body: dict[str, Any]) -> None:
        password = body.get("password")
        pwd = str(password) if password is not None and str(password).strip() else None
        ok, msg = save_credentials(
            login_id=str(body.get("login_id", "")),
            password=pwd,
            auto_login=bool(body.get("auto_login")),
        )
        if ok:
            STATE.log.add(msg)
        _send_json(self, 200 if ok else 400, {"ok": ok, "message": msg, **STATE.status_payload()})

    def _save_timezone(self, value: str) -> None:
        try:
            tz = parent_config.canonical_timezone(str(value).strip())
        except ValueError as exc:
            _send_json(self, 400, {"ok": False, "error": str(exc)})
            return
        ok, msg = save_schedule({"TIMEZONE": tz})
        if ok:
            STATE.log.add(msg)
        _send_json(self, 200 if ok else 400, {"ok": ok, "message": msg, **STATE.status_payload()})


class QuietHTTPServer(ThreadingHTTPServer):
    """Suppress BrokenPipe / client-disconnect noise when the GUI tab closes."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        exc = sys.exc_info()[1]
        if exc is not None and _client_gone(exc):
            return
        super().handle_error(request, client_address)


def _shutdown_gui(server: ThreadingHTTPServer | None = None) -> None:
    """Close GUI; LaunchAgent keeps scheduled jobs running."""
    if server is not None:
        try:
            server.shutdown()
        except Exception:
            pass

    from rc_autologin import service as rcx_service

    sched = get_background_scheduler()
    if user_stopped_scheduler():
        try:
            sched.stop()
        except Exception:
            pass
        print("  Scheduler stopped.")
    else:
        launchagent_up = hasattr(rcx_service, "is_running") and rcx_service.is_running()
        had_gui_fallback = sched.running and not launchagent_up
        try:
            sched.detach()
        except Exception:
            pass
        if launchagent_up:
            info = scheduler_status()
            upcoming = ", ".join(info["upcoming_today"]) if info["upcoming_today"] else "see saved schedule"
            print("")
            print("  ✓ GUI closed — scheduled jobs KEEP RUNNING (LaunchAgent background job).")
            print(f"    Next today: {upcoming}")
            print(f"    Log: {config.BASE_DIR / 'logs' / 'rc-autologin-scheduler.log'}")
            print("")
        elif had_gui_fallback:
            print("")
            print("  ⚠ GUI scheduler stopped — LaunchAgent was not running.")
            print("    Click Start auto job and keep LaunchAgent active, or leave GUI open.")
            print("")

    try:
        from rc_autologin.browser_cleanup import cdp_healthy
        from rc_autologin.browser_worker import shutdown as shutdown_browser

        # If user closed Chrome manually, clear stale locks (keep window if still open).
        if not cdp_healthy():
            from rc_autologin.browser_cleanup import cleanup_stale_browser

            cleanup_stale_browser(force=True, quiet=True)
        shutdown_browser(keep_browser=True)
    except Exception:
        pass


def run_gui(port: int = GUI_PORT, *, open_browser: bool = True) -> None:
    from rc_autologin.paths import migrate_legacy_profile

    migrate_legacy_profile()
    config.reload_schedule()
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    set_job_log_callback(STATE.log.add)
    if _server_responding(port):
        print(f"\n{config.APP_NAME} GUI already running on port {port}.")
        if open_browser:
            open_gui_browser(port)
        return

    STATE.log.add("RCAutoLogin ready.")
    get_background_scheduler().ensure_started_if_enabled()
    server = QuietHTTPServer(("127.0.0.1", port), GuiHandler)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n{config.APP_NAME} GUI: {url}")
    print("Press Ctrl+C to close this window — scheduled jobs keep running in the background.")
    print("(Use Stop auto job in the GUI if you want to disable scheduled runs.)\n")
    if open_browser:
        threading.Timer(0.4, lambda: open_gui_browser(port)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGUI stopped.")
    finally:
        _shutdown_gui(server)
        server.server_close()
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
