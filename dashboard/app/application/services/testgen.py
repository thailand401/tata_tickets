"""Test-generation service (Phase 8): OpenSpec bundle -> test plan.

Takes a ready OpenSpec bundle (the Phase 3 output) and produces a structured
test plan: suites for every kind (unit, integration, api, regression, edge
case, mock, benchmark), each with planned cases, plus coverage targets,
benchmark budgets and a rendered report. Documentation only; never code.
"""

from __future__ import annotations

import re
from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.application.services.base import CrudService
from app.application.testgen.builder import build_test_plan
from app.core.exceptions import GenerationError, NotFoundError, ValidationError
from app.domain.enums import AuditAction, TestPlanStatus
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:60] or "test-plan"


class TestGenService(CrudService):
    resource = "testgen"
    entity_type = "test_plan"

    def __init__(
        self,
        repository: Repository | None = None,
        *,
        suites: Repository | None = None,
        cases: Repository | None = None,
        bundles: Repository | None = None,
        artifacts: Repository | None = None,
    ) -> None:
        super().__init__(repository or _repo("test_plans"))
        self._suites = suites or _repo("test_suites")
        self._cases = cases or _repo("test_cases")
        self._bundles = bundles or _repo("spec_bundles")
        self._artifacts = artifacts or _repo("spec_artifacts")

    # -- queries ------------------------------------------------------------
    def get_suites(self, actor_id: str, plan_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "testgen:read")
        return self._suites.list(filters={"plan_id": plan_id}, limit=50)

    def get_cases(self, actor_id: str, suite_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "testgen:read")
        return self._cases.list(
            filters={"suite_id": suite_id}, order_by="created_at", limit=500
        )

    def list_for_bundle(self, actor_id: str, bundle_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "testgen:read")
        return self.repo.list(
            filters={"bundle_id": bundle_id},
            order_by="created_at",
            descending=True,
            limit=100,
        )

    def report(self, actor_id: str, plan_id: str) -> dict[str, Any]:
        """Return the plan plus its suites (each with cases) and the report."""
        rbac.require(actor_id, "testgen:read")
        plan = self.repo.get(plan_id)
        if not plan:
            raise NotFoundError("test plan not found")
        suites = self._suites.list(filters={"plan_id": plan_id}, limit=50)
        for s in suites:
            s["cases"] = self._cases.list(
                filters={"suite_id": s["id"]}, order_by="created_at", limit=500
            )
        return {"plan": plan, "suites": suites}

    # -- generation ---------------------------------------------------------
    def generate(
        self,
        actor_id: str,
        bundle_id: str,
        *,
        coverage_target: int = 80,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a test plan from a ready OpenSpec bundle."""
        rbac.require(actor_id, "testgen:generate", workspace_id)
        bundle = self._bundles.get(bundle_id)
        if not bundle:
            raise NotFoundError("OpenSpec bundle not found")
        documents = self._documents(bundle_id)
        if not documents.get("tasks"):
            raise ValidationError("Bundle has no tasks artifact to derive tests from")

        title = bundle.get("title") or "Change"
        plan = self.repo.create(
            {
                "bundle_id": bundle_id,
                "workspace_id": workspace_id or bundle.get("workspace_id"),
                "title": title,
                "slug": _slugify(title),
                "status": TestPlanStatus.GENERATING.value,
                "coverage_target": coverage_target,
                "created_by": actor_id,
            }
        )
        plan_id = str(plan.get("id"))

        try:
            built = build_test_plan(title, documents, coverage_target=coverage_target)
            stored: list[dict[str, Any]] = []
            for suite in built["suites"]:
                row = self._suites.create(
                    {
                        "plan_id": plan_id,
                        "kind": suite["kind"],
                        "title": suite["title"],
                        "framework": suite["framework"],
                        "summary": suite["summary"],
                        "mocks": suite["mocks"],
                        "data": suite["data"],
                    }
                )
                for case in suite["cases"]:
                    self._cases.create(
                        {"suite_id": row["id"], "plan_id": plan_id, **case}
                    )
                stored.append(row)
            plan = self.repo.update(
                plan_id,
                {
                    "status": TestPlanStatus.READY.value,
                    "suite_count": built["suite_count"],
                    "case_count": built["case_count"],
                    "report": built["report"],
                },
            )
        except Exception as exc:
            self.repo.update(
                plan_id,
                {"status": TestPlanStatus.FAILED.value, "error": str(exc)},
            )
            self._emit(actor_id, plan_id, workspace_id, succeeded=False)
            raise GenerationError(f"Test generation failed: {exc}") from exc

        self._emit(actor_id, plan_id, workspace_id, succeeded=True)
        return {**plan, "suites": stored, "report": built["report"]}

    # -- helpers ------------------------------------------------------------
    def _documents(self, bundle_id: str) -> dict[str, Any]:
        artifacts = self._artifacts.list(filters={"bundle_id": bundle_id}, limit=50)
        return {
            a.get("kind"): {
                "title": a.get("title"),
                "content": a.get("content", ""),
                "data": a.get("data", {}),
            }
            for a in artifacts
        }

    def _emit(
        self,
        actor_id: str,
        plan_id: str,
        workspace_id: str | None,
        *,
        succeeded: bool,
    ) -> None:
        record_audit(
            actor_id=actor_id,
            action=AuditAction.GENERATE.value,
            entity_type="test_plan",
            entity_id=plan_id,
        )
        record_event(
            event_type="testgen.generated" if succeeded else "testgen.failed",
            source="dashboard",
            workspace_id=workspace_id,
            payload={"plan_id": plan_id},
        )
