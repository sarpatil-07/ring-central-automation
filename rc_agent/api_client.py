"""NICE CXone Agent API client — login, status, logout (desktop MAX backend)."""

from __future__ import annotations

import json
from typing import Any

import requests

from rc_agent import config
from rc_agent.auth import authorization_header
from rc_agent.session_store import clear as clear_session_file
from rc_agent.session_store import load as load_session_id
from rc_agent.session_store import save as save_session_id


class RCAgentAPIError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _url(path: str) -> str:
    return f"{config.RC_API_BASE}{path}"


def _request(method: str, path: str, **kwargs) -> Any:
    headers = kwargs.pop("headers", {})
    headers.update(authorization_header())
    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Accept", "application/json")
    resp = requests.request(method, _url(path), headers=headers, timeout=60, **kwargs)
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RCAgentAPIError(
            f"RC API {method} {path} failed ({resp.status_code}): {body}",
            status=resp.status_code,
            body=body,
        )
    if not resp.content:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        return resp.text


def start_session(*, station_id: str | None = None) -> str:
    """Login agent session with station ID (replaces MAX Connect in browser)."""
    station_id = station_id or config.RC_STATION_ID
    payload: dict[str, str] = {"stationId": station_id}
    body = _request("POST", "/agent-sessions", data=json.dumps(payload))
    session_id = str(body.get("sessionId") or body.get("sessionID") or "")
    if not session_id:
        raise RCAgentAPIError(f"No sessionId in response: {body}")
    save_session_id(session_id)
    print(f"  ✓ Agent session started (station {station_id}) — session {session_id[:8]}…")
    return session_id


def join_session() -> str:
    """Join existing agent session (e.g. already logged in on desktop MAX)."""
    body = _request("POST", "/agent-sessions/join", data="{}")
    session_id = str(body.get("sessionId") or body.get("sessionID") or "")
    if not session_id:
        raise RCAgentAPIError(f"No sessionId from join: {body}")
    save_session_id(session_id)
    print(f"  ✓ Joined existing agent session — {session_id[:8]}…")
    return session_id


def ensure_session() -> str:
    """Return active session id — join, reuse saved, or start new."""
    saved = load_session_id()
    if saved:
        try:
            _request("GET", f"/agent-sessions/{saved}")
            print(f"  Reusing saved session {saved[:8]}…")
            return saved
        except RCAgentAPIError:
            clear_session_file()

    try:
        return join_session()
    except RCAgentAPIError as exc:
        print(f"  No desktop session to join ({exc}) — starting new API session…")

    return start_session()


def get_session_state(session_id: str | None = None) -> dict[str, Any]:
    sid = session_id or ensure_session()
    return _request("GET", f"/agent-sessions/{sid}") or {}


def state_label(state: dict[str, Any]) -> str:
    for key in ("currentState", "agentState", "state", "status"):
        val = state.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict):
            for sub in ("state", "name", "description"):
                if val.get(sub):
                    return str(val[sub])
    return str(state)


def is_available(session_id: str | None = None) -> bool:
    try:
        label = state_label(get_session_state(session_id)).lower()
    except RCAgentAPIError:
        return False
    return "available" in label and "unavailable" not in label


def is_lunch(session_id: str | None = None) -> bool:
    try:
        label = state_label(get_session_state(session_id)).lower()
    except RCAgentAPIError:
        return False
    return "lunch" in label


def set_available(session_id: str | None = None) -> None:
    sid = session_id or ensure_session()
    if is_available(sid):
        print("  ✓ already Available — no change needed")
        return
    payload = {"state": "Available"}
    _request("PUT", f"/agent-sessions/{sid}/state", data=json.dumps(payload))
    print("  ✓ status → Available")


def set_lunch(session_id: str | None = None) -> None:
    sid = session_id or ensure_session()
    if is_lunch(sid):
        print(f"  ✓ already on Lunch — no change needed")
        return
    payload = {"state": "Unavailable", "reason": config.RC_LUNCH_REASON}
    _request("PUT", f"/agent-sessions/{sid}/state", data=json.dumps(payload))
    print(f"  ✓ status → Unavailable ({config.RC_LUNCH_REASON})")


def end_session(session_id: str | None = None) -> None:
    sid = session_id or load_session_id()
    if not sid:
        print("  No saved agent session — already logged out")
        return
    try:
        _request("DELETE", f"/agent-sessions/{sid}")
        print("  ✓ agent session ended (logout)")
    except RCAgentAPIError as exc:
        if exc.status == 404:
            print("  Session already ended")
        else:
            raise
    finally:
        clear_session_file()
