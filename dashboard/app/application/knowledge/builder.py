"""Deterministic knowledge-graph builder (Phase 10).

Pure functions: given an OpenSpec bundle's documents (the Phase 3 artifacts)
they return typed nodes and the edges between them — api, entity, database,
architecture, business_rule, prompt, convention, history, dependency. No I/O,
no randomness, so ingest is reproducible and testable offline. Nodes store a
short summary only (never whole source bodies) so the agent fetches the
*relevant* context, not the entire codebase.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.enums import KnowledgeEdgeKind, KnowledgeKind, TaskCategory

#: OpenSpec task category -> the knowledge kind it contributes.
_CATEGORY_KIND: dict[str, KnowledgeKind] = {
    TaskCategory.BACKEND.value: KnowledgeKind.API,
    TaskCategory.DATABASE.value: KnowledgeKind.DATABASE,
    TaskCategory.FRONTEND.value: KnowledgeKind.ARCHITECTURE,
    TaskCategory.DEVOPS.value: KnowledgeKind.DEPENDENCY,
    TaskCategory.DOCUMENTATION.value: KnowledgeKind.CONVENTION,
    TaskCategory.TESTING.value: KnowledgeKind.HISTORY,
    TaskCategory.REVIEW.value: KnowledgeKind.HISTORY,
}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:60] or "item"


def _node(kind: KnowledgeKind, key: str, title: str, summary: str, **data: Any) -> dict:
    return {
        "kind": kind.value,
        "key": f"{kind.value}:{key}",
        "title": title,
        "summary": summary,
        "tags": [kind.value],
        "data": data,
    }


def _edge(source: str, target: str, kind: KnowledgeEdgeKind) -> dict:
    return {"source": source, "target": target, "kind": kind.value}


def _tasks(documents: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = (documents.get("tasks") or {}).get("data", {}).get("tasks") or []
    return [t for t in tasks if isinstance(t, dict)]


def _entity_name(title: str) -> str | None:
    """Pull a likely entity name out of a database task title."""
    m = re.search(r"(?:schema|table|model|entity)[:\s]+([a-z_][\w-]*)", title.lower())
    return m.group(1) if m else None


def _requirements(documents: dict[str, Any]) -> list[str]:
    text = (documents.get("requirements") or {}).get("content", "")
    rules = re.findall(r"^\s*(?:[-*]|\d+\.)\s+(.*\S)", text, flags=re.MULTILINE)
    return rules[:20]


def build_graph(title: str, documents: dict[str, Any]) -> dict[str, list[dict]]:
    """Build knowledge nodes + edges from OpenSpec documents (keys, not ids)."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(node: dict) -> str:
        nodes.setdefault(node["key"], node)
        return node["key"]

    # Root architecture node — everything is derived from the change bundle.
    root = add(
        _node(KnowledgeKind.ARCHITECTURE, slugify(title), title, "Change architecture")
    )
    add(_node(KnowledgeKind.HISTORY, slugify(title), f"{title} change", "Bundle ingested"))
    add(_node(KnowledgeKind.CONVENTION, "project", "Project conventions", "Coding standard"))
    add(_node(KnowledgeKind.PROMPT, "tech-spec", "Generation prompt", "Spec template"))

    # Nodes per task, by category; plus depends_on edges between them.
    tasks = _tasks(documents)
    key_by_task: dict[str, str] = {}
    for t in tasks:
        kind = _CATEGORY_KIND.get(t.get("category"), KnowledgeKind.ARCHITECTURE)
        nkey = add(_node(kind, slugify(t["key"]), t["title"], t.get("category", ""),
                         task_key=t["key"]))
        key_by_task[t["key"]] = nkey
        edges.append(_edge(nkey, root, KnowledgeEdgeKind.DERIVED_FROM))
        # database tasks own an entity
        ent = _entity_name(t["title"]) if kind is KnowledgeKind.DATABASE else None
        if ent:
            ek = add(_node(KnowledgeKind.ENTITY, ent, ent, f"Entity '{ent}'"))
            edges.append(_edge(nkey, ek, KnowledgeEdgeKind.OWNS))
    for t in tasks:
        for dep in t.get("depends_on") or []:
            if dep in key_by_task and t["key"] in key_by_task:
                edges.append(
                    _edge(key_by_task[t["key"]], key_by_task[dep],
                          KnowledgeEdgeKind.DEPENDS_ON)
                )

    # Business rules from requirements; each references the architecture.
    for i, rule in enumerate(_requirements(documents), 1):
        rk = add(_node(KnowledgeKind.BUSINESS_RULE, f"r{i}", rule[:80], rule))
        edges.append(_edge(rk, root, KnowledgeEdgeKind.RELATES_TO))

    return {"nodes": list(nodes.values()), "edges": edges}
