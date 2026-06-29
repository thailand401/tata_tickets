"""Phase 11 tests: multi-agent fleet — specialist roles + auto-assignment."""

from __future__ import annotations

import pytest

from app.application.orchestration.scheduler import (
    assign,
    assign_all,
    detect_stack,
    match_role,
    select_specialist,
)
from app.application.services.fleet import DEFAULT_FLEET, AgentFleetService
from app.core.exceptions import NotFoundError
from app.domain.enums import AgentRole
from tests.fakes import FakeRepository


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.fleet.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.fleet.record_event", lambda **k: None)


def _make():
    agents, runs, bundles = FakeRepository(), FakeRepository(), FakeRepository()
    return AgentFleetService(agents, runs=runs, bundles=bundles), agents, runs, bundles


# -- scheduler: stack detection beats the category lane --------------------
def test_detect_stack_recognises_specialists() -> None:
    assert detect_stack("Build a Flutter screen in Dart") is AgentRole.FLUTTER
    assert detect_stack("Add a Drupal module in PHP") is AgentRole.DRUPAL
    assert detect_stack("FastAPI service in Python") is AgentRole.PYTHON
    assert detect_stack("Express server with TypeScript") is AgentRole.NODE
    assert detect_stack("nothing special") is None


def test_match_role_stack_overrides_category() -> None:
    assert match_role("Flutter mobile app", "backend") is AgentRole.FLUTTER
    assert match_role("Drupal CMS endpoint", "backend") is AgentRole.DRUPAL
    assert match_role("plain endpoint", "backend") is AgentRole.BACKEND
    assert match_role("login page", "frontend") is AgentRole.FRONTEND
    assert match_role("run tests", "testing") is AgentRole.TEST
    assert match_role("write docs", "documentation") is AgentRole.DOCS


# -- scheduler: selection prefers specialist then generalist ---------------
def test_select_specialist_prefers_role_then_generalist() -> None:
    agents = [
        {"id": "1", "slug": "py", "status": "active", "role": "python"},
        {"id": "2", "slug": "gen", "status": "active", "role": "generalist"},
    ]
    assert select_specialist(AgentRole.PYTHON, agents)["slug"] == "py"
    assert select_specialist(AgentRole.FLUTTER, agents)["slug"] == "gen"


def test_assign_all_is_deterministic() -> None:
    agents = [{"id": str(s["role"].value), "slug": s["slug"], "status": "active",
               "role": s["role"].value} for s in DEFAULT_FLEET]
    tasks = [{"key": "T1", "title": "Flutter app", "category": "frontend"},
             {"key": "T2", "title": "pytest suite", "category": "testing"}]
    a, b = assign_all(tasks, agents), assign_all(tasks, agents)
    assert a == b
    assert a[0]["agent_slug"] == "flutter-agent" and a[1]["agent_slug"] == "test-agent"


def test_assign_unassigned_when_no_agent() -> None:
    plan = assign({"key": "T", "title": "x", "category": "backend"}, [])
    assert plan["status"] == "unassigned" and plan["agent_id"] is None


# -- service: seed is idempotent -------------------------------------------
def test_seed_fleet_idempotent() -> None:
    service, agents, *_ = _make()
    first = service.seed_fleet("u")
    assert len(first) == len(DEFAULT_FLEET)
    service.seed_fleet("u")
    assert len(agents.list(limit=100)) == len(DEFAULT_FLEET)  # upsert by slug


# -- service: assign every task run of a bundle ----------------------------
def test_assign_bundle_routes_to_specialists() -> None:
    service, _agents, runs, bundles = _make()
    service.seed_fleet("u")
    bid = bundles.create({"title": "B", "workspace_id": "ws1"})["id"]
    runs.create({"bundle_id": bid, "task_key": "T1", "title": "Flutter screen",
                 "category": "frontend", "workspace_id": "ws1"})
    runs.create({"bundle_id": bid, "task_key": "T2", "title": "REST endpoint",
                 "category": "backend", "workspace_id": "ws1"})

    results = service.assign_bundle("u", bid)
    by_key = {r["task_key"]: r for r in results}
    assert by_key["T1"]["agent_slug"] == "flutter-agent"
    assert by_key["T2"]["agent_slug"] == "backend-agent"


def test_assign_bundle_missing_raises() -> None:
    service, *_ = _make()
    with pytest.raises(NotFoundError):
        service.assign_bundle("u", "nope")
