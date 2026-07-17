"""OAuth / Access Key token for NICE CXone Agent API."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from rc_agent import config


@dataclass
class TokenBundle:
    access_token: str
    expires_at: float
    refresh_token: str | None = None

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - 60


_token: TokenBundle | None = None


def _oauth_password_token() -> TokenBundle:
    data = {
        "grant_type": "password",
        "username": config.RC_ACCESS_KEY_ID,
        "password": config.RC_ACCESS_KEY_SECRET,
        "client_id": config.RC_CLIENT_ID,
        "client_secret": config.RC_CLIENT_SECRET,
    }
    resp = requests.post(config.RC_TOKEN_URL, data=data, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return TokenBundle(
        access_token=body["access_token"],
        expires_at=time.time() + int(body.get("expires_in", 3600)),
        refresh_token=body.get("refresh_token"),
    )


def _access_key_json_token() -> TokenBundle:
    payload = {
        "accessKeyId": config.RC_ACCESS_KEY_ID,
        "accessKeySecret": config.RC_ACCESS_KEY_SECRET,
    }
    resp = requests.post(config.RC_ACCESS_KEY_TOKEN_URL, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return TokenBundle(
        access_token=body["access_token"],
        expires_at=time.time() + int(body.get("expires_in", 3600)),
        refresh_token=body.get("refresh_token"),
    )


def _refresh_token(bundle: TokenBundle) -> TokenBundle:
    if not bundle.refresh_token:
        return fetch_token(force=True)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": bundle.refresh_token,
        "client_id": config.RC_CLIENT_ID,
        "client_secret": config.RC_CLIENT_SECRET,
    }
    resp = requests.post(config.RC_TOKEN_URL, data=data, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return TokenBundle(
        access_token=body["access_token"],
        expires_at=time.time() + int(body.get("expires_in", 3600)),
        refresh_token=body.get("refresh_token", bundle.refresh_token),
    )


def fetch_token(*, force: bool = False) -> TokenBundle:
    global _token
    config.validate_credentials()
    if not force and _token is not None and not _token.expired:
        return _token
    if not force and _token is not None and _token.refresh_token:
        try:
            _token = _refresh_token(_token)
            return _token
        except Exception:
            pass
    if config.RC_AUTH_MODE == "access_key_json":
        _token = _access_key_json_token()
    else:
        _token = _oauth_password_token()
    return _token


def authorization_header() -> dict[str, str]:
    token = fetch_token()
    return {"Authorization": f"Bearer {token.access_token}"}
