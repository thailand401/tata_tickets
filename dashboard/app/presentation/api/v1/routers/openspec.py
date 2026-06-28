"""OpenSpec router (Phase 3): generate and read OpenSpec change bundles."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.openspec import OpenSpecService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import OpenSpecGenerate

router = APIRouter(prefix="/openspec", tags=["openspec"])


@router.get("/bundles")
def list_bundles(
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return OpenSpecService().list(
        auth.user_id, limit=limit, offset=offset, workspace_id=workspace_id
    )


@router.get("/bundles/{bundle_id}")
def get_bundle(
    bundle_id: str,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    service = OpenSpecService()
    bundle = service.get(auth.user_id, bundle_id, workspace_id=workspace_id)
    bundle["artifacts"] = service.get_artifacts(auth.user_id, bundle_id)
    return bundle


@router.get("/bundles/{bundle_id}/artifacts")
def list_artifacts(
    bundle_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return OpenSpecService().get_artifacts(auth.user_id, bundle_id)


@router.get("/bundles/{bundle_id}/artifacts/{kind}")
def get_artifact(
    bundle_id: str, kind: str, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return OpenSpecService().get_artifact(auth.user_id, bundle_id, kind)


@router.get("/specs/{spec_id}/bundles")
def list_for_spec(
    spec_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return OpenSpecService().list_for_spec(auth.user_id, spec_id)


@router.post("/specs/{spec_id}/generate", status_code=201)
def generate(
    spec_id: str,
    body: OpenSpecGenerate,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return OpenSpecService().generate(
        auth.user_id,
        spec_id,
        spec_version=body.spec_version,
        workspace_id=workspace_id,
    )
