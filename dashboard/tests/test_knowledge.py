"""Phase 10 tests: knowledge graph — ingest a bundle, fetch relevant context."""

from __future__ import annotations

import pytest

from app.application.knowledge.builder import build_graph
from app.application.services.knowledge import KnowledgeGraphService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.enums import KnowledgeKind
from tests.fakes import FakeRepository

_TASKS = [
    {"key": "T1", "title": "Design schema: users", "category": "database", "depends_on": []},
    {"key": "T2", "title": "Implement endpoint: POST /auth/login", "category": "backend",
     "depends_on": ["T1"]},
    {"key": "T3", "title": "Build UI for login", "category": "frontend", "depends_on": ["T2"]},
    {"key": "T4", "title": "Write & run tests", "category": "testing", "depends_on": ["T2"]},
]
_DOCS = {
    "tasks": {"title": "Tasks", "content": "# Tasks", "data": {"tasks": _TASKS}},
    "requirements": {"title": "Reqs", "content": "- Users must log in\n- Reject bad creds",
                     "data": {}},
}


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.knowledge.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.knowledge.record_event", lambda **k: None)


def _make():
    nodes, edges, bundles, artifacts, runs = (FakeRepository() for _ in range(5))
    service = KnowledgeGraphService(
        nodes, edges=edges, bundles=bundles, artifacts=artifacts, runs=runs
    )
    return service, nodes, edges, bundles, artifacts, runs


def _seed(bundles, artifacts) -> str:
    bundle = bundles.create({"title": "Login", "workspace_id": "ws1", "status": "ready"})
    bid = bundle["id"]
    for kind, doc in _DOCS.items():
        artifacts.create({"bundle_id": bid, "kind": kind, "title": doc["title"],
                          "content": doc["content"], "data": doc["data"]})
    return bid


# -- pure builder ----------------------------------------------------------
def test_build_graph_emits_typed_nodes_and_edges() -> None:
    graph = build_graph("Login", _DOCS)
    kinds = {n["kind"] for n in graph["nodes"]}
    assert KnowledgeKind.DATABASE.value in kinds
    assert KnowledgeKind.API.value in kinds
    assert KnowledgeKind.BUSINESS_RULE.value in kinds
    assert KnowledgeKind.ENTITY.value in kinds  # users entity from db task
    assert any(e["kind"] == "depends_on" for e in graph["edges"])


# -- ingest ----------------------------------------------------------------
def test_ingest_creates_nodes_and_is_idempotent() -> None:
    service, nodes, edges, bundles, artifacts, _ = _make()
    bid = _seed(bundles, artifacts)

    first = service.ingest("u", bid)
    count = len(nodes.list(limit=1000))
    assert first["nodes"] > 0 and first["edges"] > 0
    service.ingest("u", bid)
    assert len(nodes.list(limit=1000)) == count  # upsert, no duplicates


def test_ingest_missing_bundle_raises() -> None:
    service, *_ = _make()
    with pytest.raises(NotFoundError):
        service.ingest("u", "nope")


# -- relevant retrieval ----------------------------------------------------
def test_query_returns_only_relevant_subgraph() -> None:
    service, _n, _e, bundles, artifacts, _ = _make()
    bid = _seed(bundles, artifacts)
    service.ingest("u", bid)

    result = service.query("u", text="login endpoint", bundle_id=bid, limit=3, hops=0)
    assert 0 < len(result["nodes"]) <= 3
    assert any("login" in n["title"].lower() for n in result["nodes"])


def test_context_for_run_scopes_to_bundle() -> None:
    service, _n, _e, bundles, artifacts, runs = _make()
    bid = _seed(bundles, artifacts)
    service.ingest("u", bid)
    run = runs.create({"bundle_id": bid, "workspace_id": "ws1", "title": "POST /auth/login",
                       "category": "backend", "state": "running"})

    ctx = service.context("u", run["id"], limit=4, hops=1)
    assert ctx["run_id"] == run["id"]
    assert ctx["nodes"]


def test_context_missing_run_raises() -> None:
    service, *_ = _make()
    with pytest.raises(NotFoundError):
        service.context("u", "nope")


# -- linking ---------------------------------------------------------------
def test_link_rejects_unknown_kind() -> None:
    service, *_ = _make()
    with pytest.raises(ValidationError):
        service.link("u", "a", "b", kind="bogus")
