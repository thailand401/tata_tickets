"""Overview / landing page with quick stats."""

from __future__ import annotations

from nicegui import ui

from app.presentation.ui import api_client
from app.presentation.ui.theme import layout, require_auth

_CARDS = [
    ("Projects", "/projects", "folder"),
    ("Tickets", "/tickets", "confirmation_number"),
    ("Agents", "/agents", "smart_toy"),
    ("Models", "/models", "memory"),
    ("Workflows", "/workflows", "account_tree"),
    ("Prompts", "/prompts", "library_books"),
]


def render() -> None:
    if not require_auth():
        return

    with layout("Overview"):
        ui.label("Dashboard Overview").classes("text-2xl font-semibold")
        ui.label("AI Software Factory — foundation").classes("opacity-70")

        with ui.row().classes("w-full flex-wrap gap-4"):
            for name, path, icon in _CARDS:
                with ui.card().classes("w-60 cursor-pointer").on(
                    "click", lambda p=path: ui.navigate.to(p)
                ):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon(icon, size="lg")
                        with ui.column().classes("gap-0"):
                            ui.label(name).classes("text-lg font-medium")
                            count_label = ui.label("…").classes("opacity-60 text-sm")
                    _load_count(path, count_label)


def _load_count(path: str, label) -> None:
    try:
        rows = api_client.get(path, params={"limit": 200})
        label.set_text(f"{len(rows or [])} items")
    except Exception:  # noqa: BLE001
        label.set_text("—")
