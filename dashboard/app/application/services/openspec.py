"""OpenSpec service (Phase 3): Tech Spec -> standard OpenSpec change bundle.

Takes the latest *ready* Tech Spec version (the validated Phase 2 output) and
produces a bundle of standard OpenSpec documents — proposal, requirements,
tasks, architecture, migration and checklist. Documentation only; never code.
The ``tasks`` artifact carries a structured DAG that Phase 4 orchestrates.
"""

from __future__ import annotations

import re
from typing import Any

from app.application.openspec.builder import build_bundle
from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.application.services.base import CrudService
from app.core.exceptions import GenerationError, NotFoundError, ValidationError
from app.domain.enums import ArtifactKind, AuditAction, SpecBundleStatus
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:60] or "change"


class OpenSpecService(CrudService):
    resource = "openspec"
    entity_type = "spec_bundle"

    def __init__(
        self,
        repository: Repository | None = None,
        *,
        artifacts: Repository | None = None,
        specs: Repository | None = None,
        spec_versions: Repository | None = None,
    ) -> None:
        super().__init__(repository or _repo("spec_bundles"))
        self._artifacts = artifacts or _repo("spec_artifacts")
        self._specs = specs or _repo("tech_specs")
        self._spec_versions = spec_versions or _repo("tech_spec_versions")

    # -- queries ------------------------------------------------------------
    def get_artifacts(self, actor_id: str, bundle_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "openspec:read")
        return self._artifacts.list(filters={"bundle_id": bundle_id}, limit=50)

    def get_artifact(
        self, actor_id: str, bundle_id: str, kind: str
    ) -> dict[str, Any]:
        rbac.require(actor_id, "openspec:read")
        row = self._artifacts.find_one({"bundle_id": bundle_id, "kind": kind})
        if not row:
            raise NotFoundError(f"artifact {kind} not found")
        return row

    def list_for_spec(self, actor_id: str, spec_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "openspec:read")
        return self.repo.list(
            filters={"spec_id": spec_id},
            order_by="created_at",
            descending=True,
            limit=100,
        )

    # -- generation ---------------------------------------------------------
    def generate(
        self,
        actor_id: str,
        spec_id: str,
        *,
        spec_version: int | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate an OpenSpec bundle from a ready Tech Spec version."""
        rbac.require(actor_id, "openspec:generate", workspace_id)
        spec = self._specs.get(spec_id)
        if not spec:
            raise NotFoundError("tech spec not found")

        version_row = self._resolve_version(spec_id, spec_version)
        content = version_row.get("content") or {}
        if not content:
            raise ValidationError("Tech spec version has no structured content")

        title = spec.get("title") or "Change"
        bundle = self.repo.create(
            {
                "spec_id": spec_id,
                "spec_version": version_row.get("version"),
                "workspace_id": workspace_id or spec.get("workspace_id"),
                "title": title,
                "slug": _slugify(title),
                "status": SpecBundleStatus.GENERATING.value,
                "created_by": actor_id,
            }
        )
        bundle_id = str(bundle.get("id"))

        try:
            artifacts = build_bundle(title, content)
            stored: list[dict[str, Any]] = []
            for kind in ArtifactKind:
                art = artifacts[kind.value]
                stored.append(
                    self._artifacts.create(
                        {
                            "bundle_id": bundle_id,
                            "kind": kind.value,
                            "title": art["title"],
                            "content": art["content"],
                            "data": art["data"],
                        }
                    )
                )
            bundle = self.repo.update(
                bundle_id, {"status": SpecBundleStatus.READY.value}
            )
        except Exception as exc:
            self.repo.update(
                bundle_id,
                {"status": SpecBundleStatus.FAILED.value, "error": str(exc)},
            )
            self._emit(actor_id, bundle_id, workspace_id, succeeded=False)
            raise GenerationError(f"OpenSpec generation failed: {exc}") from exc

        self._emit(actor_id, bundle_id, workspace_id, succeeded=True)
        return {**bundle, "artifacts": stored}

    # -- helpers ------------------------------------------------------------
    def _resolve_version(
        self, spec_id: str, spec_version: int | None
    ) -> dict[str, Any]:
        if spec_version is not None:
            row = self._spec_versions.find_one(
                {"spec_id": spec_id, "version": spec_version}
            )
            if not row:
                raise NotFoundError(f"spec version {spec_version} not found")
            if row.get("status") != "succeeded":
                raise ValidationError("Selected spec version did not succeed")
            return row
        # Latest succeeded version.
        versions = self._spec_versions.list(
            filters={"spec_id": spec_id, "status": "succeeded"},
            order_by="version",
            descending=True,
            limit=1,
        )
        if not versions:
            raise ValidationError("No ready (succeeded) tech spec version to use")
        return versions[0]

    def _emit(
        self,
        actor_id: str,
        bundle_id: str,
        workspace_id: str | None,
        *,
        succeeded: bool,
    ) -> None:
        record_audit(
            actor_id=actor_id,
            action=AuditAction.GENERATE.value,
            entity_type="spec_bundle",
            entity_id=bundle_id,
        )
        record_event(
            event_type="openspec.generated" if succeeded else "openspec.failed",
            source="dashboard",
            workspace_id=workspace_id,
            payload={"bundle_id": bundle_id},
        )
