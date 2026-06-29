"""Self-healing service (Phase 9): receive errors -> fix loop -> pass -> commit.

Phase 6 takes a task from plan to a committed first draft. Phase 9 closes the
loop: when that draft (or a later push) fails, the agent feeds the errors back
in and drives one bounded loop:

    Receive errors -> Compile -> Review -> Test -> AI fix -> Loop -> Pass ->
    Commit -> Update run state.

The loop itself runs inside the VS Code extension (it owns the compiler, the
test runner and git). This server-side service is its *memory*: it records the
session, every gate step and, on success, flips the task run to SUCCEEDED so the
dashboard reflects the final state. It records but never executes anything.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import AuditAction, RepairSessionStatus, RunState
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

_TERMINAL_RUN = {RunState.SUCCEEDED.value, RunState.CANCELLED.value, RunState.DEAD.value}
_FINAL_SESSION = {RepairSessionStatus.PASSED.value, RepairSessionStatus.FAILED.value}


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RepairService:
    """Persist the self-healing loop and update the run when it passes."""

    def __init__(
        self,
        sessions: Repository | None = None,
        *,
        steps: Repository | None = None,
        runs: Repository | None = None,
    ) -> None:
        self._sessions = sessions or _repo("repair_sessions")
        self._steps = steps or _repo("repair_steps")
        self._runs = runs or _repo("task_runs")

    # =====================================================================
    # Receive errors: open a self-healing session for a (running) task run
    # =====================================================================
    def start_session(
        self,
        actor_id: str,
        run_id: str,
        *,
        errors: str = "",
        max_iterations: int = 5,
    ) -> dict[str, Any]:
        run = self._active_run(actor_id, run_id)
        session = self._sessions.create(
            {
                "run_id": run_id,
                "bundle_id": run.get("bundle_id"),
                "workspace_id": run.get("workspace_id"),
                "status": RepairSessionStatus.RECEIVING.value,
                "errors": errors or "",
                "summary": "",
                "iterations_count": 0,
                "max_iterations": max_iterations,
                "created_by": actor_id,
                "started_at": _now(),
            }
        )
        self._event("repair.session.started", run, {"session_id": session["id"]})
        return session

    # =====================================================================
    # Loop: one gate (compile/review/test/fix/commit), pass or fail
    # =====================================================================
    def record_step(
        self,
        actor_id: str,
        session_id: str,
        *,
        iteration: int,
        gate: str,
        result: str,
        output: str = "",
        files: list[dict] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        session = self._open_session(actor_id, session_id)
        if gate not in _GATE_STATUS:
            raise OrchestrationError(f"gate must be one of {sorted(_GATE_STATUS)}")
        step = self._steps.create(
            {
                "session_id": session_id,
                "iteration": iteration,
                "gate": gate,
                "result": result,
                "output": output or "",
                "files": files or [],
                "error": error,
            }
        )
        self._sessions.update(
            session_id,
            {
                "status": _GATE_STATUS[gate],
                "iterations_count": int(session.get("iterations_count", 0)) + 1,
                "last_error": error if result == "fail" else session.get("last_error"),
            },
        )
        return step

    # =====================================================================
    # Pass + commit + update run state, or fail (both terminal)
    # =====================================================================
    def finish_session(
        self,
        actor_id: str,
        session_id: str,
        *,
        status: str,
        commit_sha: str | None = None,
        summary: str = "",
    ) -> dict[str, Any]:
        session = self._open_session(actor_id, session_id)
        if status not in _FINAL_SESSION:
            raise OrchestrationError(
                f"finish status must be one of {sorted(_FINAL_SESSION)}"
            )
        updated = self._sessions.update(
            session_id,
            {
                "status": status,
                "commit_sha": commit_sha,
                "summary": summary or "",
                "finished_at": _now(),
            },
        )
        run = self._runs.get(session.get("run_id"))
        # On pass: flip the run to SUCCEEDED — the dashboard sees it as done.
        if status == RepairSessionStatus.PASSED.value and run:
            self._runs.update(run["id"], {"state": RunState.SUCCEEDED.value})
            record_audit(
                actor_id=actor_id,
                action=AuditAction.UPDATE.value,
                entity_type="task_run",
                entity_id=run["id"],
            )
        self._event(
            "repair.session.finished",
            run or {"workspace_id": session.get("workspace_id")},
            {"session_id": session_id, "status": status, "commit_sha": commit_sha},
        )
        return updated

    def get_session(self, actor_id: str, session_id: str) -> dict[str, Any]:
        """Return a session plus its steps (read model for the dashboard)."""
        rbac.require(actor_id, "agent:bridge")
        session = self._sessions.get(session_id)
        if not session:
            raise NotFoundError("repair session not found")
        steps = self._steps.list(
            filters={"session_id": session_id}, order_by="created_at", limit=200
        )
        return {"session": session, "steps": steps}

    # =====================================================================
    # Internals
    # =====================================================================
    def _active_run(self, actor_id: str, run_id: str) -> dict[str, Any]:
        rbac.require(actor_id, "agent:bridge")
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        if run.get("state") in _TERMINAL_RUN:
            raise OrchestrationError(f"task run is {run['state']} (terminal)")
        return run

    def _open_session(self, actor_id: str, session_id: str) -> dict[str, Any]:
        rbac.require(actor_id, "agent:bridge")
        session = self._sessions.get(session_id)
        if not session:
            raise NotFoundError("repair session not found")
        if session.get("status") in _FINAL_SESSION:
            raise OrchestrationError(f"repair session is {session['status']} (terminal)")
        return session

    def _event(
        self, event_type: str, run: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        record_event(
            event_type=event_type,
            source="self-heal",
            workspace_id=run.get("workspace_id"),
            payload={"run_id": run.get("id"), **payload},
        )


#: Map the gate just recorded to the session status it implies.
_GATE_STATUS: dict[str, str] = {
    "compile": RepairSessionStatus.COMPILING.value,
    "review": RepairSessionStatus.REVIEWING.value,
    "test": RepairSessionStatus.TESTING.value,
    "fix": RepairSessionStatus.FIXING.value,
    "commit": RepairSessionStatus.COMMITTING.value,
}
