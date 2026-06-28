"""Read-only monitoring pages with realtime-ish auto refresh."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.presentation.ui import api_client
from app.presentation.ui.api_client import ApiError
from app.presentation.ui.theme import layout, require_auth


def monitor_page(
    *, title: str, endpoint: str, columns: list[dict[str, Any]], interval: float = 5.0
) -> None:
    if not require_auth():
        return

    with layout(title):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(title).classes("text-xl font-semibold")
            ui.badge("live").props("color=green")

        table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")

        def refresh() -> None:
            try:
                rows = api_client.get(endpoint, params={"limit": 100})
                table.rows = rows or []
                table.update()
            except ApiError as exc:
                ui.notify(exc.message, type="negative")

        refresh()
        ui.timer(interval, refresh)
