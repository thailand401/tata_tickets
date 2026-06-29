"""Coding agent service (Phase 6): persist the autonomous agent loop.

The agent itself runs inside the VS Code extension. It pulls a task (Phase 5),
reads context (project + coding standard + OpenSpec docs), plans, generates
code, compiles, fixes in a bounded loop and commits — without a review step.

This server-side service is the agent's *memory*: it serves the task context
(the OpenSpec artifacts of the task's bundle) and records each agent session
and the attempts within it, so the dashboard can show exactly what the agent
did. State transitions of the task run itself stay in ``AgentBridgeService``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_event
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import AgentSessionStatus, RunState
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

_TERMINAL = {RunState.SUCCEEDED.value, RunState.CANCELLED.value, RunState.DEAD.value}
_FINAL_SESSION = {AgentSessionStatus.SUCCEEDED.value, AgentSessionStatus.FAILED.value}


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CodingAgentService:
    def __init__(
        self,
        sessions: Repository | None = None,
        *,
        attempts: Repository | None = None,
        runs: Repository | None = None,
        artifacts: Repository | None = None,
    ) -> None:
        self._sessions = sessions or _repo("agent_sessions")
        self._attempts = attempts or _repo("agent_attempts")
        self._runs = runs or _repo("task_runs")
        self._artifacts = artifacts or _repo("spec_artifacts")

    # =====================================================================
    # Context: everything the agent needs to start coding
    # =====================================================================
    def get_context(self, actor_id: str, run_id: str) -> dict[str, Any]:
        """Return the task run plus the OpenSpec documents of its bundle."""
        rbac.require(actor_id, "agent:bridge")
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        artifacts = self._artifacts.list(
            filters={"bundle_id": run.get("bundle_id")}, limit=50
        )
        documents = {
            a.get("kind"): {
                "title": a.get("title"),
                "content": a.get("content", ""),
                "data": a.get("data", {}),
            }
            for a in artifacts
        }
        return {"run": run, "documents": documents}

    # =====================================================================
    # Session lifecycle: start -> plan -> attempt(s) -> finish
    # =====================================================================
    def start_session(self, actor_id: str, run_id: str) -> dict[str, Any]:
        """Begin a coding-agent session for a (running) task run."""
        run = self._active_run(actor_id, run_id)
        session = self._sessions.create(
            {
                "run_id": run_id,
                "bundle_id": run.get("bundle_id"),
                "workspace_id": run.get("workspace_id"),
                "status": AgentSessionStatus.PLANNING.value,
                "plan": {},
                "summary": "",
                "attempts_count": 0,
                "created_by": actor_id,
                "started_at": _now(),
            }
        )
        self._event("agent.session.started", run, {"session_id": session["id"]})
        return session

    def record_plan(
        self, actor_id: str, session_id: str, *, plan: dict
    ) -> dict[str, Any]:
        """Store the structured plan the agent produced before coding."""
        self._open_session(actor_id, session_id)
        updated = self._sessions.update(
            session_id,
            {"plan": plan or {}, "status": AgentSessionStatus.CODING.value},
        )
        self._attempts.create(
            {
                "session_id": session_id,
                "iteration": 0,
                "phase": "plan",
                "status": "pass",
                "compile_output": "",
                "files": [],
            }
        )
        return updated

    def record_attempt(
        self,
        actor_id: str,
        session_id: str,
        *,
        iteration: int,
        phase: str,
        status: str,
        compile_output: str = "",
        files: list[dict] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Record one iteration of the code/compile/fix loop."""
        session = self._open_session(actor_id, session_id)
        attempt = self._attempts.create(
            {
                "session_id": session_id,
                "iteration": iteration,
                "phase": phase,
                "status": status,
                "compile_output": compile_output or "",
                "files": files or [],
                "error": error,
            }
        )
        new_status = _PHASE_STATUS.get(phase, session.get("status"))
        self._sessions.update(
            session_id,
            {
                "attempts_count": int(session.get("attempts_count", 0)) + 1,
                "status": new_status,
                "last_error": error if status == "fail" else session.get("last_error"),
            },
        )
        return attempt

    def finish_session(
        self,
        actor_id: str,
        session_id: str,
        *,
        status: str,
        summary: str = "",
    ) -> dict[str, Any]:
        """Close the session as succeeded or failed (terminal)."""
        session = self._open_session(actor_id, session_id)
        if status not in _FINAL_SESSION:
            raise OrchestrationError(
                f"finish status must be one of {sorted(_FINAL_SESSION)}"
            )
        updated = self._sessions.update(
            session_id,
            {"status": status, "summary": summary or "", "finished_at": _now()},
        )
        run = self._runs.get(session.get("run_id"))
        self._event(
            "agent.session.finished",
            run or {"workspace_id": session.get("workspace_id")},
            {"session_id": session_id, "status": status},
        )
        return updated

    def get_session(self, actor_id: str, session_id: str) -> dict[str, Any]:
        """Return a session plus its attempts (read model for the dashboard)."""
        rbac.require(actor_id, "agent:bridge")
        session = self._sessions.get(session_id)
        if not session:
            raise NotFoundError("agent session not found")
        attempts = self._attempts.list(
            filters={"session_id": session_id},
            order_by="created_at",
            limit=200,
        )
        return {"session": session, "attempts": attempts}

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

    def _open_session(self, actor_id: str, session_id: str) -> dict[str, Any]:
        rbac.require(actor_id, "agent:bridge")
        session = self._sessions.get(session_id)
        if not session:
            raise NotFoundError("agent session not found")
        if session.get("status") in _FINAL_SESSION:
            raise OrchestrationError(f"agent session is {session['status']} (terminal)")
        return session

    def _event(
        self, event_type: str, run: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        record_event(
            event_type=event_type,
            source="coding-agent",
            workspace_id=run.get("workspace_id"),
            payload={"run_id": run.get("id"), **payload},
        )


#: Map the phase just recorded to the session status it implies.
_PHASE_STATUS: dict[str, str] = {
    "code": AgentSessionStatus.COMPILING.value,
    "compile": AgentSessionStatus.COMPILING.value,
    "fix": AgentSessionStatus.FIXING.value,
    "commit": AgentSessionStatus.COMMITTING.value,
}
