"""Auth endpoints: login, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import AuthContext
from app.infrastructure.auth import SupabaseAuthAdapter
from app.presentation.api.v1.dependencies import get_auth
from app.presentation.api.v1.schemas import LoginRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])
_auth = SupabaseAuthAdapter()


@router.post("/login")
def login(body: LoginRequest) -> dict:
    session = _auth.login(body.email, body.password)
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
        "user": {"id": session.user_id, "email": session.email},
    }


@router.post("/refresh")
def refresh(body: RefreshRequest) -> dict:
    session = _auth.refresh(body.refresh_token)
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
    }


@router.get("/me")
def me(auth: AuthContext = Depends(get_auth)) -> dict:
    return {"id": auth.user_id, "email": auth.email}
