"""Tests for JWT verification."""

from __future__ import annotations

import time

import pytest
from jose import jwt

from app.core.exceptions import AuthenticationError
from app.core.security import verify_token

SECRET = "test-secret-key"


def _make_token(**overrides) -> str:
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    payload.update(overrides)
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_verify_valid_token() -> None:
    ctx = verify_token(_make_token())
    assert ctx.user_id == "user-123"
    assert ctx.email == "user@example.com"


def test_verify_rejects_bad_signature() -> None:
    bad = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        verify_token(bad)


def test_verify_rejects_missing_sub() -> None:
    token = jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        verify_token(token)


def test_verify_rejects_expired() -> None:
    with pytest.raises(AuthenticationError):
        verify_token(_make_token(exp=int(time.time()) - 10))
