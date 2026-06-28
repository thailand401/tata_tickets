"""FastAPI dependencies: extract & verify the authenticated principal."""

from __future__ import annotations

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError
from app.core.security import AuthContext, verify_token

_bearer = HTTPBearer(auto_error=False)


def get_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    """Resolve the current user from the Bearer access token."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token")
    return verify_token(credentials.credentials)


def optional_workspace(
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> str | None:
    """Optional workspace scope for RBAC, passed via header."""
    return x_workspace_id
