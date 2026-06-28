"""Tests for the RBAC permission resolution engine."""

from __future__ import annotations

import pytest

from app.application.rbac import RBAC
from app.core.exceptions import AuthorizationError


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def in_(self, *_a, **_k):
        return self

    def execute(self):
        return _Result(self._data)


class _FakeClient:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _Query(self._tables.get(name, []))


@pytest.fixture
def patched_client(monkeypatch):
    def _install(tables):
        monkeypatch.setattr(
            "app.application.rbac.get_service_client",
            lambda: _FakeClient(tables),
        )

    return _install


def test_effective_permissions_global(patched_client) -> None:
    patched_client(
        {
            "user_roles": [{"role_id": "r1", "workspace_id": None}],
            "role_permissions": [
                {"permission_id": "p1", "permissions": {"code": "ticket:read"}},
                {"permission_id": "p2", "permissions": {"code": "ticket:write"}},
            ],
        }
    )
    perms = RBAC().effective_permissions("u1")
    assert perms == {"ticket:read", "ticket:write"}


def test_workspace_scoped_assignment_filtered(patched_client) -> None:
    patched_client(
        {
            "user_roles": [{"role_id": "r1", "workspace_id": "ws-A"}],
            "role_permissions": [
                {"permission_id": "p1", "permissions": {"code": "ticket:read"}}
            ],
        }
    )
    # Request for a different workspace -> the ws-scoped role does not apply.
    assert RBAC().effective_permissions("u1", workspace_id="ws-B") == set()
    # Matching workspace -> applies.
    assert RBAC().effective_permissions("u1", workspace_id="ws-A") == {"ticket:read"}


def test_require_raises_when_missing(patched_client) -> None:
    patched_client({"user_roles": [], "role_permissions": []})
    with pytest.raises(AuthorizationError):
        RBAC().require("u1", "ticket:write")
