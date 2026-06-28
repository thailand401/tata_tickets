"""Concrete resource services with correct permission + audit bindings."""

from __future__ import annotations

from typing import Any

from app.application.services.base import CrudService
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


class ProjectService(CrudService):
    resource = "project"
    entity_type = "project"

    def __init__(self) -> None:
        super().__init__(_repo("projects"))


class WorkspaceService(CrudService):
    resource = "workspace"
    entity_type = "workspace"

    def __init__(self) -> None:
        super().__init__(_repo("workspaces"))


class TicketService(CrudService):
    resource = "ticket"
    entity_type = "ticket"

    def __init__(self) -> None:
        super().__init__(_repo("tickets"))


class AgentService(CrudService):
    resource = "agent"
    entity_type = "agent"

    def __init__(self) -> None:
        super().__init__(_repo("agents"))


class WorkflowService(CrudService):
    resource = "workflow"
    entity_type = "workflow"

    def __init__(self) -> None:
        super().__init__(_repo("workflows"))


class ModelService(CrudService):
    """models table has no created_by column."""

    resource = "model"
    entity_type = "model"

    def __init__(self) -> None:
        super().__init__(_repo("models"))

    def _on_create(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return dict(data)


class RoleService(CrudService):
    """roles use the role:read / role:write permission codes."""

    resource = "role"
    entity_type = "role"

    def __init__(self) -> None:
        super().__init__(_repo("roles"))

    def _perm(self, action: str) -> str:
        # roles only define read/write (no separate delete permission)
        return f"role:{'read' if action == 'read' else 'write'}"

    def _on_create(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return dict(data)
