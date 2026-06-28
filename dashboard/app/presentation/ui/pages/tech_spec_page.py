"""Tech Spec UI: free-text intake, AI generation, history and version compare."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.presentation.ui import api_client
from app.presentation.ui.api_client import ApiError
from app.presentation.ui.theme import layout, require_auth

_SECTIONS: list[tuple[str, str]] = [
    ("feature", "Feature"),
    ("business_goal", "Business Goal"),
    ("functional_requirements", "Functional Requirements"),
    ("non_functional", "Non Functional"),
    ("api", "API"),
    ("database", "Database"),
    ("acceptance_criteria", "Acceptance Criteria"),
    ("risks", "Risk"),
    ("dependencies", "Dependency"),
    ("estimate", "Estimate"),
    ("priority", "Priority"),
]


def _render_value(value: Any) -> None:
    if isinstance(value, list):
        if not value:
            ui.label("—").classes("opacity-50")
        for item in value:
            ui.label(f"• {item}").classes("text-sm")
    else:
        ui.label(str(value) if value not in (None, "") else "—").classes("text-sm")


def _render_content(content: dict[str, Any]) -> None:
    for key, title in _SECTIONS:
        with ui.card().classes("w-full gap-1 p-3"):
            ui.label(title).classes("text-sm font-semibold opacity-70")
            _render_value(content.get(key))


# ---------------------------------------------------------------------------
# List page
# ---------------------------------------------------------------------------
def tech_spec_list_page() -> None:
    if not require_auth():
        return

    columns = [
        {"name": "title", "label": "Title", "field": "title",
         "align": "left", "sortable": True},
        {"name": "status", "label": "Status", "field": "status",
         "align": "left", "sortable": True},
        {"name": "current_version", "label": "Version",
         "field": "current_version", "align": "left"},
        {"name": "created_at", "label": "Created", "field": "created_at",
         "align": "left", "sortable": True},
        {"name": "actions", "label": "", "field": "actions", "align": "right"},
    ]

    with layout("Tech Specs"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Tech Specs").classes("text-xl font-semibold")
            ui.button("New", icon="add", on_click=lambda: _open_create()).props("color=primary")

        table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")
        table.add_slot(
            "body-cell-actions",
            r'''
            <q-td :props="props">
              <q-btn dense flat round icon="open_in_new" color="primary"
                     @click="() => $parent.$emit('open_row', props.row)" />
              <q-btn dense flat round icon="delete" color="negative"
                     @click="() => $parent.$emit('delete_row', props.row)" />
            </q-td>
            ''',
        )

        def refresh() -> None:
            try:
                table.rows = api_client.get("/tech-specs", params={"limit": 200}) or []
                table.update()
            except ApiError as exc:
                ui.notify(exc.message, type="negative")

        def _open_row(e) -> None:
            ui.navigate.to(f"/tech-specs/{e.args.get('id')}")

        def _delete_row(e) -> None:
            try:
                api_client.delete(f"/tech-specs/{e.args.get('id')}")
                ui.notify("Deleted", type="positive")
                refresh()
            except ApiError as exc:
                ui.notify(exc.message, type="negative")

        table.on("open_row", _open_row)
        table.on("delete_row", _delete_row)

        def _open_create() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-[32rem] gap-2 p-4"):
                ui.label("New Tech Spec").classes("text-lg font-semibold")
                title = ui.input("Title").props("outlined").classes("w-full")
                source = (
                    ui.textarea("Ticket (free text)")
                    .props("outlined autogrow")
                    .classes("w-full")
                )
                prompt_id = ui.input("Prompt ID (optional)").props("outlined").classes("w-full")
                model_id = ui.input("Model ID (optional)").props("outlined").classes("w-full")

                def submit() -> None:
                    payload = {
                        "title": title.value,
                        "source_text": source.value,
                        "prompt_id": prompt_id.value or None,
                        "model_id": model_id.value or None,
                    }
                    payload = {k: v for k, v in payload.items() if v not in (None, "")}
                    try:
                        api_client.post("/tech-specs", payload)
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


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------
def tech_spec_detail_page(spec_id: str) -> None:
    if not require_auth():
        return

    with layout("Tech Spec"):
        try:
            spec = api_client.get(f"/tech-specs/{spec_id}")
        except ApiError as exc:
            ui.notify(exc.message, type="negative")
            ui.button("Back", on_click=lambda: ui.navigate.to("/tech-specs")).props("flat")
            return

        with ui.row().classes("items-center justify-between w-full"):
            with ui.row().classes("items-center gap-2"):
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/tech-specs"),
                ).props("flat round")
                ui.label(spec.get("title", "Tech Spec")).classes("text-xl font-semibold")
            ui.badge(spec.get("status", "draft")).props("color=primary")

        with ui.card().classes("w-full gap-1 p-3"):
            ui.label("Ticket (free text)").classes("text-sm font-semibold opacity-70")
            ui.label(spec.get("source_text", "")).classes("text-sm whitespace-pre-wrap")

        versions_holder = ui.column().classes("w-full gap-2")
        content_holder = ui.column().classes("w-full gap-2")

        def load_versions() -> list[dict[str, Any]]:
            try:
                return api_client.get(f"/tech-specs/{spec_id}/versions") or []
            except ApiError as exc:
                ui.notify(exc.message, type="negative")
                return []

        def show_version(version: int) -> None:
            content_holder.clear()
            try:
                row = api_client.get(f"/tech-specs/{spec_id}/versions/{version}")
            except ApiError as exc:
                ui.notify(exc.message, type="negative")
                return
            with content_holder:
                ui.label(
                    f"Version {version} — {row.get('status')}"
                ).classes("text-lg font-semibold")
                if row.get("error"):
                    ui.label(row["error"]).classes("text-sm text-red-400")
                _render_content(row.get("content") or {})

        def render_versions() -> None:
            versions_holder.clear()
            rows = load_versions()
            with versions_holder:
                with ui.row().classes("items-center gap-2"):
                    ui.label("History").classes("text-lg font-semibold")
                    nums = [r.get("version") for r in rows]
                    sel_a = ui.select(nums, label="A").props("dense outlined").classes("w-24")
                    sel_b = ui.select(nums, label="B").props("dense outlined").classes("w-24")

                    def do_compare() -> None:
                        if sel_a.value is None or sel_b.value is None:
                            ui.notify("Pick two versions", type="warning")
                            return
                        _open_compare(spec_id, int(sel_a.value), int(sel_b.value))

                    ui.button("Compare", icon="compare_arrows", on_click=do_compare).props("flat")
                for r in rows:
                    with ui.row().classes("items-center gap-3 w-full"):
                        ui.badge(f"v{r.get('version')}").props("color=secondary")
                        ui.label(str(r.get("status"))).classes("text-sm")
                        ui.label(f"{r.get('attempts')} attempt(s)").classes("text-sm opacity-60")
                        ui.button(
                            "View", on_click=lambda v=r.get("version"): show_version(int(v))
                        ).props("flat dense")

        def generate() -> None:
            try:
                api_client.post(f"/tech-specs/{spec_id}/generate", {})
                ui.notify("Generated", type="positive")
            except ApiError as exc:
                ui.notify(exc.message, type="negative")
            render_versions()

        with ui.row().classes("items-center gap-2"):
            ui.button(
                "Generate / Retry", icon="auto_awesome", on_click=generate
            ).props("color=primary")

        render_versions()


def _open_compare(spec_id: str, a: int, b: int) -> None:
    try:
        result = api_client.get(f"/tech-specs/{spec_id}/compare", params={"a": a, "b": b})
    except ApiError as exc:
        ui.notify(exc.message, type="negative")
        return
    with ui.dialog() as dialog, ui.card().classes("w-[48rem] gap-2 p-4"):
        ui.label(f"Compare v{a} vs v{b}").classes("text-lg font-semibold")
        diff = result.get("diff", {})
        for key, title in _SECTIONS:
            entry = diff.get(key, {})
            changed = entry.get("changed")
            with ui.card().classes("w-full gap-1 p-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(title).classes("text-sm font-semibold opacity-70")
                    ui.badge("changed" if changed else "same").props(
                        f"color={'orange' if changed else 'green'}"
                    )
                with ui.row().classes("w-full gap-4"):
                    with ui.column().classes("flex-1 gap-1"):
                        ui.label(f"v{a}").classes("text-xs opacity-50")
                        _render_value(entry.get("a"))
                    with ui.column().classes("flex-1 gap-1"):
                        ui.label(f"v{b}").classes("text-xs opacity-50")
                        _render_value(entry.get("b"))
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()
