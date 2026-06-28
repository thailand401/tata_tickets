"""Shared UI layout: responsive shell, navigation drawer, dark-mode toggle."""

from __future__ import annotations

from nicegui import ui

from app.presentation.ui.state import clear_session, current_user, is_authenticated

NAV_ITEMS = [
    ("Overview", "/", "dashboard"),
    ("Projects", "/projects", "folder"),
    ("Workspaces", "/workspaces", "workspaces"),
    ("Tickets", "/tickets", "confirmation_number"),
    ("Prompt Library", "/prompts", "library_books"),
    ("Tech Specs", "/tech-specs", "description"),
    ("Agent Registry", "/agents", "smart_toy"),
    ("Model Registry", "/models", "memory"),
    ("Workflow Registry", "/workflows", "account_tree"),
    ("Roles", "/roles", "admin_panel_settings"),
    ("Event Log", "/events", "bolt"),
    ("Task Queue", "/queue", "queue"),
    ("Audit Log", "/audit", "fact_check"),
]


def apply_dark_mode() -> ui.dark_mode:
    """Create a dark-mode controller defaulting to dark."""
    dark = ui.dark_mode()
    dark.enable()
    return dark


def layout(title: str):
    """Build the standard page chrome and return the content container.

    Usage:
        with layout("Projects"):
            ui.label("...")
    """
    dark = apply_dark_mode()

    with ui.header().classes("items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            ui.button(on_click=lambda: drawer.toggle(), icon="menu").props("flat round color=white")
            ui.label("Tata — AI Software Factory").classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-2"):
            ui.label(title).classes("text-sm opacity-80")
            ui.button(icon="dark_mode", on_click=dark.toggle).props("flat round color=white")
            user = current_user()
            if user:
                ui.label(user.get("email", "")).classes("text-sm opacity-80")
                ui.button(icon="logout", on_click=_logout).props("flat round color=white")

    with ui.left_drawer(value=True).classes("bg-gray-900 text-white") as drawer:
        ui.label("Navigation").classes("text-xs uppercase opacity-60 q-pa-sm")
        for label_text, path, icon in NAV_ITEMS:
            ui.link(text="", target=path).classes("no-underline w-full")
            with ui.row().classes("items-center w-full"):
                ui.button(
                    label_text, icon=icon, on_click=lambda p=path: ui.navigate.to(p)
                ).props("flat align=left color=white").classes("w-full justify-start")

    content = ui.column().classes("w-full max-w-screen-xl mx-auto p-4 gap-4")
    return content


def _logout() -> None:
    clear_session()
    ui.navigate.to("/login")


def require_auth() -> bool:
    """Redirect to /login if not authenticated. Returns True if OK to render."""
    if not is_authenticated():
        ui.navigate.to("/login")
        return False
    return True
