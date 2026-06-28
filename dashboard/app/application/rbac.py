"""RBAC engine: resolve a user's effective permissions and enforce checks."""

from __future__ import annotations

from app.core.exceptions import AuthorizationError
from app.infrastructure.supabase.client import get_service_client


class RBAC:
    """Resolves effective permissions from workspace-scoped role assignments.

    Permission codes follow "resource:action" (e.g. "ticket:write").
    A role assignment with workspace_id = NULL is treated as global.
    """

    def effective_permissions(
        self, user_id: str, workspace_id: str | None = None
    ) -> set[str]:
        client = get_service_client()

        # Role assignments that apply: global (workspace_id is null) OR matching ws.
        assignments = (
            client.table("user_roles")
            .select("role_id, workspace_id")
            .eq("user_id", user_id)
            .execute()
            .data
            or []
        )

        role_ids: set[str] = set()
        for a in assignments:
            ws = a.get("workspace_id")
            if ws is None or (workspace_id is not None and ws == workspace_id):
                role_ids.add(a["role_id"])

        if not role_ids:
            return set()

        rp = (
            client.table("role_permissions")
            .select("permission_id, permissions(code)")
            .in_("role_id", list(role_ids))
            .execute()
            .data
            or []
        )

        perms: set[str] = set()
        for row in rp:
            perm = row.get("permissions")
            if isinstance(perm, dict) and perm.get("code"):
                perms.add(perm["code"])
        return perms

    def has_permission(
        self, user_id: str, permission: str, workspace_id: str | None = None
    ) -> bool:
        return permission in self.effective_permissions(user_id, workspace_id)

    def require(
        self, user_id: str, permission: str, workspace_id: str | None = None
    ) -> None:
        if not self.has_permission(user_id, permission, workspace_id):
            raise AuthorizationError(f"Missing permission: {permission}")


rbac = RBAC()
