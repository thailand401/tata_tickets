"""Deploy & operate router (Phase 12): CI/CD, webhooks, health, rollback, scale.

A bundle is shipped as a versioned deployment — manually or auto-deployed from a
GitHub/GitLab push webhook on a deployable branch. Health checks flip it
healthy/degraded; rollback reverts to the last good release; scale changes
replicas; backup/restore snapshot the database; metrics feed Grafana.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.deploy import DeployService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import (
    BackupIn,
    DeployIn,
    HealthCheckIn,
    RestoreIn,
    ScaleIn,
    WebhookIn,
)

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.post("/deployments", status_code=201)
def deploy(
    body: DeployIn,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return DeployService().deploy(
        auth.user_id, bundle_id=body.bundle_id, environment=body.environment,
        commit_sha=body.commit_sha, trigger=body.trigger, repo=body.repo,
        workspace_id=body.workspace_id or workspace_id,
    )


@router.get("/deployments")
def list_deployments(
    limit: int = 100, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return DeployService().list_deployments(auth.user_id, limit=limit)


@router.post("/deployments/{deployment_id}/health")
def health_check(
    deployment_id: str, body: HealthCheckIn, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return DeployService().health_check(auth.user_id, deployment_id, probes=body.probes)


@router.post("/deployments/{deployment_id}/rollback")
def rollback(deployment_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return DeployService().rollback(auth.user_id, deployment_id)


@router.post("/deployments/{deployment_id}/scale")
def scale(
    deployment_id: str, body: ScaleIn, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return DeployService().scale(auth.user_id, deployment_id, replicas=body.replicas)


@router.post("/webhook")
def webhook(
    body: WebhookIn,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return DeployService().handle_webhook(
        auth.user_id, provider=body.provider, payload=body.payload,
        workspace_id=body.workspace_id or workspace_id,
    )


@router.post("/backups", status_code=201)
def backup(body: BackupIn, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return DeployService().backup(
        auth.user_id, kind=body.kind, location=body.location, workspace_id=body.workspace_id
    )


@router.post("/backups/{backup_id}/restore")
def restore(
    backup_id: str, body: RestoreIn, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return DeployService().restore(auth.user_id, backup_id, workspace_id=body.workspace_id)


@router.get("/metrics")
def metrics(auth: AuthContext = Depends(get_auth)) -> dict[str, int]:
    return DeployService().metrics(auth.user_id)
