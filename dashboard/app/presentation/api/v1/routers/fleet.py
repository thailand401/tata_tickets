"""Agent fleet router (Phase 11): seed specialists, auto-assign, roster, match.

A fleet of specialist agents (backend, frontend, flutter, python, node, drupal,
review, test, docs, planner) is seeded once; the scheduler then auto-assigns
each task run of a bundle to the best specialist. ``/match`` previews the
routing for a free-text task without touching any run.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.fleet import AgentFleetService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import FleetAssign, FleetMatch, FleetSeed

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.post("/seed", status_code=201)
def seed(
    body: FleetSeed,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return AgentFleetService().seed_fleet(
        auth.user_id, workspace_id=body.workspace_id or workspace_id
    )


@router.get("/roster")
def roster(
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return AgentFleetService().roster(auth.user_id, workspace_id=workspace_id)


@router.post("/bundles/{bundle_id}/assign")
def assign(
    bundle_id: str,
    body: FleetAssign,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return AgentFleetService().assign_bundle(
        auth.user_id, bundle_id, workspace_id=body.workspace_id or workspace_id
    )


@router.post("/match")
def match(body: FleetMatch, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return AgentFleetService().match(auth.user_id, title=body.title, category=body.category)
