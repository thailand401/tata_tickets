"""Read-only services for monitoring views (event log, queue, audit log)."""

from __future__ import annotations

from typing import Any

from app.application.rbac import rbac
from app.infrastructure.realtime import fetch_recent


class MonitoringService:
    """Read-only access to observability tables, guarded by permissions."""

    def event_log(self, actor_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rbac.require(actor_id, "event:read")
        return fetch_recent("event_log", limit=limit)

    def task_queue(self, actor_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rbac.require(actor_id, "queue:read")
        return fetch_recent("task_queue", limit=limit, order_by="created_at")

    def audit_log(self, actor_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rbac.require(actor_id, "audit:read")
        return fetch_recent("audit_log", limit=limit)


class PermissionService:
    """Read access to the permission catalog."""

    def list(self, actor_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rbac.require(actor_id, "role:read")
        from app.infrastructure.supabase.client import get_service_client

        return (
            get_service_client()
            .table("permissions")
            .select("*")
            .order("code")
            .limit(limit)
            .execute()
            .data
            or []
        )
