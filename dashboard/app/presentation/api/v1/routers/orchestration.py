"""Orchestration router (Phase 4): enqueue, run, resume, cancel, inspect."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.orchestrator import OrchestratorService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import OrchestrationEnqueue, OrchestrationRun

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.post("/bundles/{bundle_id}/enqueue", status_code=201)
def enqueue(
    bundle_id: str,
    body: OrchestrationEnqueue,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return OrchestratorService().enqueue(
        auth.user_id,
        bundle_id,
        max_attempts=body.max_attempts,
        timeout_seconds=body.timeout_seconds,
        workspace_id=workspace_id,
    )


@router.post("/bundles/{bundle_id}/run")
def run(
    bundle_id: str,
    body: OrchestrationRun,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return OrchestratorService().run(
        auth.user_id, bundle_id, max_parallel=body.max_parallel, workspace_id=workspace_id
    )


@router.post("/bundles/{bundle_id}/resume")
def resume(
    bundle_id: str,
    body: OrchestrationRun,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return OrchestratorService().resume(
        auth.user_id, bundle_id, max_parallel=body.max_parallel, workspace_id=workspace_id
    )


@router.get("/bundles/{bundle_id}/runs")
def list_runs(
    bundle_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return OrchestratorService().list_runs(auth.user_id, bundle_id)


@router.get("/runs/{run_id}")
def get_run(run_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return OrchestratorService().get_run(auth.user_id, run_id)


@router.get("/runs/{run_id}/logs")
def run_logs(
    run_id: str, limit: int = 200, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return OrchestratorService().run_logs(auth.user_id, run_id, limit=limit)


@router.post("/runs/{run_id}/cancel")
def cancel(
    run_id: str,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return OrchestratorService().cancel(auth.user_id, run_id, workspace_id=workspace_id)
