"""Agent fleet service (Phase 11): a roster of specialists + auto-assignment.

Phase 4 schedules tasks into lanes; Phase 11 staffs those lanes with a fleet of
specialist agents and lets the scheduler auto-assign each task run to the best
one. The fleet is seeded idempotently (backend, frontend, flutter, python,
node, drupal, review, test, docs, planner + a generalist) and assignment is
deterministic via :mod:`app.application.orchestration.scheduler`.
"""

from __future__ import annotations

from typing import Any

from app.application.orchestration.scheduler import assign as assign_task
from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.application.services.base import CrudService
from app.core.exceptions import NotFoundError
from app.domain.enums import AgentRole, AuditAction, RegistryStatus
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

#: The default specialist roster. Pure config — seeded idempotently by slug.
DEFAULT_FLEET: tuple[dict[str, Any], ...] = (
    {"slug": "backend-agent", "name": "Backend Agent", "role": AgentRole.BACKEND,
     "stacks": ["api", "service", "server"], "desc": "Services, endpoints, business logic"},
    {"slug": "frontend-agent", "name": "Frontend Agent", "role": AgentRole.FRONTEND,
     "stacks": ["web", "ui", "css"], "desc": "Web UI, pages, components"},
    {"slug": "flutter-agent", "name": "Flutter Agent", "role": AgentRole.FLUTTER,
     "stacks": ["flutter", "dart", "mobile"], "desc": "Flutter / Dart mobile & desktop"},
    {"slug": "python-agent", "name": "Python Agent", "role": AgentRole.PYTHON,
     "stacks": ["python", "fastapi", "django"], "desc": "Python services & scripts"},
    {"slug": "node-agent", "name": "Node Agent", "role": AgentRole.NODE,
     "stacks": ["node", "express", "typescript"], "desc": "Node.js / TypeScript runtimes"},
    {"slug": "drupal-agent", "name": "Drupal Agent", "role": AgentRole.DRUPAL,
     "stacks": ["drupal", "php", "twig"], "desc": "Drupal / PHP CMS"},
    {"slug": "review-agent", "name": "Review Agent", "role": AgentRole.REVIEW,
     "stacks": ["review", "audit"], "desc": "Code review & feedback"},
    {"slug": "test-agent", "name": "Test Agent", "role": AgentRole.TEST,
     "stacks": ["test", "qa"], "desc": "Test generation & QA"},
    {"slug": "docs-agent", "name": "Docs Agent", "role": AgentRole.DOCS,
     "stacks": ["docs", "readme"], "desc": "Documentation & changelogs"},
    {"slug": "planner-agent", "name": "Planner Agent", "role": AgentRole.PLANNER,
     "stacks": ["plan", "breakdown"], "desc": "Planning, breakdown, orchestration"},
    {"slug": "generalist-agent", "name": "Generalist Agent", "role": AgentRole.GENERALIST,
     "stacks": [], "desc": "Fallback when no specialist matches"},
)


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


class AgentFleetService(CrudService):
    resource = "agent"
    entity_type = "agent"

    def __init__(
        self,
        agents: Repository | None = None,
        *,
        runs: Repository | None = None,
        bundles: Repository | None = None,
    ) -> None:
        super().__init__(agents or _repo("agents"))
        self._runs = runs or _repo("task_runs")
        self._bundles = bundles or _repo("spec_bundles")

    # =====================================================================
    # Seed: register the specialist roster (idempotent by slug)
    # =====================================================================
    def seed_fleet(
        self, actor_id: str, *, workspace_id: str | None = None
    ) -> list[dict[str, Any]]:
        rbac.require(actor_id, "fleet:manage", workspace_id)
        roster: list[dict[str, Any]] = []
        for spec in DEFAULT_FLEET:
            existing = self.repo.find_one({"slug": spec["slug"]})
            payload = {
                "slug": spec["slug"],
                "name": spec["name"],
                "description": spec["desc"],
                "role": spec["role"].value,
                "config": {"roles": [spec["role"].value], "stacks": spec["stacks"]},
                "status": RegistryStatus.ACTIVE.value,
            }
            roster.append(self.repo.update(existing["id"], payload) if existing
                          else self.repo.create({**payload, "created_by": actor_id}))
        record_audit(actor_id=actor_id, action=AuditAction.CREATE.value,
                     entity_type="agent_fleet", entity_id=None, after={"count": len(roster)})
        record_event(event_type="fleet.seeded", source="dashboard", workspace_id=workspace_id,
                     payload={"agents": len(roster)})
        return roster

    def roster(
        self, actor_id: str, *, workspace_id: str | None = None
    ) -> list[dict[str, Any]]:
        rbac.require(actor_id, "agent:read", workspace_id)
        return self.repo.list(filters={"status": "active"}, limit=200)

    # =====================================================================
    # Auto-assign: scheduler staffs every task run of a bundle
    # =====================================================================
    def assign_bundle(
        self, actor_id: str, bundle_id: str, *, workspace_id: str | None = None
    ) -> list[dict[str, Any]]:
        rbac.require(actor_id, "fleet:assign", workspace_id)
        runs = self._runs.list(filters={"bundle_id": bundle_id}, limit=500)
        if not runs:
            raise NotFoundError("no task runs for bundle; enqueue first")
        agents = self.repo.list(filters={"status": "active"}, limit=200)
        ws = workspace_id
        results: list[dict[str, Any]] = []
        for run in runs:
            task = {"key": run.get("task_key"), "title": run.get("title", ""),
                    "category": run.get("category", "backend"),
                    "description": (run.get("payload") or {}).get("description", "")}
            plan = assign_task(task, agents)
            self._runs.update(run["id"], {"agent_id": plan["agent_id"],
                                          "agent_slug": plan["agent_slug"], "role": plan["role"]})
            results.append({"run_id": run["id"], **plan})
            ws = ws or run.get("workspace_id")
        record_audit(actor_id=actor_id, action=AuditAction.DISPATCH.value,
                     entity_type="spec_bundle", entity_id=bundle_id,
                     after={"assigned": sum(r["status"] == "assigned" for r in results)})
        record_event(event_type="fleet.assigned", source="dashboard", workspace_id=ws,
                     payload={"bundle_id": bundle_id, "runs": len(results)})
        return results

    def match(self, actor_id: str, *, title: str, category: str = "backend") -> dict[str, Any]:
        rbac.require(actor_id, "agent:read")
        agents = self.repo.list(filters={"status": "active"}, limit=200)
        return assign_task({"key": "preview", "title": title, "category": category}, agents)
