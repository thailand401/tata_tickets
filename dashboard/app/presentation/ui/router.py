"""Register all NiceGUI pages/routes."""

from __future__ import annotations

from app.domain.enums import (
    ModelProvider,
    RegistryStatus,
    TicketPriority,
    TicketStatus,
)
from app.presentation.ui.pages import login, overview
from app.presentation.ui.pages.crud_page import crud_page
from app.presentation.ui.pages.monitor_page import monitor_page
from app.presentation.ui.pages.tech_spec_page import (
    tech_spec_detail_page,
    tech_spec_list_page,
)


def _col(name: str, label: str, field: str | None = None) -> dict:
    return {"name": name, "label": label, "field": field or name, "align": "left", "sortable": True}


_ACTIONS = {"name": "actions", "label": "", "field": "actions", "align": "right"}


def register_pages() -> None:
    from nicegui import ui

    @ui.page("/login")
    def _login():  # noqa: ANN202
        login.render()

    @ui.page("/")
    def _index():  # noqa: ANN202
        overview.render()

    @ui.page("/projects")
    def _projects():  # noqa: ANN202
        crud_page(
            title="Projects",
            endpoint="/projects",
            columns=[_col("name", "Name"), _col("slug", "Slug"),
                     _col("is_active", "Active"), _col("created_at", "Created"), _ACTIONS],
            create_fields=[
                {"name": "name", "label": "Name"},
                {"name": "slug", "label": "Slug"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ],
        )

    @ui.page("/workspaces")
    def _workspaces():  # noqa: ANN202
        crud_page(
            title="Workspaces",
            endpoint="/workspaces",
            columns=[_col("name", "Name"), _col("project_id", "Project"),
                     _col("created_at", "Created"), _ACTIONS],
            create_fields=[
                {"name": "project_id", "label": "Project ID"},
                {"name": "name", "label": "Name"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ],
        )

    @ui.page("/tickets")
    def _tickets():  # noqa: ANN202
        crud_page(
            title="Tickets",
            endpoint="/tickets",
            columns=[_col("title", "Title"), _col("status", "Status"),
                     _col("priority", "Priority"), _col("created_at", "Created"), _ACTIONS],
            create_fields=[
                {"name": "workspace_id", "label": "Workspace ID"},
                {"name": "title", "label": "Title"},
                {"name": "description", "label": "Description", "type": "textarea"},
                {"name": "status", "label": "Status", "type": "select",
                 "options": [s.value for s in TicketStatus]},
                {"name": "priority", "label": "Priority", "type": "select",
                 "options": [p.value for p in TicketPriority]},
            ],
        )

    @ui.page("/prompts")
    def _prompts():  # noqa: ANN202
        crud_page(
            title="Prompt Library",
            endpoint="/prompts",
            columns=[_col("name", "Name"), _col("slug", "Slug"),
                     _col("status", "Status"), _col("current_version", "Version"), _ACTIONS],
            create_fields=[
                {"name": "name", "label": "Name"},
                {"name": "slug", "label": "Slug"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ],
        )

    @ui.page("/tech-specs")
    def _tech_specs():  # noqa: ANN202
        tech_spec_list_page()

    @ui.page("/tech-specs/{spec_id}")
    def _tech_spec_detail(spec_id: str):  # noqa: ANN202
        tech_spec_detail_page(spec_id)

    @ui.page("/agents")
    def _agents():  # noqa: ANN202
        crud_page(
            title="Agent Registry",
            endpoint="/agents",
            columns=[_col("name", "Name"), _col("slug", "Slug"),
                     _col("status", "Status"), _ACTIONS],
            create_fields=[
                {"name": "name", "label": "Name"},
                {"name": "slug", "label": "Slug"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ],
        )

    @ui.page("/models")
    def _models():  # noqa: ANN202
        crud_page(
            title="Model Registry",
            endpoint="/models",
            columns=[_col("name", "Name"), _col("provider", "Provider"),
                     _col("model_key", "Key"), _col("status", "Status"), _ACTIONS],
            create_fields=[
                {"name": "name", "label": "Name"},
                {"name": "provider", "label": "Provider", "type": "select",
                 "options": [p.value for p in ModelProvider]},
                {"name": "model_key", "label": "Model Key"},
            ],
        )

    @ui.page("/workflows")
    def _workflows():  # noqa: ANN202
        crud_page(
            title="Workflow Registry",
            endpoint="/workflows",
            columns=[_col("name", "Name"), _col("slug", "Slug"),
                     _col("status", "Status"), _ACTIONS],
            create_fields=[
                {"name": "name", "label": "Name"},
                {"name": "slug", "label": "Slug"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ],
        )

    @ui.page("/roles")
    def _roles():  # noqa: ANN202
        crud_page(
            title="Roles",
            endpoint="/roles",
            columns=[_col("name", "Name"), _col("description", "Description"),
                     _col("is_system", "System"), _ACTIONS],
            create_fields=[
                {"name": "name", "label": "Name"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ],
        )

    @ui.page("/events")
    def _events():  # noqa: ANN202
        monitor_page(
            title="Event Log",
            endpoint="/events",
            columns=[_col("event_type", "Type"), _col("source", "Source"),
                     _col("created_at", "When")],
        )

    @ui.page("/queue")
    def _queue():  # noqa: ANN202
        monitor_page(
            title="Task Queue Monitor",
            endpoint="/queue",
            columns=[_col("task_type", "Task"), _col("state", "State"),
                     _col("attempts", "Attempts"), _col("created_at", "When")],
        )

    @ui.page("/audit")
    def _audit():  # noqa: ANN202
        monitor_page(
            title="Audit Log",
            endpoint="/audit",
            columns=[_col("action", "Action"), _col("entity_type", "Entity"),
                     _col("entity_id", "Entity ID"), _col("created_at", "When")],
        )

    # Mark unused import usage for status enum (kept for future status fields)
    _ = RegistryStatus
