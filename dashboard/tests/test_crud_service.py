"""Tests for CrudService: RBAC enforcement and audit/event emission."""

from __future__ import annotations

import pytest

from app.application.services.base import CrudService
from app.core.exceptions import AuthorizationError, NotFoundError
from tests.fakes import FakeRepository


class _ProjectService(CrudService):
    resource = "project"
    entity_type = "project"


@pytest.fixture
def captured(monkeypatch):
    audits: list[dict] = []
    events: list[dict] = []

    monkeypatch.setattr(
        "app.application.services.base.record_audit",
        lambda **kw: audits.append(kw),
    )
    monkeypatch.setattr(
        "app.application.services.base.record_event",
        lambda **kw: events.append(kw),
    )
    return {"audits": audits, "events": events}


@pytest.fixture
def allow_all(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)


@pytest.fixture
def deny_all(monkeypatch):
    def _deny(*_a, **_k):
        raise AuthorizationError("denied")

    monkeypatch.setattr("app.application.rbac.rbac.require", _deny)


def test_create_emits_audit_and_event(captured, allow_all) -> None:
    svc = _ProjectService(FakeRepository())
    row = svc.create("actor-1", {"name": "P", "slug": "p"})

    assert row["name"] == "P"
    assert row["created_by"] == "actor-1"
    assert len(captured["audits"]) == 1
    assert captured["audits"][0]["action"] == "create"
    assert len(captured["events"]) == 1
    assert captured["events"][0]["event_type"] == "project.created"


def test_create_denied_without_permission(deny_all) -> None:
    svc = _ProjectService(FakeRepository())
    with pytest.raises(AuthorizationError):
        svc.create("actor-1", {"name": "P", "slug": "p"})


def test_update_records_before_and_after(captured, allow_all) -> None:
    repo = FakeRepository()
    svc = _ProjectService(repo)
    created = svc.create("actor-1", {"name": "P", "slug": "p"})
    captured["audits"].clear()

    svc.update("actor-1", created["id"], {"name": "P2"})
    audit = captured["audits"][0]
    assert audit["action"] == "update"
    assert audit["before"]["name"] == "P"
    assert audit["after"]["name"] == "P2"


def test_get_missing_raises(allow_all) -> None:
    svc = _ProjectService(FakeRepository())
    with pytest.raises(NotFoundError):
        svc.get("actor-1", "does-not-exist")


def test_delete_records_audit(captured, allow_all) -> None:
    repo = FakeRepository()
    svc = _ProjectService(repo)
    created = svc.create("actor-1", {"name": "P", "slug": "p"})
    captured["audits"].clear()

    svc.delete("actor-1", created["id"])
    assert captured["audits"][0]["action"] == "delete"
    assert repo.get(created["id"]) is None
