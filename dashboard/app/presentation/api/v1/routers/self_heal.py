"""Self-healing router (Phase 9): receive errors -> fix loop -> pass -> commit.

The fix loop runs inside the VS Code extension; this bridge records the session,
every gate step, and on success flips the task run to SUCCEEDED. Reuses the
``agent:bridge`` permission (no new permission). Mounted under /agent so it sits
beside the Phase 5/6 bridge endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.self_heal import RepairService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth
from app.presentation.api.v1.schemas import (
    RepairFinish,
    RepairStart,
    RepairStepIn,
)

router = APIRouter(prefix="/agent", tags=["self-heal"])


@router.post("/tasks/{run_id}/repair/session")
def start_session(
    run_id: str, body: RepairStart, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return RepairService().start_session(
        auth.user_id, run_id, errors=body.errors, max_iterations=body.max_iterations
    )


@router.get("/repair/sessions/{session_id}")
def get_session(
    session_id: str, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return RepairService().get_session(auth.user_id, session_id)


@router.post("/repair/sessions/{session_id}/step")
def record_step(
    session_id: str, body: RepairStepIn, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return RepairService().record_step(
        auth.user_id,
        session_id,
        iteration=body.iteration,
        gate=body.gate,
        result=body.result,
        output=body.output,
        files=body.files,
        error=body.error,
    )


@router.post("/repair/sessions/{session_id}/finish")
def finish_session(
    session_id: str, body: RepairFinish, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return RepairService().finish_session(
        auth.user_id,
        session_id,
        status=body.status,
        commit_sha=body.commit_sha,
        summary=body.summary,
    )
