"""Deterministic task classification and agent selection (Phase 4).

A task is routed to one execution *lane* (``TaskCategory``). The classifier is
keyword-based and deterministic so routing is reproducible and testable. Agent
selection then picks the best-matching active agent for that lane based on the
agent's declared capabilities/categories (config-only — no hardcoding).
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import TaskCategory

# Ordered keyword hints per lane. First lane with a match wins (order matters:
# more specific lanes are checked before generic ones).
_KEYWORDS: tuple[tuple[TaskCategory, tuple[str, ...]], ...] = (
    (TaskCategory.DATABASE, ("schema", "migration", "table", "database", "index", "sql", "ddl")),
    (TaskCategory.TESTING, ("test", "tests", "qa", "coverage", "assert", "pytest")),
    (TaskCategory.REVIEW, ("review", "approve", "audit", "inspect")),
    (TaskCategory.DEVOPS, ("deploy", "docker", "ci", "cd", "pipeline", "release", "package", "infra")),
    (TaskCategory.DOCUMENTATION, ("document", "docs", "readme", "changelog", "manual")),
    (TaskCategory.FRONTEND, ("ui", "frontend", "page", "component", "css", "view", "screen")),
    (TaskCategory.BACKEND, ("api", "endpoint", "backend", "service", "server", "handler", "route")),
)


def classify_category(text: str, *, default: TaskCategory = TaskCategory.BACKEND) -> TaskCategory:
    """Classify free text into a single execution lane."""
    low = (text or "").lower()
    for category, hints in _KEYWORDS:
        if any(h in low for h in hints):
            return category
    return default


def _agent_categories(agent: dict[str, Any]) -> set[str]:
    config = agent.get("config") or {}
    cats = config.get("categories") or config.get("capabilities") or []
    if isinstance(cats, str):
        cats = [cats]
    return {str(c).lower() for c in cats}


def select_agent(
    category: TaskCategory, agents: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Pick the best active agent for ``category``.

    Preference order:
      1. An active agent that declares the exact category/capability.
      2. An active agent with no declared categories (a generalist).
      3. ``None`` when no agent is available (task is left unassigned).
    """
    active = [a for a in agents if (a.get("status") or "active") == "active"]
    cat = category.value

    for agent in active:
        if cat in _agent_categories(agent):
            return agent
    for agent in active:
        if not _agent_categories(agent):
            return agent
    return None
