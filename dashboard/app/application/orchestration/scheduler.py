"""Multi-agent scheduler (Phase 11): auto-assign tasks to specialist agents.

Phase 4 gives every task a single execution *lane* (``TaskCategory``). Phase 11
turns that lane plus a lightweight *tech-stack* detection into a concrete
**specialist role** (backend, frontend, flutter, python, node, drupal, review,
test, docs, planner) and picks the best active agent for it. A stack specialist
always beats a category generalist — a ``backend`` task about *Flutter* goes to
the Flutter agent, a ``backend`` task about *Drupal* goes to the Drupal agent.

Everything here is pure and deterministic so assignment is reproducible and
testable offline — no I/O, no randomness, no hardcoded model.
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import AgentRole, TaskCategory

# Stack hints checked *before* the category lane. First match wins, so order
# from most specific to least. A match overrides the category default.
_STACK: tuple[tuple[AgentRole, tuple[str, ...]], ...] = (
    (AgentRole.FLUTTER, ("flutter", "dart", "android", "ios", "mobile app")),
    (AgentRole.DRUPAL, ("drupal", "php", "twig", "composer", "cms")),
    (AgentRole.NODE, ("node", "nodejs", "express", "nestjs", "npm", "typescript", "javascript")),
    (AgentRole.PYTHON, ("python", "fastapi", "django", "flask")),
)

# Activity lanes win over a language stack: a *Python test* is the Test agent's
# job, a *Flutter doc* is the Docs agent's. These lanes are cross-cutting.
_ACTIVITY_ROLE: dict[str, AgentRole] = {
    TaskCategory.REVIEW.value: AgentRole.REVIEW,
    TaskCategory.TESTING.value: AgentRole.TEST,
    TaskCategory.DOCUMENTATION.value: AgentRole.DOCS,
}

# Category lane -> default specialist role when no stack hint matches.
_CATEGORY_ROLE: dict[str, AgentRole] = {
    TaskCategory.BACKEND.value: AgentRole.BACKEND,
    TaskCategory.FRONTEND.value: AgentRole.FRONTEND,
    TaskCategory.DATABASE.value: AgentRole.BACKEND,
    TaskCategory.DEVOPS.value: AgentRole.BACKEND,
    TaskCategory.REVIEW.value: AgentRole.REVIEW,
    TaskCategory.TESTING.value: AgentRole.TEST,
    TaskCategory.DOCUMENTATION.value: AgentRole.DOCS,
}


def detect_stack(text: str) -> AgentRole | None:
    """Return the specialist role implied by the task's tech stack, if any."""
    low = (text or "").lower()
    for role, hints in _STACK:
        if any(h in low for h in hints):
            return role
    return None


def match_role(text: str, category: str, *, default: AgentRole = AgentRole.BACKEND) -> AgentRole:
    """Resolve a task to a single specialist role.

    Activity lanes (review/test/docs) win; otherwise a tech stack beats the
    generic category lane, which beats the default.
    """
    cat = (category or "").lower()
    if cat in _ACTIVITY_ROLE:
        return _ACTIVITY_ROLE[cat]
    stack = detect_stack(text)
    if stack is not None:
        return stack
    return _CATEGORY_ROLE.get(cat, default)


def _agent_roles(agent: dict[str, Any]) -> set[str]:
    """All roles an agent can serve (top-level ``role`` + config roles/caps)."""
    config = agent.get("config") or {}
    raw: list[Any] = []
    if agent.get("role"):
        raw.append(agent["role"])
    for field in ("roles", "categories", "capabilities"):
        value = config.get(field)
        if isinstance(value, str):
            raw.append(value)
        elif isinstance(value, list):
            raw.extend(value)
    return {str(r).lower() for r in raw}


def select_specialist(
    role: AgentRole, agents: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Pick the best active agent for ``role``.

    1. an active agent declaring the exact role; 2. an explicit generalist;
    3. an agent with no declared role; otherwise ``None`` (left unassigned).
    """
    active = [a for a in agents if (a.get("status") or "active") in ("active", "draft")]
    want = role.value
    for agent in active:
        if want in _agent_roles(agent):
            return agent
    for agent in active:
        if AgentRole.GENERALIST.value in _agent_roles(agent):
            return agent
    for agent in active:
        if not _agent_roles(agent):
            return agent
    return None


def assign(task: dict[str, Any], agents: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign one task to a specialist. Returns the role + chosen agent (or none)."""
    text = f"{task.get('title', '')} {task.get('description', '')} {task.get('category', '')}"
    role = match_role(text, task.get("category", TaskCategory.BACKEND.value))
    agent = select_specialist(role, agents)
    return {
        "task_key": task.get("key"),
        "role": role.value,
        "agent_id": (agent or {}).get("id"),
        "agent_slug": (agent or {}).get("slug"),
        "status": "assigned" if agent else "unassigned",
    }


def assign_all(
    tasks: list[dict[str, Any]], agents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Assign a batch of tasks; deterministic for a given fleet."""
    return [assign(t, agents) for t in tasks]
