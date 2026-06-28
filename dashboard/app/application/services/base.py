"""Base CRUD service binding a repository to RBAC + audit/event emission."""

from __future__ import annotations

from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.core.exceptions import NotFoundError
from app.domain.enums import AuditAction
from app.domain.repositories import Repository


class CrudService:
    """Generic create/read/update/delete use cases for a resource.

    Subclasses set ``resource`` (used to build permission codes like
    "<resource>:read") and ``entity_type`` (used in audit entries).
    """

    resource: str = ""
    entity_type: str = ""

    def __init__(self, repository: Repository) -> None:
        self.repo = repository

    # -- permission helpers -------------------------------------------------
    def _perm(self, action: str) -> str:
        return f"{self.resource}:{action}"

    # -- queries ------------------------------------------------------------
    def list(
        self,
        actor_id: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rbac.require(actor_id, self._perm("read"), workspace_id)
        return self.repo.list(
            filters=filters,
            limit=limit,
            offset=offset,
            order_by="created_at",
            descending=True,
        )

    def get(
        self, actor_id: str, entity_id: str, *, workspace_id: str | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, self._perm("read"), workspace_id)
        row = self.repo.get(entity_id)
        if not row:
            raise NotFoundError(f"{self.entity_type} not found")
        return row

    # -- mutations ----------------------------------------------------------
    def create(
        self,
        actor_id: str,
        data: dict[str, Any],
        *,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, self._perm("write"), workspace_id)
        created = self.repo.create(self._on_create(actor_id, data))
        record_audit(
            actor_id=actor_id,
            action=AuditAction.CREATE.value,
            entity_type=self.entity_type,
            entity_id=str(created.get("id")),
            after=created,
        )
        record_event(
            event_type=f"{self.entity_type}.created",
            source="dashboard",
            workspace_id=workspace_id,
            payload={"id": str(created.get("id"))},
        )
        return created

    def update(
        self,
        actor_id: str,
        entity_id: str,
        data: dict[str, Any],
        *,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, self._perm("write"), workspace_id)
        current = self.repo.get(entity_id)
        if not current:
            raise NotFoundError(f"{self.entity_type} not found")
        before = dict(current)  # snapshot before mutation
        updated = self.repo.update(entity_id, data)
        record_audit(
            actor_id=actor_id,
            action=AuditAction.UPDATE.value,
            entity_type=self.entity_type,
            entity_id=entity_id,
            before=before,
            after=updated,
        )
        record_event(
            event_type=f"{self.entity_type}.updated",
            source="dashboard",
            workspace_id=workspace_id,
            payload={"id": entity_id},
        )
        return updated

    def delete(
        self, actor_id: str, entity_id: str, *, workspace_id: str | None = None
    ) -> None:
        rbac.require(actor_id, self._perm("delete"), workspace_id)
        before = self.repo.get(entity_id)
        if not before:
            raise NotFoundError(f"{self.entity_type} not found")
        self.repo.delete(entity_id)
        record_audit(
            actor_id=actor_id,
            action=AuditAction.DELETE.value,
            entity_type=self.entity_type,
            entity_id=entity_id,
            before=before,
        )
        record_event(
            event_type=f"{self.entity_type}.deleted",
            source="dashboard",
            workspace_id=workspace_id,
            payload={"id": entity_id},
        )

    # -- hooks --------------------------------------------------------------
    def _on_create(self, actor_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Inject created_by when the table supports it. Override as needed."""
        payload = dict(data)
        payload.setdefault("created_by", actor_id)
        return payload
