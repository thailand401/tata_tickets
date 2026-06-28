"""Login page."""

from __future__ import annotations

from nicegui import ui

from app.presentation.ui import api_client
from app.presentation.ui.api_client import ApiError
from app.presentation.ui.state import is_authenticated, set_session
from app.presentation.ui.theme import apply_dark_mode


def render() -> None:
    apply_dark_mode()
    if is_authenticated():
        ui.navigate.to("/")
        return

    with ui.column().classes("absolute-center items-center gap-4"):
        ui.label("Tata — AI Software Factory").classes("text-2xl font-bold")
        ui.label("Sign in to the dashboard").classes("opacity-70")

        with ui.card().classes("w-96 p-6 gap-3"):
            email = ui.input("Email").props("outlined").classes("w-full")
            password = (
                ui.input("Password", password=True, password_toggle_button=True)
                .props("outlined")
                .classes("w-full")
            )

            def do_login() -> None:
                try:
                    session = api_client.login(email.value, password.value)
                    set_session(session)
                    ui.navigate.to("/")
                except ApiError as exc:
                    ui.notify(exc.message or "Login failed", type="negative")
                except Exception as exc:  # noqa: BLE001
                    ui.notify(f"Unexpected error: {exc}", type="negative")

            ui.button("Sign in", on_click=do_login).props("color=primary").classes("w-full")
            password.on("keydown.enter", lambda _: do_login())
