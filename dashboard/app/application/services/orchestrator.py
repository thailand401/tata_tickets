"""Orchestrator service (Phase 4): schedule and execute OpenSpec tasks.

Reads the structured task DAG from an OpenSpec ``tasks`` artifact and turns it
into orchestrated runs. Provides the full set of cross-cutting controls:

- **Queue**      — tasks become ``queued`` then ``running`` through a scheduler.
- **Retry**      — failed attempts retry up to ``max_attempts``.
- **Timeout**    — each attempt is bounded by ``timeout_seconds``.
- **Priority**   — ready tasks are ordered by priority.
- **Dependency** — a task only runs once every dependency has succeeded.
- **Parallel**   — independent ready tasks run concurrently (``max_parallel``).
- **Resume**     — re-running picks up unfinished tasks without redoing work.
- **Cancel**     — a task (and its blocked dependents) can be cancelled.
- **Log**        — every state change / attempt is logged and event-recorded.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from app.application.orchestration.classifier import classify_category, select_agent
from app.application.orchestration.executor import (
    ExecutionError,
    ExecutionTimeout,
    StubTaskExecutor,
    TaskExecutor,
)
from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.core.exceptions import NotFoundError, OrchestrationError, ValidationError
from app.domain.enums import AuditAction, RunState, TaskCategory, TicketPriority
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

# States from which no further scheduling happens within a run.
_TERMINAL = {RunState.SUCCEEDED.value, RunState.CANCELLED.value, RunState.DEAD.value}
# A dependency in one of these states can never succeed -> blocks dependents.
_DEP_FAILED = {RunState.DEAD.value, RunState.CANCELLED.value, RunState.FAILED.value}

_PRIORITY_RANK = {
    TicketPriority.CRITICAL.value: 3,
    TicketPriority.HIGH.value: 2,
    TicketPriority.MEDIUM.value: 1,
    TicketPriority.LOW.value: 0,
}


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


class OrchestratorService:
    resource = "orchestration"

    def __init__(
        self,
        runs: Repository | None = None,
        *,
        logs: Repository | None = None,
        bundles: Repository | None = None,
        artifacts: Repository | None = None,
        agents: Repository | None = None,
        executor: TaskExecutor | None = None,
    ) -> None:
        self._runs = runs or _repo("task_runs")
        self._logs = logs or _repo("task_logs")
        self._bundles = bundles or _repo("spec_bundles")
        self._artifacts = artifacts or _repo("spec_artifacts")
        self._agents = agents or _repo("agents")
        self._executor = executor or StubTaskExecutor()

    # =====================================================================
    # Enqueue: OpenSpec tasks artifact -> task_runs (classified + assigned)
    # =====================================================================
    def enqueue(
        self,
        actor_id: str,
        bundle_id: str,
        *,
        max_attempts: int = 3,
        timeout_seconds: int = 300,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rbac.require(actor_id, "orchestration:write", workspace_id)
        bundle = self._bundles.get(bundle_id)
        if not bundle:
            raise NotFoundError("spec bundle not found")

        existing = self._runs.list(filters={"bundle_id": bundle_id}, limit=500)
        if existing:
            raise OrchestrationError("bundle already enqueued; use resume")

        artifact = self._artifacts.find_one({"bundle_id": bundle_id, "kind": "tasks"})
        tasks = ((artifact or {}).get("data") or {}).get("tasks") or []
        if not tasks:
            raise ValidationError("bundle has no tasks artifact to orchestrate")

        agents = self._agents.list(filters={"status": "active"}, limit=200)
        ws = workspace_id or bundle.get("workspace_id")
        created: list[dict[str, Any]] = []
        for task in tasks:
            category = classify_category(
                f"{task.get('title', '')} {task.get('description', '')} "
                f"{task.get('category', '')}",
                default=TaskCategory(task.get("category", TaskCategory.BACKEND.value)),
            )
            agent = select_agent(category, agents)
            run = self._runs.create(
                {
                    "bundle_id": bundle_id,
                    "workspace_id": ws,
                    "task_key": task.get("key"),
                    "title": task.get("title", ""),
                    "category": category.value,
                    "state": RunState.PENDING.value,
                    "priority": task.get("priority", TicketPriority.MEDIUM.value),
                    "depends_on": task.get("depends_on", []),
                    "agent_id": (agent or {}).get("id"),
                    "agent_slug": (agent or {}).get("slug"),
                    "attempts": 0,
                    "max_attempts": max_attempts,
                    "timeout_seconds": timeout_seconds,
                    "payload": task,
                }
            )
            created.append(run)
            self._log(run["id"], "state", f"enqueued -> {category.value}", level="info")

        record_audit(
            actor_id=actor_id,
            action=AuditAction.ENQUEUE.value,
            entity_type="spec_bundle",
            entity_id=bundle_id,
            after={"count": len(created)},
        )
        record_event(
            event_type="orchestration.enqueued",
            source="dashboard",
            workspace_id=ws,
            payload={"bundle_id": bundle_id, "tasks": len(created)},
        )
        return created

    # =====================================================================
    # Run / resume: dependency-aware, prioritized, parallel scheduler
    # =====================================================================
    def run(
        self,
        actor_id: str,
        bundle_id: str,
        *,
        max_parallel: int = 4,
        retry_delay: float = 0.0,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, "orchestration:execute", workspace_id)
        return self._schedule(bundle_id, max_parallel=max_parallel, retry_delay=retry_delay)

    def resume(
        self,
        actor_id: str,
        bundle_id: str,
        *,
        max_parallel: int = 4,
        retry_delay: float = 0.0,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, "orchestration:execute", workspace_id)
        # Reset transient non-terminal states so they become schedulable again.
        for run in self._runs.list(filters={"bundle_id": bundle_id}, limit=500):
            if run.get("state") in {RunState.BLOCKED.value, RunState.QUEUED.value,
                                    RunState.RETRYING.value, RunState.RUNNING.value,
                                    RunState.FAILED.value, RunState.TIMED_OUT.value,
                                    RunState.DEAD.value}:
                self._set_state(run["id"], RunState.PENDING)
        record_audit(
            actor_id=actor_id,
            action=AuditAction.RESUME.value,
            entity_type="spec_bundle",
            entity_id=bundle_id,
        )
        return self._schedule(bundle_id, max_parallel=max_parallel, retry_delay=retry_delay)

    def _schedule(
        self, bundle_id: str, *, max_parallel: int, retry_delay: float
    ) -> dict[str, Any]:
        runs = self._runs.list(filters={"bundle_id": bundle_id}, limit=500)
        if not runs:
            raise NotFoundError("no task runs for bundle; enqueue first")
        by_key: dict[str, dict[str, Any]] = {r["task_key"]: r for r in runs}

        # Iterate until no further progress is possible.
        while True:
            ready: list[dict[str, Any]] = []
            waiting = False
            for run in by_key.values():
                if run["state"] in _TERMINAL or run["state"] == RunState.BLOCKED.value:
                    continue
                deps = run.get("depends_on") or []
                dep_states = [by_key.get(d, {}).get("state") for d in deps]
                if any(s in _DEP_FAILED for s in dep_states):
                    self._set_state(run["id"], RunState.BLOCKED, by=run)
                    self._log(run["id"], "state", "blocked: dependency failed", level="warn")
                    continue
                if all(s == RunState.SUCCEEDED.value for s in dep_states):
                    ready.append(run)
                else:
                    waiting = True

            if not ready:
                if waiting:
                    # Nothing runnable but tasks still waiting -> circular/blocked.
                    for run in by_key.values():
                        if run["state"] not in _TERMINAL and run["state"] != RunState.BLOCKED.value:
                            self._set_state(run["id"], RunState.BLOCKED, by=run)
                break

            ready.sort(key=lambda r: _PRIORITY_RANK.get(r.get("priority"), 1), reverse=True)
            batch = ready[:max_parallel]
            for run in batch:
                self._set_state(run["id"], RunState.QUEUED, by=run)

            workers = max(1, min(max_parallel, len(batch)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(self._execute_one, run, retry_delay): run["task_key"]
                    for run in batch
                }
                for future in futures:
                    final = future.result()
                    by_key[final["task_key"]] = final

        return self._summary(bundle_id)

    # -- single task execution with retry + timeout ------------------------
    def _execute_one(self, run: dict[str, Any], retry_delay: float) -> dict[str, Any]:
        run_id = run["id"]
        max_attempts = int(run.get("max_attempts", 3))
        timeout = int(run.get("timeout_seconds", 300))

        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            self._runs.update(run_id, {"attempts": attempt})
            state = RunState.RUNNING if attempt == 1 else RunState.RETRYING
            self._set_state(run_id, state, by=run)
            self._log(run_id, "state", f"attempt {attempt}/{max_attempts}", level="info")
            try:
                result = self._run_with_timeout(run, timeout)
                final = self._set_state(
                    run_id, RunState.SUCCEEDED, by=run,
                    extra={"result": result.output, "last_error": None},
                )
                self._log(run_id, "state", "succeeded", level="info")
                return final
            except FuturesTimeout:
                last_error = f"timed out after {timeout}s"
                self._set_state(run_id, RunState.TIMED_OUT, by=run,
                                extra={"last_error": last_error})
                self._log(run_id, "error", last_error, level="error")
            except (ExecutionError, ExecutionTimeout) as exc:
                last_error = str(exc)
                self._log(run_id, "error", last_error, level="error")
            if retry_delay and attempt < max_attempts:
                import time

                time.sleep(retry_delay)

        final = self._set_state(
            run_id, RunState.DEAD, by=run, extra={"last_error": last_error}
        )
        self._log(run_id, "state", f"dead after {max_attempts} attempts", level="error")
        return final

    def _run_with_timeout(self, run: dict[str, Any], timeout: int):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._executor.execute, run)
            return future.result(timeout=timeout)

    # =====================================================================
    # Cancel
    # =====================================================================
    def cancel(
        self, actor_id: str, run_id: str, *, workspace_id: str | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, "orchestration:execute", workspace_id)
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        if run.get("state") in _TERMINAL:
            raise OrchestrationError(f"cannot cancel a {run['state']} task")
        updated = self._set_state(run_id, RunState.CANCELLED, by=run)
        self._log(run_id, "state", "cancelled by user", level="warn")
        record_audit(
            actor_id=actor_id,
            action=AuditAction.CANCEL.value,
            entity_type="task_run",
            entity_id=run_id,
        )
        return updated

    # =====================================================================
    # Reads
    # =====================================================================
    def list_runs(self, actor_id: str, bundle_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "orchestration:read")
        return self._runs.list(
            filters={"bundle_id": bundle_id}, order_by="created_at", limit=500
        )

    def get_run(self, actor_id: str, run_id: str) -> dict[str, Any]:
        rbac.require(actor_id, "orchestration:read")
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        return run

    def run_logs(self, actor_id: str, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rbac.require(actor_id, "orchestration:read")
        return self._logs.list(
            filters={"run_id": run_id}, order_by="created_at", limit=limit
        )

    # =====================================================================
    # Internals
    # =====================================================================
    def _set_state(
        self,
        run_id: str,
        state: RunState,
        *,
        by: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"state": state.value}
        if extra:
            data.update(extra)
        updated = self._runs.update(run_id, data)
        if by is not None:
            by.update(updated)
        return updated

    def _log(
        self, run_id: str, kind: str, message: str, *, level: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        self._logs.create(
            {
                "run_id": run_id,
                "level": level,
                "kind": kind,
                "message": message,
                "data": data or {},
            }
        )

    def _summary(self, bundle_id: str) -> dict[str, Any]:
        runs = self._runs.list(filters={"bundle_id": bundle_id}, limit=500)
        counts: dict[str, int] = {}
        for run in runs:
            counts[run["state"]] = counts.get(run["state"], 0) + 1
        return {
            "bundle_id": bundle_id,
            "total": len(runs),
            "counts": counts,
            "runs": runs,
        }
