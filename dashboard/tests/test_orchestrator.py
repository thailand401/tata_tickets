"""Phase 4 tests: task orchestration — queue, deps, priority, parallel,
retry, timeout, cancel, resume, logs."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from app.application.orchestration.classifier import classify_category, select_agent
from app.application.orchestration.executor import (
    ExecutionError,
    ExecutionResult,
    TaskExecutor,
)
from app.application.services.orchestrator import OrchestratorService
from app.core.exceptions import OrchestrationError
from app.domain.enums import RunState, TaskCategory
from tests.fakes import FakeRepository


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.orchestrator.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.orchestrator.record_event", lambda **k: None)


# -- executors -------------------------------------------------------------
class RecordingExecutor(TaskExecutor):
    def __init__(self) -> None:
        self.order: list[str] = []
        self._lock = threading.Lock()

    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        with self._lock:
            self.order.append(task_run["task_key"])
        return ExecutionResult(output={"ok": True})


class ConcurrencyExecutor(TaskExecutor):
    def __init__(self) -> None:
        self.max_seen = 0
        self._current = 0
        self._lock = threading.Lock()

    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        with self._lock:
            self._current += 1
            self.max_seen = max(self.max_seen, self._current)
        time.sleep(0.05)
        with self._lock:
            self._current -= 1
        return ExecutionResult(output={})


class FlakyExecutor(TaskExecutor):
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ExecutionError("transient")
        return ExecutionResult(output={})


class FailingExecutor(TaskExecutor):
    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        raise ExecutionError("always fails")


class SlowExecutor(TaskExecutor):
    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        time.sleep(5)
        return ExecutionResult(output={})


# -- helpers ---------------------------------------------------------------
def _make(executor=None, agents_rows=None):
    bundles = FakeRepository()
    artifacts = FakeRepository()
    runs = FakeRepository()
    logs = FakeRepository()
    agents = FakeRepository()
    for a in agents_rows or []:
        agents.create(a)
    service = OrchestratorService(
        runs, logs=logs, bundles=bundles, artifacts=artifacts,
        agents=agents, executor=executor,
    )
    return service, bundles, artifacts, runs, logs


def _seed_bundle(bundles, artifacts, tasks) -> str:
    bundle = bundles.create({"title": "B", "status": "ready"})
    artifacts.create(
        {"bundle_id": bundle["id"], "kind": "tasks", "title": "Tasks", "data": {"tasks": tasks}}
    )
    return bundle["id"]


def _task(key, category, depends_on=None, priority="medium"):
    return {
        "key": key,
        "title": f"{category} {key}",
        "category": category,
        "description": "",
        "depends_on": depends_on or [],
        "priority": priority,
    }


# -- classifier ------------------------------------------------------------
def test_classify_category_keywords() -> None:
    assert classify_category("Add a database migration") is TaskCategory.DATABASE
    assert classify_category("Write pytest tests") is TaskCategory.TESTING
    assert classify_category("Build the UI page component") is TaskCategory.FRONTEND
    assert classify_category("Implement the REST endpoint") is TaskCategory.BACKEND
    assert classify_category("Deploy via docker pipeline") is TaskCategory.DEVOPS


def test_select_agent_prefers_capability_match() -> None:
    agents = [
        {"id": "1", "slug": "be", "status": "active", "config": {"categories": ["backend"]}},
        {"id": "2", "slug": "fe", "status": "active", "config": {"categories": ["frontend"]}},
    ]
    chosen = select_agent(TaskCategory.FRONTEND, agents)
    assert chosen["slug"] == "fe"


def test_select_agent_falls_back_to_generalist() -> None:
    agents = [{"id": "1", "slug": "gen", "status": "active", "config": {}}]
    assert select_agent(TaskCategory.DEVOPS, agents)["slug"] == "gen"


# -- enqueue ---------------------------------------------------------------
def test_enqueue_classifies_and_assigns_agents() -> None:
    agents = [{"id": "a", "slug": "any", "status": "active", "config": {}}]
    service, bundles, artifacts, runs, _ = _make(agents_rows=agents)
    bundle_id = _seed_bundle(
        bundles, artifacts, [_task("T1", "database"), _task("T2", "backend", ["T1"])]
    )

    created = service.enqueue("actor", bundle_id)

    assert len(created) == 2
    assert all(r["state"] == RunState.PENDING.value for r in created)
    assert all(r["agent_slug"] == "any" for r in created)


def test_enqueue_twice_is_rejected() -> None:
    service, bundles, artifacts, runs, _ = _make()
    bundle_id = _seed_bundle(bundles, artifacts, [_task("T1", "database")])
    service.enqueue("actor", bundle_id)
    with pytest.raises(OrchestrationError):
        service.enqueue("actor", bundle_id)


# -- run: dependencies + success -------------------------------------------
def test_run_respects_dependency_order() -> None:
    rec = RecordingExecutor()
    service, bundles, artifacts, runs, _ = _make(executor=rec)
    bundle_id = _seed_bundle(
        bundles, artifacts,
        [_task("T1", "database"), _task("T2", "backend", ["T1"]),
         _task("T3", "testing", ["T2"])],
    )
    service.enqueue("actor", bundle_id)

    summary = service.run("actor", bundle_id, max_parallel=4)

    assert summary["counts"].get(RunState.SUCCEEDED.value) == 3
    assert rec.order == ["T1", "T2", "T3"]


# -- run: parallelism ------------------------------------------------------
def test_independent_tasks_run_in_parallel() -> None:
    conc = ConcurrencyExecutor()
    service, bundles, artifacts, runs, _ = _make(executor=conc)
    bundle_id = _seed_bundle(
        bundles, artifacts, [_task("T1", "database"), _task("T2", "database")]
    )
    service.enqueue("actor", bundle_id)

    service.run("actor", bundle_id, max_parallel=2)

    assert conc.max_seen == 2


# -- run: priority ---------------------------------------------------------
def test_priority_orders_ready_tasks() -> None:
    rec = RecordingExecutor()
    service, bundles, artifacts, runs, _ = _make(executor=rec)
    bundle_id = _seed_bundle(
        bundles, artifacts,
        [_task("T1", "database", priority="low"),
         _task("T2", "database", priority="critical")],
    )
    service.enqueue("actor", bundle_id)

    # max_parallel=1 forces sequential execution in priority order.
    service.run("actor", bundle_id, max_parallel=1)
    assert rec.order == ["T2", "T1"]


# -- run: retry ------------------------------------------------------------
def test_retry_until_success() -> None:
    flaky = FlakyExecutor(fail_times=2)
    service, bundles, artifacts, runs, _ = _make(executor=flaky)
    bundle_id = _seed_bundle(bundles, artifacts, [_task("T1", "database")])
    service.enqueue("actor", bundle_id, max_attempts=3)

    summary = service.run("actor", bundle_id)

    assert summary["counts"].get(RunState.SUCCEEDED.value) == 1
    assert flaky.calls == 3


def test_exhausted_retries_marks_dead_and_blocks_dependents() -> None:
    service, bundles, artifacts, runs, _ = _make(executor=FailingExecutor())
    bundle_id = _seed_bundle(
        bundles, artifacts, [_task("T1", "database"), _task("T2", "backend", ["T1"])]
    )
    service.enqueue("actor", bundle_id, max_attempts=2)

    summary = service.run("actor", bundle_id)

    assert summary["counts"].get(RunState.DEAD.value) == 1
    assert summary["counts"].get(RunState.BLOCKED.value) == 1


# -- run: timeout ----------------------------------------------------------
def test_timeout_marks_task_dead() -> None:
    service, bundles, artifacts, runs, _ = _make(executor=SlowExecutor())
    bundle_id = _seed_bundle(bundles, artifacts, [_task("T1", "database")])
    service.enqueue("actor", bundle_id, max_attempts=1, timeout_seconds=1)

    summary = service.run("actor", bundle_id)

    assert summary["counts"].get(RunState.DEAD.value) == 1


# -- cancel ----------------------------------------------------------------
def test_cancel_before_run_blocks_dependents() -> None:
    service, bundles, artifacts, runs, _ = _make(executor=RecordingExecutor())
    bundle_id = _seed_bundle(
        bundles, artifacts, [_task("T1", "database"), _task("T2", "backend", ["T1"])]
    )
    created = service.enqueue("actor", bundle_id)
    t1 = next(r for r in created if r["task_key"] == "T1")

    service.cancel("actor", t1["id"])
    summary = service.run("actor", bundle_id)

    assert summary["counts"].get(RunState.CANCELLED.value) == 1
    assert summary["counts"].get(RunState.BLOCKED.value) == 1


def test_cancel_terminal_task_rejected() -> None:
    service, bundles, artifacts, runs, _ = _make(executor=RecordingExecutor())
    bundle_id = _seed_bundle(bundles, artifacts, [_task("T1", "database")])
    service.enqueue("actor", bundle_id)
    service.run("actor", bundle_id)
    run = runs.list(filters={"bundle_id": bundle_id})[0]
    with pytest.raises(OrchestrationError):
        service.cancel("actor", run["id"])


# -- resume ----------------------------------------------------------------
def test_resume_reruns_failed_after_fix() -> None:
    # First run fails everything; a fresh service with a good executor resumes.
    bundles = FakeRepository()
    artifacts = FakeRepository()
    runs = FakeRepository()
    logs = FakeRepository()
    bundle_id = _seed_bundle(
        bundles, artifacts, [_task("T1", "database"), _task("T2", "backend", ["T1"])]
    )

    failing = OrchestratorService(
        runs, logs=logs, bundles=bundles, artifacts=artifacts,
        agents=FakeRepository(), executor=FailingExecutor(),
    )
    failing.enqueue("actor", bundle_id, max_attempts=1)
    failing.run("actor", bundle_id)

    good = OrchestratorService(
        runs, logs=logs, bundles=bundles, artifacts=artifacts,
        agents=FakeRepository(), executor=RecordingExecutor(),
    )
    summary = good.resume("actor", bundle_id)

    assert summary["counts"].get(RunState.SUCCEEDED.value) == 2


# -- logs ------------------------------------------------------------------
def test_run_writes_logs_per_task() -> None:
    service, bundles, artifacts, runs, logs = _make(executor=RecordingExecutor())
    bundle_id = _seed_bundle(bundles, artifacts, [_task("T1", "database")])
    service.enqueue("actor", bundle_id)
    service.run("actor", bundle_id)

    run = runs.list(filters={"bundle_id": bundle_id})[0]
    entries = service.run_logs("actor", run["id"])
    kinds = {e["kind"] for e in entries}
    assert "state" in kinds
    assert any("succeeded" in e["message"] for e in entries)
