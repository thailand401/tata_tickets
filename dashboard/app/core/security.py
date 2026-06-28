"""JWT verification for Supabase-issued access tokens."""

from __future__ import annotations

from dataclasses import dataclass, field

from jose import JWTError, jwt

from app.core.exceptions import AuthenticationError
from app.core.settings import get_settings


@dataclass(frozen=True)
class AuthContext:
    """Authenticated principal extracted from a verified JWT."""

    user_id: str
    email: str | None = None
    claims: dict = field(default_factory=dict)


def verify_token(token: str) -> AuthContext:
    """Verify a Supabase access token (HS256, signed with the JWT secret).

    Raises AuthenticationError on any failure.
    """
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise AuthenticationError("JWT secret is not configured")

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError as exc:  # noqa: PERF203
        raise AuthenticationError(f"Invalid token: {exc}") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject (sub) claim")

    return AuthContext(
        user_id=user_id,
        email=payload.get("email"),
        claims=payload,
    )
