"""Generic CRUD page: table + create/delete for a REST resource."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from app.presentation.ui import api_client
from app.presentation.ui.api_client import ApiError
from app.presentation.ui.theme import layout, require_auth


def crud_page(
    *,
    title: str,
    endpoint: str,
    columns: list[dict[str, Any]],
    create_fields: list[dict[str, Any]],
    row_key: str = "id",
) -> None:
    """Render a standard list + create + delete page.

    create_fields: list of {name, label, type('text'|'textarea'|'select'|'bool'),
                            options?, required?}
    columns: NiceGUI/Quasar column dicts with at least name+label+field.
    """
    if not require_auth():
        return

    with layout(title):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(title).classes("text-xl font-semibold")
            ui.button("New", icon="add", on_click=lambda: _open_create()).props("color=primary")

        table = ui.table(columns=columns, rows=[], row_key=row_key).classes("w-full")
        table.add_slot(
            "body-cell-actions",
            r'''
            <q-td :props="props">
              <q-btn dense flat round icon="delete" color="negative"
                     @click="() => $parent.$emit('delete_row', props.row)" />
            </q-td>
            ''',
        )

        def refresh() -> None:
            try:
                rows = api_client.get(endpoint, params={"limit": 200})
                table.rows = rows or []
                table.update()
            except ApiError as exc:
                ui.notify(exc.message, type="negative")

        def _delete_row(e) -> None:
            row = e.args
            item_id = row.get(row_key)
            try:
                api_client.delete(f"{endpoint}/{item_id}")
                ui.notify("Deleted", type="positive")
                refresh()
            except ApiError as exc:
                ui.notify(exc.message, type="negative")

        table.on("delete_row", _delete_row)

        def _open_create() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96 gap-2 p-4"):
                ui.label(f"New {title}").classes("text-lg font-semibold")
                inputs: dict[str, Callable[[], Any]] = {}
                for f in create_fields:
                    ftype = f.get("type", "text")
                    if ftype == "textarea":
                        el = ui.textarea(f["label"]).props("outlined").classes("w-full")
                        inputs[f["name"]] = lambda el=el: el.value
                    elif ftype == "select":
                        el = (
                            ui.select(f["options"], label=f["label"])
                            .props("outlined")
                            .classes("w-full")
                        )
                        inputs[f["name"]] = lambda el=el: el.value
                    elif ftype == "bool":
                        el = ui.switch(f["label"], value=f.get("default", True))
                        inputs[f["name"]] = lambda el=el: el.value
                    else:
                        el = ui.input(f["label"]).props("outlined").classes("w-full")
                        inputs[f["name"]] = lambda el=el: el.value

                def submit() -> None:
                    payload = {name: getter() for name, getter in inputs.items()}
                    payload = {k: v for k, v in payload.items() if v not in (None, "")}
                    try:
                        api_client.post(endpoint, payload)
                        ui.notify("Created", type="positive")
                        dialog.close()
                        refresh()
                    except ApiError as exc:
                        ui.notify(exc.message, type="negative")

                with ui.row().classes("justify-end w-full gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Create", on_click=submit).props("color=primary")
            dialog.open()

        refresh()
