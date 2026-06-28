"""Thin HTTP client the UI uses to call the REST API with the user's JWT."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.settings import get_settings
from app.presentation.ui.state import access_token


def _base_url() -> str:
    s = get_settings()
    return f"http://127.0.0.1:{s.app_port}/api/v1"


def _headers() -> dict[str, str]:
    token = access_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _handle(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        message = resp.text
        try:
            body = resp.json()
            message = body.get("error", {}).get("message", message)
        except Exception:
            pass
        raise ApiError(resp.status_code, message)
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def login(email: str, password: str) -> dict[str, Any]:
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{_base_url()}/auth/login",
            json={"email": email, "password": password},
        )
    return _handle(resp)


def get(path: str, params: dict[str, Any] | None = None) -> Any:
    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{_base_url()}{path}", headers=_headers(), params=params)
    return _handle(resp)


def post(path: str, json: dict[str, Any]) -> Any:
    with httpx.Client(timeout=15) as client:
        resp = client.post(f"{_base_url()}{path}", headers=_headers(), json=json)
    return _handle(resp)


def patch(path: str, json: dict[str, Any]) -> Any:
    with httpx.Client(timeout=15) as client:
        resp = client.patch(f"{_base_url()}{path}", headers=_headers(), json=json)
    return _handle(resp)


def delete(path: str) -> Any:
    with httpx.Client(timeout=15) as client:
        resp = client.delete(f"{_base_url()}{path}", headers=_headers())
    return _handle(resp)
