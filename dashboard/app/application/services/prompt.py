"""Prompt service: prompt CRUD plus version creation and rollback."""

from __future__ import annotations

from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.application.services.base import CrudService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.enums import AuditAction
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository


class PromptService(CrudService):
    resource = "prompt"
    entity_type = "prompt"

    def __init__(self) -> None:
        super().__init__(SupabaseRepository(get_service_client(), "prompts"))
        self._versions = SupabaseRepository(get_service_client(), "prompt_versions")

    # -- versions -----------------------------------------------------------
    def list_versions(self, actor_id: str, prompt_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "prompt:read")
        return self._versions.list(
            filters={"prompt_id": prompt_id},
            order_by="version",
            descending=True,
            limit=200,
        )

    def add_version(
        self,
        actor_id: str,
        prompt_id: str,
        *,
        content: str,
        variables: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create a new immutable version and bump prompt.current_version."""
        rbac.require(actor_id, "prompt:write")
        prompt = self.repo.get(prompt_id)
        if not prompt:
            raise NotFoundError("prompt not found")
        if not content or not content.strip():
            raise ValidationError("Prompt content cannot be empty")

        next_version = int(prompt.get("current_version", 0)) + 1
        version_row = self._versions.create(
            {
                "prompt_id": prompt_id,
                "version": next_version,
                "content": content,
                "variables": variables or {},
                "notes": notes,
                "created_by": actor_id,
            }
        )
        self.repo.update(prompt_id, {"current_version": next_version})

        record_audit(
            actor_id=actor_id,
            action=AuditAction.UPDATE.value,
            entity_type="prompt_version",
            entity_id=str(version_row.get("id")),
            after=version_row,
        )
        record_event(
            event_type="prompt.version_added",
            source="dashboard",
            payload={"prompt_id": prompt_id, "version": next_version},
        )
        return version_row

    def rollback(self, actor_id: str, prompt_id: str, version: int) -> dict[str, Any]:
        """Roll back by creating a NEW version that copies an older one.

        History is preserved (never destructive); the rollback itself is a
        new version pointing at the previous content.
        """
        rbac.require(actor_id, "prompt:rollback")
        prompt = self.repo.get(prompt_id)
        if not prompt:
            raise NotFoundError("prompt not found")

        target = self._versions.find_one({"prompt_id": prompt_id, "version": version})
        if not target:
            raise NotFoundError(f"prompt version {version} not found")

        new_version = self.add_version(
            actor_id,
            prompt_id,
            content=target["content"],
            variables=target.get("variables") or {},
            notes=f"Rollback to v{version}",
        )
        record_audit(
            actor_id=actor_id,
            action=AuditAction.ROLLBACK.value,
            entity_type="prompt",
            entity_id=prompt_id,
            before={"to_version": version},
            after={"new_version": new_version.get("version")},
        )
        record_event(
            event_type="prompt.rolled_back",
            source="dashboard",
            payload={"prompt_id": prompt_id, "to_version": version},
        )
        return new_version
