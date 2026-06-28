"""Tech Spec router: CRUD plus AI generation, history and version compare."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.application.services.tech_spec import TechSpecService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import (
    TechSpecCreate,
    TechSpecGenerate,
    TechSpecUpdate,
)

router = APIRouter(prefix="/tech-specs", tags=["tech-specs"])


@router.get("")
def list_specs(
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return TechSpecService().list(
        auth.user_id, limit=limit, offset=offset, workspace_id=workspace_id
    )


@router.get("/{spec_id}")
def get_spec(
    spec_id: str,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return TechSpecService().get(auth.user_id, spec_id, workspace_id=workspace_id)


@router.post("", status_code=201)
def create_spec(
    body: TechSpecCreate,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return TechSpecService().create(
        auth.user_id, body.model_dump(exclude_unset=True), workspace_id=workspace_id
    )


@router.patch("/{spec_id}")
def update_spec(
    spec_id: str,
    body: TechSpecUpdate,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return TechSpecService().update(
        auth.user_id,
        spec_id,
        body.model_dump(exclude_unset=True),
        workspace_id=workspace_id,
    )


@router.delete("/{spec_id}", status_code=204)
def delete_spec(
    spec_id: str,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> None:
    TechSpecService().delete(auth.user_id, spec_id, workspace_id=workspace_id)


# -- generation / history --------------------------------------------------
@router.post("/{spec_id}/generate", status_code=201)
def generate(
    spec_id: str,
    body: TechSpecGenerate,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return TechSpecService().generate(
        auth.user_id,
        spec_id,
        model_id=body.model_id,
        prompt_id=body.prompt_id,
        temperature=body.temperature,
        max_attempts=body.max_attempts,
        notes=body.notes,
        workspace_id=workspace_id,
    )


@router.get("/{spec_id}/versions")
def list_versions(
    spec_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return TechSpecService().list_versions(auth.user_id, spec_id)


@router.get("/{spec_id}/versions/{version}")
def get_version(
    spec_id: str, version: int, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return TechSpecService().get_version(auth.user_id, spec_id, version)


@router.get("/{spec_id}/compare")
def compare_versions(
    spec_id: str,
    a: int = Query(..., ge=1),
    b: int = Query(..., ge=1),
    auth: AuthContext = Depends(get_auth),
) -> dict[str, Any]:
    return TechSpecService().compare(auth.user_id, spec_id, a, b)
