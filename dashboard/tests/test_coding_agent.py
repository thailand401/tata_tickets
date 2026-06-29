"""Phase 6 tests: coding agent — context + session/attempt persistence."""

from __future__ import annotations

import pytest

from app.application.services.coding_agent import CodingAgentService
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import AgentSessionStatus
from tests.fakes import FakeRepository


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.application.services.coding_agent.record_event", lambda **k: None
    )


def _make():
    sessions = FakeRepository()
    attempts = FakeRepository()
    runs = FakeRepository()
    artifacts = FakeRepository()
    service = CodingAgentService(
        sessions, attempts=attempts, runs=runs, artifacts=artifacts
    )
    return service, sessions, attempts, runs, artifacts


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


# -- context ---------------------------------------------------------------
def test_get_context_returns_run_and_documents() -> None:
    service, _s, _a, runs, artifacts = _make()
    run = _run(runs)
    artifacts.create(
        {"bundle_id": "b1", "kind": "architecture", "title": "Arch",
         "content": "# Arch", "data": {}}
    )
    artifacts.create(
        {"bundle_id": "b1", "kind": "tasks", "title": "Tasks",
         "content": "# Tasks", "data": {"tasks": [1]}}
    )

    ctx = service.get_context("w", run["id"])

    assert ctx["run"]["id"] == run["id"]
    assert ctx["documents"]["architecture"]["content"] == "# Arch"
    assert ctx["documents"]["tasks"]["data"] == {"tasks": [1]}


def test_get_context_missing_run_raises() -> None:
    service, *_ = _make()
    with pytest.raises(NotFoundError):
        service.get_context("w", "nope")


# -- session lifecycle -----------------------------------------------------
def test_start_session_creates_planning_session() -> None:
    service, sessions, _a, runs, _ = _make()
    run = _run(runs)

    session = service.start_session("w", run["id"])

    assert session["status"] == AgentSessionStatus.PLANNING.value
    assert session["run_id"] == run["id"]
    assert sessions.get(session["id"]) is not None


def test_start_session_rejects_terminal_run() -> None:
    service, _s, _a, runs, _ = _make()
    run = _run(runs, state="succeeded")
    with pytest.raises(OrchestrationError):
        service.start_session("w", run["id"])


def test_record_plan_moves_to_coding_and_logs_attempt() -> None:
    service, _s, attempts, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])

    updated = service.record_plan("w", session["id"], plan={"steps": ["a", "b"]})

    assert updated["status"] == AgentSessionStatus.CODING.value
    assert updated["plan"] == {"steps": ["a", "b"]}
    plan_attempts = attempts.list(filters={"session_id": session["id"]})
    assert any(a["phase"] == "plan" for a in plan_attempts)


def test_record_attempt_increments_count_and_sets_status() -> None:
    service, sessions, attempts, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])

    service.record_attempt(
        "w", session["id"], iteration=1, phase="compile", status="fail",
        compile_output="error TS1005", error="compile failed",
    )

    stored = sessions.get(session["id"])
    assert stored["attempts_count"] == 1
    assert stored["status"] == AgentSessionStatus.COMPILING.value
    assert stored["last_error"] == "compile failed"
    rows = attempts.list(filters={"session_id": session["id"]})
    assert rows[-1]["compile_output"] == "error TS1005"


def test_fix_phase_sets_fixing_status() -> None:
    service, sessions, _a, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])

    service.record_attempt(
        "w", session["id"], iteration=2, phase="fix", status="pass"
    )

    assert sessions.get(session["id"])["status"] == AgentSessionStatus.FIXING.value


def test_finish_session_succeeded_is_terminal() -> None:
    service, sessions, _a, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])

    finished = service.finish_session(
        "w", session["id"], status="succeeded", summary="committed abc123"
    )

    assert finished["status"] == AgentSessionStatus.SUCCEEDED.value
    assert finished["summary"] == "committed abc123"
    assert finished["finished_at"] is not None


def test_finish_session_rejects_invalid_status() -> None:
    service, _s, _a, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])
    with pytest.raises(OrchestrationError):
        service.finish_session("w", session["id"], status="coding")


def test_operations_on_finished_session_rejected() -> None:
    service, _s, _a, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])
    service.finish_session("w", session["id"], status="failed", summary="gave up")

    with pytest.raises(OrchestrationError):
        service.record_attempt(
            "w", session["id"], iteration=1, phase="code", status="pass"
        )


def test_get_session_returns_attempts_in_order() -> None:
    service, _s, _a, runs, _ = _make()
    run = _run(runs)
    session = service.start_session("w", run["id"])
    service.record_plan("w", session["id"], plan={})
    service.record_attempt(
        "w", session["id"], iteration=1, phase="compile", status="pass"
    )

    view = service.get_session("w", session["id"])

    assert view["session"]["id"] == session["id"]
    phases = [a["phase"] for a in view["attempts"]]
    assert phases == ["plan", "compile"]
