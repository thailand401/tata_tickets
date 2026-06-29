"""Phase 9 tests: self-healing loop — receive errors -> fix -> pass -> commit."""

from __future__ import annotations

import pytest

from app.application.services.self_heal import RepairService
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import RepairSessionStatus, RunState
from tests.fakes import FakeRepository


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.application.services.self_heal.record_event", lambda **k: None
    )
    monkeypatch.setattr(
        "app.application.services.self_heal.record_audit", lambda **k: None
    )


def _make():
    sessions = FakeRepository()
    steps = FakeRepository()
    runs = FakeRepository()
    return RepairService(sessions, steps=steps, runs=runs), sessions, steps, runs


def _run(runs, *, state="running", bundle="b1"):
    return runs.create(
        {
            "bundle_id": bundle,
            "workspace_id": "ws1",
            "task_key": "T1",
            "title": "Build it",
            "category": "backend",
            "state": state,
        }
    )


# -- start (receive errors) ------------------------------------------------
def test_start_session_records_errors_and_is_receiving() -> None:
    service, sessions, _st, runs = _make()
    run = _run(runs)

    session = service.start_session(
        "w", run["id"], errors="error TS2304: cannot find name", max_iterations=3
    )

    assert session["status"] == RepairSessionStatus.RECEIVING.value
    assert session["errors"].startswith("error TS2304")
    assert session["max_iterations"] == 3
    assert sessions.get(session["id"]) is not None


def test_start_session_missing_run_raises() -> None:
    service, *_ = _make()
    with pytest.raises(NotFoundError):
        service.start_session("w", "nope")


def test_start_session_rejects_terminal_run() -> None:
    service, _s, _st, runs = _make()
    run = _run(runs, state="succeeded")
    with pytest.raises(OrchestrationError):
        service.start_session("w", run["id"])


# -- loop steps ------------------------------------------------------------
def test_compile_fail_sets_status_and_last_error() -> None:
    service, sessions, _st, runs = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])

    service.record_step(
        "w", session["id"], iteration=1, gate="compile", result="fail",
        output="error TS1005", error="compile failed",
    )

    stored = sessions.get(session["id"])
    assert stored["status"] == RepairSessionStatus.COMPILING.value
    assert stored["iterations_count"] == 1
    assert stored["last_error"] == "compile failed"


def test_gates_advance_status_review_test_fix() -> None:
    service, sessions, _st, runs = _make()
    run = _run(runs)
    sid = service.start_session("w", run["id"])["id"]

    for gate, expected in [
        ("review", RepairSessionStatus.REVIEWING.value),
        ("test", RepairSessionStatus.TESTING.value),
        ("fix", RepairSessionStatus.FIXING.value),
    ]:
        service.record_step("w", sid, iteration=1, gate=gate, result="pass")
        assert sessions.get(sid)["status"] == expected


def test_record_step_rejects_unknown_gate() -> None:
    service, _s, _st, runs = _make()
    sid = service.start_session("w", _run(runs)["id"])["id"]
    with pytest.raises(OrchestrationError):
        service.record_step("w", sid, iteration=1, gate="deploy", result="pass")


# -- finish / commit / update status --------------------------------------
def test_pass_commits_and_updates_run_to_succeeded() -> None:
    service, _s, _st, runs = _make()
    run = _run(runs)
    sid = service.start_session("w", run["id"])["id"]

    finished = service.finish_session(
        "w", sid, status="passed", commit_sha="abc123", summary="green"
    )

    assert finished["status"] == RepairSessionStatus.PASSED.value
    assert finished["commit_sha"] == "abc123"
    assert finished["finished_at"] is not None
    assert runs.get(run["id"])["state"] == RunState.SUCCEEDED.value


def test_fail_does_not_change_run_state() -> None:
    service, _s, _st, runs = _make()
    run = _run(runs)
    sid = service.start_session("w", run["id"])["id"]

    service.finish_session("w", sid, status="failed", summary="gave up")

    assert runs.get(run["id"])["state"] == "running"


def test_finish_rejects_invalid_status() -> None:
    service, _s, _st, runs = _make()
    sid = service.start_session("w", _run(runs)["id"])["id"]
    with pytest.raises(OrchestrationError):
        service.finish_session("w", sid, status="fixing")


def test_operations_on_finished_session_rejected() -> None:
    service, _s, _st, runs = _make()
    sid = service.start_session("w", _run(runs)["id"])["id"]
    service.finish_session("w", sid, status="failed")
    with pytest.raises(OrchestrationError):
        service.record_step("w", sid, iteration=1, gate="compile", result="pass")


def test_get_session_returns_steps_in_order() -> None:
    service, _s, _st, runs = _make()
    sid = service.start_session("w", _run(runs)["id"])["id"]
    service.record_step("w", sid, iteration=1, gate="compile", result="fail")
    service.record_step("w", sid, iteration=2, gate="fix", result="pass")
    service.record_step("w", sid, iteration=2, gate="compile", result="pass")

    view = service.get_session("w", sid)

    assert view["session"]["id"] == sid
    assert [s["gate"] for s in view["steps"]] == ["compile", "fix", "compile"]
