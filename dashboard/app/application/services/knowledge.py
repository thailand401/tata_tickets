"""Knowledge-graph service (Phase 10): store facts, serve relevant context.

Phase 3 produces the OpenSpec bundle; here it is ingested into a typed graph of
api / entity / database / architecture / business_rule / prompt / convention /
history / dependency nodes and the edges between them. The agent then asks for
*relevant* context (a small, scored subgraph) instead of reading the whole
source — fast to fetch, cheap to feed a model, and grounded in the spec.
"""

from __future__ import annotations

import re
from typing import Any

from app.application.knowledge.builder import build_graph
from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.application.services.base import CrudService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.enums import AuditAction, KnowledgeEdgeKind, KnowledgeKind
from app.domain.repositories import Repository
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

_KINDS = {k.value for k in KnowledgeKind}
_EDGE_KINDS = {k.value for k in KnowledgeEdgeKind}


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


class KnowledgeGraphService(CrudService):
    resource = "knowledge"
    entity_type = "knowledge_node"

    def __init__(
        self,
        repository: Repository | None = None,
        *,
        edges: Repository | None = None,
        bundles: Repository | None = None,
        artifacts: Repository | None = None,
        runs: Repository | None = None,
    ) -> None:
        super().__init__(repository or _repo("kg_nodes"))
        self._edges = edges or _repo("kg_edges")
        self._bundles = bundles or _repo("spec_bundles")
        self._artifacts = artifacts or _repo("spec_artifacts")
        self._runs = runs or _repo("task_runs")

    # =====================================================================
    # Ingest: OpenSpec bundle -> typed nodes + edges (idempotent upsert)
    # =====================================================================
    def ingest(
        self, actor_id: str, bundle_id: str, *, workspace_id: str | None = None
    ) -> dict[str, Any]:
        rbac.require(actor_id, "knowledge:ingest", workspace_id)
        bundle = self._bundles.get(bundle_id)
        if not bundle:
            raise NotFoundError("OpenSpec bundle not found")
        ws = workspace_id or bundle.get("workspace_id")
        graph = build_graph(bundle.get("title") or "Change", self._documents(bundle_id))

        id_by_key: dict[str, str] = {}
        for node in graph["nodes"]:
            id_by_key[node["key"]] = self._upsert_node(actor_id, node, bundle_id, ws)
        edges = 0
        for edge in graph["edges"]:
            src, dst = id_by_key.get(edge["source"]), id_by_key.get(edge["target"])
            if src and dst and self._link(src, dst, edge["kind"], ws):
                edges += 1

        record_audit(
            actor_id=actor_id, action=AuditAction.GENERATE.value,
            entity_type="knowledge_graph", entity_id=bundle_id,
        )
        record_event(
            event_type="knowledge.ingested", source="dashboard", workspace_id=ws,
            payload={"bundle_id": bundle_id, "nodes": len(graph["nodes"]), "edges": edges},
        )
        return {"bundle_id": bundle_id, "nodes": len(graph["nodes"]), "edges": edges}

    def link(
        self, actor_id: str, source_id: str, target_id: str,
        *, kind: str = "relates_to", weight: float = 1.0,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        rbac.require(actor_id, "knowledge:write", workspace_id)
        if kind not in _EDGE_KINDS:
            raise ValidationError(f"edge kind must be one of {sorted(_EDGE_KINDS)}")
        return self._edges.create(
            {"source_id": source_id, "target_id": target_id, "kind": kind,
             "weight": weight, "workspace_id": workspace_id}
        )

    # =====================================================================
    # Retrieval: relevant subgraph only — never the whole source
    # =====================================================================
    def query(
        self, actor_id: str, *, text: str = "", kinds: list[str] | None = None,
        bundle_id: str | None = None, workspace_id: str | None = None,
        limit: int = 8, hops: int = 1,
    ) -> dict[str, Any]:
        rbac.require(actor_id, "knowledge:read", workspace_id)
        filters: dict[str, Any] = {}
        if bundle_id:
            filters["bundle_id"] = bundle_id
        if workspace_id:
            filters["workspace_id"] = workspace_id
        pool = self.repo.list(filters=filters or None, limit=1000)
        if kinds:
            allow = set(kinds) & _KINDS
            pool = [n for n in pool if n.get("kind") in allow]
        seeds = self._rank(pool, text, limit)
        return self._expand(seeds, pool, hops)

    def context(
        self, actor_id: str, run_id: str, *, limit: int = 8, hops: int = 1
    ) -> dict[str, Any]:
        """Relevant subgraph for a task run — what the agent fetches to code."""
        rbac.require(actor_id, "agent:bridge")
        run = self._runs.get(run_id)
        if not run:
            raise NotFoundError("task run not found")
        result = self.query(
            actor_id, text=f"{run.get('title','')} {run.get('category','')}",
            bundle_id=run.get("bundle_id"), workspace_id=run.get("workspace_id"),
            limit=limit, hops=hops,
        )
        return {"run_id": run_id, **result}

    # =====================================================================
    # Internals
    # =====================================================================
    def _upsert_node(
        self, actor_id: str, node: dict, bundle_id: str, ws: str | None
    ) -> str:
        existing = self.repo.find_one({"key": node["key"], "workspace_id": ws})
        payload = {**node, "bundle_id": bundle_id, "workspace_id": ws}
        if existing:
            return str(self.repo.update(existing["id"], payload)["id"])
        payload["created_by"] = actor_id
        return str(self.repo.create(payload)["id"])

    def _link(self, src: str, dst: str, kind: str, ws: str | None) -> bool:
        if self._edges.find_one({"source_id": src, "target_id": dst, "kind": kind}):
            return False
        self._edges.create(
            {"source_id": src, "target_id": dst, "kind": kind, "workspace_id": ws}
        )
        return True

    def _rank(self, pool: list[dict], text: str, limit: int) -> list[dict]:
        terms = _tokens(text)
        if not terms:
            return pool[:limit]
        scored = []
        for n in pool:
            hay = _tokens(f"{n.get('title','')} {n.get('summary','')} {n.get('key','')}")
            score = len(terms & hay)
            if score:
                scored.append((score, n))
        scored.sort(key=lambda s: (-s[0], str(s[1].get("title"))))
        return [n for _, n in scored[:limit]]

    def _expand(
        self, seeds: list[dict], pool: list[dict], hops: int
    ) -> dict[str, Any]:
        by_id = {n["id"]: n for n in pool}
        keep = {n["id"] for n in seeds}
        frontier = set(keep)
        for _ in range(max(0, hops)):
            edges = self._edges.list(limit=2000)
            nxt: set[str] = set()
            for e in edges:
                if e.get("source_id") in frontier and e.get("target_id") in by_id:
                    nxt.add(e["target_id"])
                if e.get("target_id") in frontier and e.get("source_id") in by_id:
                    nxt.add(e["source_id"])
            new = nxt - keep
            keep |= new
            frontier = new
            if not new:
                break
        nodes = [by_id[i] for i in keep]
        ids = set(keep)
        rel = [
            e for e in self._edges.list(limit=2000)
            if e.get("source_id") in ids and e.get("target_id") in ids
        ]
        return {"nodes": nodes, "edges": rel}

    def _documents(self, bundle_id: str) -> dict[str, Any]:
        rows = self._artifacts.list(filters={"bundle_id": bundle_id}, limit=50)
        return {
            a.get("kind"): {"title": a.get("title"), "content": a.get("content", ""),
                            "data": a.get("data", {})}
            for a in rows
        }
