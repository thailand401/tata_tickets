"""Agent bridge service (Phase 5): pull tasks & push results.

This is the server side of the VS Code extension bridge. An external worker
(the extension) authenticates, *pulls* the next ready task, and *pushes* back
progress, logs, commits, reviews, errors and completion. The bridge does **not**
manage tickets — it only moves a task run through its lifecycle and records the
worker's updates as logs/events for realtime sync.
"""

from __future__ import annotations

from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import AuditAction, RunState, TicketPriority
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

_TERMINAL = {RunState.SUCCEEDED.value, RunState.CANCELLED.value, RunState.DEAD.value}
_PRIORITY_RANK = {
    TicketPriority.CRITICAL.value: 3,
    TicketPriority.HIGH.value: 2,
    TicketPriority.MEDIUM.value: 1,
    TicketPriority.LOW.value: 0,
}


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


class AgentBridgeService:
    def __init__(
        self,
        runs: Repository | None = None,
        *,
        logs: Repository | None = None,
    ) -> None:
        self._runs = runs or _repo("task_runs")
        self._logs = logs or _repo("task_logs")

    # =====================================================================
    # Pull: claim the next ready task for this worker
    # =====================================================================
    def pull_next(
        self,
        actor_id: str,
        *,
        categories: list[str] | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any] | None:
        rbac.require(actor_id, "agent:bridge", workspace_id)
        filters: dict[str, Any] = {"state": RunState.PENDING.value}
        if workspace_id:
            filters["workspace_id"] = workspace_id
        candidates = self._runs.list(filters=filters, limit=500)
        candidates.sort(
            key=lambda r: _PRIORITY_RANK.get(r.get("priority"), 1), reverse=True
        )
        wanted = {c.lower() for c in categories} if categories else None

        for run in candidates:
            if wanted and (run.get("category") or "").lower() not in wanted:
                continue
            if not self._deps_satisfied(run):
                continue
            claimed = self._runs.update(
                run["id"],
                {
                    "state": RunState.RUNNING.value,
                    "claimed_by": actor_id,
                    "attempts": int(run.get("attempts", 0)) + 1,
                },
            )
            self._log(run["id"], "state", "pulled by worker", level="info")
            record_event(
                event_type="agent.pulled",
                source="vscode-bridge",
                workspace_id=run.get("workspace_id"),
                payload={"run_id": run["id"], "task_key": run.get("task_key")},
            )
            return claimed
        return None

    # =====================================================================
    # Push: worker updates (progress / log / commit / review / error / done)
    # =====================================================================
    def push_progress(
        self, actor_id: str, run_id: str, *, percent: int, message: str, data: dict
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        self._log(
            run_id, "progress", message or f"{percent}%", level="info",
            data={"percent": percent, **(data or {})},
        )
        self._event("agent.progress", run, {"percent": percent})
        return run

    def push_log(
        self, actor_id: str, run_id: str, *, level: str, message: str, data: dict
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        self._log(run_id, "log", message, level=level, data=data or {})
        return run

    def push_commit(
        self, actor_id: str, run_id: str, *, sha: str, message: str,
        branch: str | None, url: str | None,
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        self._log(
            run_id, "commit", message or sha, level="info",
            data={"sha": sha, "branch": branch, "url": url},
        )
        self._event("agent.commit", run, {"sha": sha})
        return run

    def push_review(
        self, actor_id: str, run_id: str, *, status: str, summary: str, data: dict
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        self._log(
            run_id, "review", summary or status, level="info",
            data={"status": status, **(data or {})},
        )
        self._event("agent.review", run, {"status": status})
        return run

    def push_error(
        self, actor_id: str, run_id: str, *, message: str, retry: bool, data: dict
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        self._log(run_id, "error", message, level="error", data=data or {})
        attempts = int(run.get("attempts", 0))
        max_attempts = int(run.get("max_attempts", 3))
        if retry and attempts < max_attempts:
            new_state = RunState.PENDING  # re-pullable for another attempt
        else:
            new_state = RunState.DEAD
        updated = self._runs.update(
            run_id, {"state": new_state.value, "last_error": message, "claimed_by": None}
        )
        self._event("agent.error", run, {"retry": retry, "state": new_state.value})
        return updated

    def push_complete(
        self, actor_id: str, run_id: str, *, summary: str, result: dict
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        updated = self._runs.update(
            run_id,
            {"state": RunState.SUCCEEDED.value, "result": result or {}, "last_error": None},
        )
        self._log(run_id, "state", summary or "completed", level="info")
        record_audit(
            actor_id=actor_id,
            action=AuditAction.DISPATCH.value,
            entity_type="task_run",
            entity_id=run_id,
            after={"state": RunState.SUCCEEDED.value},
        )
        self._event("agent.completed", run, {"task_key": run.get("task_key")})
        return updated

    # =====================================================================
    # Realtime sync: read a run + its recent logs
    # =====================================================================
    def sync(self, actor_id: str, run_id: str, *, log_limit: int = 50) -> dict[str, Any]:
        rbac.require(actor_id, "agent:bridge")
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        logs = self._logs.list(
            filters={"run_id": run_id}, order_by="created_at", descending=True,
            limit=log_limit,
        )
        return {"run": run, "logs": logs}

    # =====================================================================
    # Internals
    # =====================================================================
    def _active_run(self, actor_id: str, run_id: str) -> dict[str, Any]:
        rbac.require(actor_id, "agent:bridge")
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        if run.get("state") in _TERMINAL:
            raise OrchestrationError(f"task run is {run['state']} (terminal)")
        return run

    def _deps_satisfied(self, run: dict[str, Any]) -> bool:
        deps = run.get("depends_on") or []
        if not deps:
            return True
        siblings = self._runs.list(filters={"bundle_id": run["bundle_id"]}, limit=500)
        by_key = {s["task_key"]: s for s in siblings}
        return all(
            by_key.get(d, {}).get("state") == RunState.SUCCEEDED.value for d in deps
        )

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

    def _event(self, event_type: str, run: dict[str, Any], payload: dict[str, Any]) -> None:
        record_event(
            event_type=event_type,
            source="vscode-bridge",
            workspace_id=run.get("workspace_id"),
            payload={"run_id": run.get("id"), **payload},
        )
