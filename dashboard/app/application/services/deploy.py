"""Deploy & operate service (Phase 12): CI/CD, auto-deploy, health, rollback,
backup/restore, scale and metrics.

This is the operational memory of the pipeline. CI builds images, a webhook or a
manual trigger creates a versioned :class:`Deployment`, health checks flip it
healthy/degraded, rollback reverts to the last good release, scale changes the
replica count, backups snapshot the database, and metrics feed Grafana. The
service records and orchestrates state; the actual container roll-out lives in
docker-compose/CI. All routing logic is pure (:mod:`app.application.deploy`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.application.deploy.pipeline import (
    branch_environment,
    health_summary,
    image_tag,
    metrics_snapshot,
    next_version,
    parse_webhook,
    scale_plan,
)
from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import (
    AuditAction,
    BackupKind,
    BackupStatus,
    DeployEnv,
    DeployStatus,
    DeployTrigger,
    HealthStatus,
)
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

_DEFAULT_REPO = "ghcr.io/tata/dashboard"


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DeployService:
    """Manage deployments, webhooks, health, rollback, scale and backups."""

    resource = "deploy"

    def __init__(
        self,
        deployments: Repository | None = None,
        *,
        backups: Repository | None = None,
        webhooks: Repository | None = None,
    ) -> None:
        self._deployments = deployments or _repo("deployments")
        self._backups = backups or _repo("backups")
        self._webhooks = webhooks or _repo("webhook_events")

    # =====================================================================
    # Deploy: build a versioned release and roll it out (manual or auto)
    # =====================================================================
    def deploy(
        self,
        actor_id: str,
        *,
        bundle_id: str | None = None,
        environment: str = DeployEnv.STAGING.value,
        commit_sha: str | None = None,
        trigger: str = DeployTrigger.MANUAL.value,
        repo: str = _DEFAULT_REPO,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:write", workspace_id)
        valid = environment in DeployEnv._value2member_map_
        env = DeployEnv(environment) if valid else DeployEnv.STAGING
        sequence = len(self._deployments.list(filters={"environment": env.value}, limit=10_000))
        version = next_version(env, sequence)
        deployment = self._deployments.create(
            {
                "workspace_id": workspace_id,
                "bundle_id": bundle_id,
                "environment": env.value,
                "version": version,
                "image": image_tag(repo, version, commit_sha),
                "commit_sha": commit_sha,
                "trigger": trigger,
                "status": DeployStatus.DEPLOYING.value,
                "replicas": 1,
                "health": HealthStatus.DOWN.value,
                "summary": "",
                "created_by": actor_id,
                "deployed_at": _now(),
            }
        )
        record_audit(actor_id=actor_id, action=AuditAction.DISPATCH.value,
                     entity_type="deployment", entity_id=deployment["id"],
                     after={"version": version})
        record_event(event_type="deploy.started", source="deploy", workspace_id=workspace_id,
                     payload={"deployment_id": deployment["id"], "version": version,
                              "env": env.value})
        return deployment

    # =====================================================================
    # Health check: probe a deployment and mark it healthy/degraded
    # =====================================================================
    def health_check(
        self, actor_id: str, deployment_id: str, *, probes: list[dict] | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:write")
        deployment = self._get(deployment_id)
        health = health_summary(probes)
        status = DeployStatus.HEALTHY if health is HealthStatus.HEALTHY else DeployStatus.DEGRADED
        updated = self._deployments.update(
            deployment_id, {"health": health.value, "status": status.value}
        )
        record_event(event_type="deploy.health", source="deploy",
                     workspace_id=deployment.get("workspace_id"),
                     payload={"deployment_id": deployment_id, "health": health.value})
        return updated

    # =====================================================================
    # Rollback: revert an environment to its last healthy release
    # =====================================================================
    def rollback(
        self, actor_id: str, deployment_id: str, *, workspace_id: str | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:rollback", workspace_id)
        current = self._get(deployment_id)
        previous = self._previous_healthy(current)
        if not previous:
            raise OrchestrationError("no previous healthy release to roll back to")
        self._deployments.update(deployment_id, {"status": DeployStatus.ROLLED_BACK.value})
        restored = self._deployments.update(
            previous["id"],
            {"status": DeployStatus.HEALTHY.value, "health": HealthStatus.HEALTHY.value},
        )
        record_audit(actor_id=actor_id, action=AuditAction.ROLLBACK.value,
                     entity_type="deployment", entity_id=deployment_id,
                     after={"restored": previous["id"]})
        record_event(event_type="deploy.rolled_back", source="deploy",
                     workspace_id=current.get("workspace_id"),
                     payload={"from": deployment_id, "to": previous["id"]})
        return restored

    # =====================================================================
    # Scale: change the replica count for a healthy deployment
    # =====================================================================
    def scale(self, actor_id: str, deployment_id: str, *, replicas: int) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:scale")
        deployment = self._get(deployment_id)
        plan = scale_plan(int(deployment.get("replicas", 1)), replicas)
        updated = self._deployments.update(deployment_id, {"replicas": plan["to"]})
        record_event(event_type="deploy.scaled", source="deploy",
                     workspace_id=deployment.get("workspace_id"),
                     payload={"deployment_id": deployment_id, **plan})
        return {"deployment": updated, "plan": plan}

    # =====================================================================
    # Webhook: GitHub/GitLab push -> normalize -> auto-deploy deployable refs
    # =====================================================================
    def handle_webhook(
        self, actor_id: str, *, provider: str, payload: dict, workspace_id: str | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:write", workspace_id)
        parsed = parse_webhook(provider, payload)
        deployment = None
        if parsed["deployable"]:
            env = branch_environment(parsed["ref"])
            deployment = self.deploy(actor_id, environment=env.value,
                                     commit_sha=parsed["commit_sha"], trigger=parsed["provider"],
                                     workspace_id=workspace_id)
        self._webhooks.create({
            "workspace_id": workspace_id, "provider": parsed["provider"], "event": parsed["event"],
            "ref": parsed["ref"], "commit_sha": parsed["commit_sha"],
            "deployment_id": deployment["id"] if deployment else None,
        })
        return {"received": parsed, "deployment": deployment}

    # =====================================================================
    # Backup / restore
    # =====================================================================
    def backup(
        self, actor_id: str, *, kind: str = BackupKind.FULL.value,
        location: str = "", workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:backup", workspace_id)
        snapshot = self._backups.create({
            "workspace_id": workspace_id, "kind": kind,
            "location": location or f"backups/{kind}-{_now()}.dump",
            "size_bytes": 0, "status": BackupStatus.COMPLETE.value, "created_by": actor_id,
        })
        record_event(event_type="deploy.backup", source="deploy", workspace_id=workspace_id,
                     payload={"backup_id": snapshot["id"], "kind": kind})
        return snapshot

    def restore(
        self, actor_id: str, backup_id: str, *, workspace_id: str | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, "deploy:backup", workspace_id)
        snapshot = self._backups.get(backup_id)
        if not snapshot:
            raise NotFoundError("backup not found")
        updated = self._backups.update(backup_id, {"status": BackupStatus.RESTORED.value})
        record_audit(actor_id=actor_id, action=AuditAction.UPDATE.value,
                     entity_type="backup", entity_id=backup_id, after={"restored": True})
        record_event(event_type="deploy.restored", source="deploy", workspace_id=workspace_id,
                     payload={"backup_id": backup_id})
        return updated

    # =====================================================================
    # Read models
    # =====================================================================
    def list_deployments(self, actor_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        rbac.require(actor_id, "deploy:read")
        return self._deployments.list(order_by="created_at", descending=True, limit=limit)

    def metrics(self, actor_id: str) -> dict[str, int]:
        rbac.require(actor_id, "deploy:read")
        return metrics_snapshot(
            self._deployments.list(limit=10_000), self._backups.list(limit=10_000)
        )

    # =====================================================================
    # Internals
    # =====================================================================
    def _get(self, deployment_id: str) -> dict[str, Any]:
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            raise NotFoundError("deployment not found")
        return deployment

    def _previous_healthy(self, current: dict[str, Any]) -> dict[str, Any] | None:
        peers = self._deployments.list(
            filters={"environment": current.get("environment")},
            order_by="created_at", descending=True, limit=200,
        )
        for d in peers:
            if d["id"] != current["id"] and d.get("status") in {
                DeployStatus.HEALTHY.value, DeployStatus.ROLLED_BACK.value,
            }:
                return d
        return None
