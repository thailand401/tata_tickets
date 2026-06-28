"""Monitoring & catalog routers: event log, task queue, audit log, permissions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.monitoring import MonitoringService, PermissionService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth

router = APIRouter(tags=["monitoring"])


@router.get("/events")
def event_log(
    limit: int = 100, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return MonitoringService().event_log(auth.user_id, limit=limit)


@router.get("/queue")
def task_queue(
    limit: int = 100, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return MonitoringService().task_queue(auth.user_id, limit=limit)


@router.get("/audit")
def audit_log(
    limit: int = 100, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return MonitoringService().audit_log(auth.user_id, limit=limit)


@router.get("/permissions")
def permissions(auth: AuthContext = Depends(get_auth)) -> list[dict[str, Any]]:
    return PermissionService().list(auth.user_id)
