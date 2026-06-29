"""Phase 8 tests: test generation — OpenSpec bundle -> test plan + report."""

from __future__ import annotations

import pytest

from app.application.services.testgen import TestGenService
from app.application.testgen.builder import build_suites, build_test_plan
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.enums import TestKind, TestPlanStatus
from tests.fakes import FakeRepository

_TASKS = [
    {"key": "T1", "title": "Design schema: users", "category": "database", "depends_on": []},
    {"key": "T2", "title": "Implement endpoint: POST /auth/login", "category": "backend",
     "depends_on": ["T1"]},
    {"key": "T3", "title": "Build UI for login", "category": "frontend", "depends_on": ["T2"]},
    {"key": "T4", "title": "Write & run tests", "category": "testing",
     "depends_on": ["T2", "T3"], "acceptance": "Valid creds -> session; Bad code -> rejected"},
]
_DOCS = {
    "tasks": {"title": "Tasks", "content": "# Tasks", "data": {"tasks": _TASKS}},
    "architecture": {"title": "Arch", "content": "# Arch", "data": {}},
}


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.testgen.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.testgen.record_event", lambda **k: None)


def _make_service():
    plans = FakeRepository()
    suites = FakeRepository()
    cases = FakeRepository()
    bundles = FakeRepository()
    artifacts = FakeRepository()
    service = TestGenService(
        plans, suites=suites, cases=cases, bundles=bundles, artifacts=artifacts
    )
    return service, plans, suites, cases, bundles, artifacts


def _seed_bundle(bundles, artifacts) -> str:
    bundle = bundles.create({"title": "Login", "workspace_id": "ws1", "status": "ready"})
    bid = bundle["id"]
    for kind, doc in _DOCS.items():
        artifacts.create(
            {"bundle_id": bid, "kind": kind, "title": doc["title"],
             "content": doc["content"], "data": doc["data"]}
        )
    return bid


# -- pure builder ----------------------------------------------------------
def test_build_suites_covers_every_kind() -> None:
    suites = build_suites(_DOCS)
    assert {s["kind"] for s in suites} == {k.value for k in TestKind}
    for s in suites:
        assert s["cases"], f"{s['kind']} has no cases"


def test_build_plan_reports_counts_and_mocks_and_budgets() -> None:
    plan = build_test_plan("Login", _DOCS, coverage_target=90)
    assert plan["suite_count"] == len(list(TestKind))
    assert plan["case_count"] == sum(len(s["cases"]) for s in plan["suites"])
    mock = next(s for s in plan["suites"] if s["kind"] == TestKind.MOCK.value)
    bench = next(s for s in plan["suites"] if s["kind"] == TestKind.BENCHMARK.value)
    assert mock["mocks"]
    assert bench["data"]["budgets"]
    assert "Coverage target:** 90%" in plan["report"] or "90%" in plan["report"]


# -- service ---------------------------------------------------------------
def test_generate_creates_ready_plan_with_suites_and_cases() -> None:
    service, plans, suites, cases, bundles, artifacts = _make_service()
    bid = _seed_bundle(bundles, artifacts)

    result = service.generate("u", bid)

    assert result["status"] == TestPlanStatus.READY.value
    assert len(suites.list()) == len(list(TestKind))
    assert result["case_count"] == len(cases.list())
    assert result["report"]


def test_generate_requires_tasks_artifact() -> None:
    service, _p, _s, _c, bundles, _a = _make_service()
    bundle = bundles.create({"title": "Empty", "status": "ready"})
    with pytest.raises(ValidationError):
        service.generate("u", bundle["id"])


def test_generate_unknown_bundle_raises() -> None:
    service, *_ = _make_service()
    with pytest.raises(NotFoundError):
        service.generate("u", "nope")


def test_report_returns_suites_with_cases() -> None:
    service, _p, _s, _c, bundles, artifacts = _make_service()
    bid = _seed_bundle(bundles, artifacts)
    plan = service.generate("u", bid)

    report = service.report("u", plan["id"])

    assert report["plan"]["id"] == plan["id"]
    assert len(report["suites"]) == len(list(TestKind))
    assert all("cases" in s for s in report["suites"])
