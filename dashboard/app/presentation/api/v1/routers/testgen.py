"""Test-generation router (Phase 8): OpenSpec bundle -> test plan + report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.testgen import TestGenService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import TestGenGenerate

router = APIRouter(prefix="/testgen", tags=["testgen"])


@router.get("/bundles/{bundle_id}/plans")
def list_for_bundle(
    bundle_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return TestGenService().list_for_bundle(auth.user_id, bundle_id)


@router.get("/plans/{plan_id}")
def get_report(plan_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return TestGenService().report(auth.user_id, plan_id)


@router.get("/plans/{plan_id}/suites")
def list_suites(
    plan_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return TestGenService().get_suites(auth.user_id, plan_id)


@router.get("/suites/{suite_id}/cases")
def list_cases(
    suite_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return TestGenService().get_cases(auth.user_id, suite_id)


@router.post("/bundles/{bundle_id}/generate", status_code=201)
def generate(
    bundle_id: str,
    body: TestGenGenerate,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return TestGenService().generate(
        auth.user_id,
        bundle_id,
        coverage_target=body.coverage_target,
        workspace_id=workspace_id,
    )
