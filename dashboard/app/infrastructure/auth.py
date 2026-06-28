"""Authentication adapter wrapping Supabase Auth (gotrue) flows."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AuthenticationError
from app.infrastructure.supabase.client import get_anon_client


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    expires_at: int | None
    user_id: str
    email: str | None


class SupabaseAuthAdapter:
    """Login / refresh / logout via Supabase Auth."""

    def login(self, email: str, password: str) -> AuthSession:
        client = get_anon_client()
        try:
            res = client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as exc:  # gotrue raises on bad creds
            raise AuthenticationError("Invalid email or password") from exc

        if not res.session or not res.user:
            raise AuthenticationError("Login failed")

        return AuthSession(
            access_token=res.session.access_token,
            refresh_token=res.session.refresh_token,
            expires_at=res.session.expires_at,
            user_id=res.user.id,
            email=res.user.email,
        )

    def refresh(self, refresh_token: str) -> AuthSession:
        client = get_anon_client()
        try:
            res = client.auth.refresh_session(refresh_token)
        except Exception as exc:
            raise AuthenticationError("Could not refresh session") from exc

        if not res.session or not res.user:
            raise AuthenticationError("Refresh failed")

        return AuthSession(
            access_token=res.session.access_token,
            refresh_token=res.session.refresh_token,
            expires_at=res.session.expires_at,
            user_id=res.user.id,
            email=res.user.email,
        )
