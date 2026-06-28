"""Phase 5 tests: agent bridge — pull a ready task and push results/sync."""

from __future__ import annotations

import pytest

from app.application.services.agent_bridge import AgentBridgeService
from app.core.exceptions import OrchestrationError
from app.domain.enums import RunState
from tests.fakes import FakeRepository


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.agent_bridge.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.agent_bridge.record_event", lambda **k: None)


def _make():
    runs = FakeRepository()
    logs = FakeRepository()
    return AgentBridgeService(runs, logs=logs), runs, logs


def _run(runs, key, category, state="pending", depends_on=None, priority="medium", bundle="b1"):
    return runs.create(
        {
            "bundle_id": bundle,
            "task_key": key,
            "title": key,
            "category": category,
            "state": state,
            "priority": priority,
            "depends_on": depends_on or [],
            "attempts": 0,
            "max_attempts": 3,
        }
    )


# -- pull ------------------------------------------------------------------
def test_pull_claims_ready_task_and_marks_running() -> None:
    service, runs, _ = _make()
    _run(runs, "T1", "backend")

    claimed = service.pull_next("worker-1")

    assert claimed["state"] == RunState.RUNNING.value
    assert claimed["claimed_by"] == "worker-1"
    assert claimed["attempts"] == 1


def test_pull_skips_tasks_with_unmet_dependencies() -> None:
    service, runs, _ = _make()
    _run(runs, "T1", "database", state="running")
    _run(runs, "T2", "backend", depends_on=["T1"])

    assert service.pull_next("worker-1") is None


def test_pull_returns_task_when_dependency_succeeded() -> None:
    service, runs, _ = _make()
    _run(runs, "T1", "database", state="succeeded")
    _run(runs, "T2", "backend", depends_on=["T1"])

    claimed = service.pull_next("worker-1")
    assert claimed["task_key"] == "T2"


def test_pull_respects_priority() -> None:
    service, runs, _ = _make()
    _run(runs, "T1", "backend", priority="low")
    _run(runs, "T2", "backend", priority="critical")

    claimed = service.pull_next("worker-1")
    assert claimed["task_key"] == "T2"


def test_pull_filters_by_category() -> None:
    service, runs, _ = _make()
    _run(runs, "T1", "backend")
    _run(runs, "T2", "frontend")

    claimed = service.pull_next("worker-1", categories=["frontend"])
    assert claimed["task_key"] == "T2"


def test_pull_returns_none_when_nothing_ready() -> None:
    service, runs, _ = _make()
    _run(runs, "T1", "backend", state="succeeded")
    assert service.pull_next("worker-1") is None


# -- push ------------------------------------------------------------------
def test_push_progress_and_log_write_entries() -> None:
    service, runs, logs = _make()
    run = _run(runs, "T1", "backend", state="running")

    service.push_progress("w", run["id"], percent=40, message="halfway", data={})
    service.push_log("w", run["id"], level="info", message="building", data={})

    entries = logs.list(filters={"run_id": run["id"]})
    kinds = {e["kind"] for e in entries}
    assert {"progress", "log"} <= kinds


def test_push_commit_and_review() -> None:
    service, runs, logs = _make()
    run = _run(runs, "T1", "backend", state="running")

    service.push_commit("w", run["id"], sha="abc123", message="feat", branch="main", url=None)
    service.push_review("w", run["id"], status="approved", summary="LGTM", data={})

    entries = logs.list(filters={"run_id": run["id"]})
    kinds = {e["kind"] for e in entries}
    assert {"commit", "review"} <= kinds


def test_push_error_with_retry_requeues() -> None:
    service, runs, _ = _make()
    run = _run(runs, "T1", "backend", state="running")
    runs.update(run["id"], {"attempts": 1})

    updated = service.push_error("w", run["id"], message="boom", retry=True, data={})

    assert updated["state"] == RunState.PENDING.value
    assert updated["claimed_by"] is None


def test_push_error_without_retry_marks_dead() -> None:
    service, runs, _ = _make()
    run = _run(runs, "T1", "backend", state="running")

    updated = service.push_error("w", run["id"], message="fatal", retry=False, data={})
    assert updated["state"] == RunState.DEAD.value


def test_push_complete_marks_succeeded() -> None:
    service, runs, _ = _make()
    run = _run(runs, "T1", "backend", state="running")

    updated = service.push_complete("w", run["id"], summary="done", result={"files": 3})

    assert updated["state"] == RunState.SUCCEEDED.value
    assert updated["result"] == {"files": 3}


def test_push_to_terminal_task_rejected() -> None:
    service, runs, _ = _make()
    run = _run(runs, "T1", "backend", state="succeeded")
    with pytest.raises(OrchestrationError):
        service.push_log("w", run["id"], level="info", message="x", data={})


# -- sync ------------------------------------------------------------------
def test_sync_returns_run_and_logs() -> None:
    service, runs, _ = _make()
    run = _run(runs, "T1", "backend", state="running")
    service.push_log("w", run["id"], level="info", message="hello", data={})

    result = service.sync("w", run["id"])
    assert result["run"]["id"] == run["id"]
    assert result["logs"]
