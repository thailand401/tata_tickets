"""Agent bridge router (Phase 5): the VS Code extension <-> dashboard bridge.

A worker pulls the next ready task and pushes progress, logs, commits, reviews,
errors and completion. No ticket management lives here — this is a thin bridge.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from app.application.services.agent_bridge import AgentBridgeService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import (
    AgentCommit,
    AgentComplete,
    AgentError,
    AgentLog,
    AgentProgress,
    AgentPull,
    AgentReview,
)

router = APIRouter(prefix="/agent", tags=["agent-bridge"])


@router.post("/tasks/next")
def pull_next(
    body: AgentPull,
    response: Response,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any] | None:
    run = AgentBridgeService().pull_next(
        auth.user_id, categories=body.categories, workspace_id=workspace_id
    )
    if run is None:
        response.status_code = 204
        return None
    return run


@router.get("/tasks/{run_id}")
def sync(run_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return AgentBridgeService().sync(auth.user_id, run_id)


@router.post("/tasks/{run_id}/progress")
def push_progress(
    run_id: str, body: AgentProgress, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return AgentBridgeService().push_progress(
        auth.user_id, run_id, percent=body.percent, message=body.message, data=body.data
    )


@router.post("/tasks/{run_id}/log")
def push_log(
    run_id: str, body: AgentLog, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return AgentBridgeService().push_log(
        auth.user_id, run_id, level=body.level, message=body.message, data=body.data
    )


@router.post("/tasks/{run_id}/commit")
def push_commit(
    run_id: str, body: AgentCommit, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return AgentBridgeService().push_commit(
        auth.user_id, run_id, sha=body.sha, message=body.message,
        branch=body.branch, url=body.url,
    )


@router.post("/tasks/{run_id}/review")
def push_review(
    run_id: str, body: AgentReview, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return AgentBridgeService().push_review(
        auth.user_id, run_id, status=body.status, summary=body.summary, data=body.data
    )


@router.post("/tasks/{run_id}/error")
def push_error(
    run_id: str, body: AgentError, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return AgentBridgeService().push_error(
        auth.user_id, run_id, message=body.message, retry=body.retry, data=body.data
    )


@router.post("/tasks/{run_id}/complete")
def push_complete(
    run_id: str, body: AgentComplete, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return AgentBridgeService().push_complete(
        auth.user_id, run_id, summary=body.summary, result=body.result
    )
