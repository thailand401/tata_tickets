"""Per-browser auth/session state for the NiceGUI UI."""

from __future__ import annotations

from typing import Any

from nicegui import app


def set_session(data: dict[str, Any]) -> None:
    app.storage.user["auth"] = data


def clear_session() -> None:
    app.storage.user.pop("auth", None)


def get_session() -> dict[str, Any] | None:
    return app.storage.user.get("auth")


def access_token() -> str | None:
    sess = get_session()
    return sess.get("access_token") if sess else None


def current_user() -> dict[str, Any] | None:
    sess = get_session()
    return sess.get("user") if sess else None


def is_authenticated() -> bool:
    return access_token() is not None
