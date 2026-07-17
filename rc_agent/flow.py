"""Daily RC agent flows — login, lunch, logout via Agent API."""

from __future__ import annotations

from rc_agent import api_client


def morning_login() -> None:
    """Work start: agent session + Available (use desktop MAX for calls after this)."""
    print("RC Agent API — morning (login + Available)")
    api_client.ensure_session()
    api_client.set_available()


def lunch_start() -> None:
    print("RC Agent API — lunch")
    api_client.set_lunch()


def lunch_end() -> None:
    print("RC Agent API — back from lunch")
    api_client.set_available()


def logout() -> None:
    print("RC Agent API — logout")
    api_client.end_session()


def run_action(action: str) -> None:
    actions = {
        "morning": morning_login,
        "login": morning_login,
        "lunch": lunch_start,
        "lunch-end": lunch_end,
        "logout": logout,
    }
    fn = actions.get(action)
    if fn is None:
        raise ValueError(f"Unknown action: {action}")
    fn()
    print("\nDone.")
