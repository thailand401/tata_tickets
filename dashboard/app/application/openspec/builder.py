"""Deterministic OpenSpec document renderers.

The functions here are pure: given a validated Tech Spec content dict they
return markdown strings and a structured task list. No I/O, no randomness — so
the whole Phase 3 pipeline is reproducible and testable offline.
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import ArtifactKind, TaskCategory, TicketPriority

# Order in which task lanes are scheduled; also drives the dependency DAG.
_LANE_ORDER = (
    TaskCategory.DATABASE,
    TaskCategory.BACKEND,
    TaskCategory.FRONTEND,
    TaskCategory.TESTING,
    TaskCategory.REVIEW,
    TaskCategory.DEVOPS,
    TaskCategory.DOCUMENTATION,
)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if value:
        return [str(value).strip()]
    return []


def _md_list(items: list[str], *, empty: str = "_None specified._") -> str:
    items = [i for i in items if i]
    if not items:
        return empty
    return "\n".join(f"- {i}" for i in items)


def _priority(content: dict[str, Any]) -> str:
    pr = content.get("priority") or TicketPriority.MEDIUM.value
    return str(pr)


def build_tasks(content: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive an ordered, dependency-linked task list from a Tech Spec.

    Produces a DAG: database -> backend -> frontend -> testing -> review ->
    devops -> documentation. Items within the database/backend lanes can run in
    parallel; later lanes depend on the lanes that precede them.
    """
    priority = _priority(content)
    feature = (content.get("feature") or "the feature").strip()
    database = _as_list(content.get("database"))
    api = _as_list(content.get("api"))
    acceptance = _as_list(content.get("acceptance_criteria"))

    tasks: list[dict[str, Any]] = []
    counter = 1

    def _add(
        title: str,
        category: TaskCategory,
        description: str,
        depends_on: list[str],
        *,
        acceptance_text: str = "",
    ) -> str:
        nonlocal counter
        key = f"T{counter}"
        counter += 1
        tasks.append(
            {
                "key": key,
                "title": title,
                "category": category.value,
                "description": description,
                "acceptance": acceptance_text,
                "depends_on": depends_on,
                "priority": priority,
            }
        )
        return key

    # -- Database lane (roots) ---------------------------------------------
    db_keys: list[str] = []
    if database:
        for item in database:
            db_keys.append(
                _add(
                    f"Design schema: {item[:80]}",
                    TaskCategory.DATABASE,
                    f"Model and migrate: {item}",
                    [],
                )
            )
    else:
        db_keys.append(
            _add(
                "Design data model",
                TaskCategory.DATABASE,
                f"Define the persistence model required for {feature}.",
                [],
            )
        )

    # -- Backend lane (depends on database) --------------------------------
    backend_keys: list[str] = []
    if api:
        for item in api:
            backend_keys.append(
                _add(
                    f"Implement endpoint: {item[:80]}",
                    TaskCategory.BACKEND,
                    f"Build the backend behaviour for: {item}",
                    list(db_keys),
                )
            )
    else:
        backend_keys.append(
            _add(
                "Implement backend logic",
                TaskCategory.BACKEND,
                f"Implement the server-side behaviour for {feature}.",
                list(db_keys),
            )
        )

    # -- Frontend lane (depends on backend) --------------------------------
    fe_key = _add(
        f"Build UI for {feature}",
        TaskCategory.FRONTEND,
        f"Implement the user-facing interface for {feature}.",
        list(backend_keys),
    )

    # -- Testing lane (depends on backend + frontend) ----------------------
    test_key = _add(
        "Write & run tests",
        TaskCategory.TESTING,
        "Cover acceptance criteria with automated tests.",
        list(backend_keys) + [fe_key],
        acceptance_text="; ".join(acceptance) if acceptance else "All criteria pass.",
    )

    # -- Review lane (depends on testing) ----------------------------------
    review_key = _add(
        "Code & spec review",
        TaskCategory.REVIEW,
        "Review implementation against the spec and acceptance criteria.",
        [test_key],
    )

    # -- DevOps lane (depends on review) -----------------------------------
    devops_key = _add(
        "Build, package & deploy",
        TaskCategory.DEVOPS,
        "Containerize and roll out the change behind safe checks.",
        [review_key],
    )

    # -- Documentation lane (depends on review) ----------------------------
    _add(
        "Update documentation",
        TaskCategory.DOCUMENTATION,
        f"Document {feature}, its API and operational notes.",
        [review_key, devops_key],
    )

    return tasks


# ---------------------------------------------------------------------------
# Markdown renderers (one per artifact kind)
# ---------------------------------------------------------------------------
def _render_proposal(title: str, content: dict[str, Any]) -> str:
    return (
        f"# Proposal: {title}\n\n"
        "## Why\n\n"
        f"{content.get('business_goal') or 'Deliver the requested capability.'}\n\n"
        "## What Changes\n\n"
        f"{_md_list(_as_list(content.get('functional_requirements')))}\n\n"
        "## Impact\n\n"
        f"- **Priority:** {_priority(content)}\n"
        f"- **Estimate:** {content.get('estimate') or 'TBD'}\n"
        f"- **Dependencies:** {', '.join(_as_list(content.get('dependencies'))) or 'none'}\n"
    )


def _render_requirements(title: str, content: dict[str, Any]) -> str:
    functional = _as_list(content.get("functional_requirements"))
    scenarios = "\n\n".join(
        f"#### Requirement: {req}\n\n"
        f"- **Scenario:** WHEN the feature is used, THEN `{req}` holds."
        for req in functional
    ) or "_No functional requirements captured._"
    return (
        f"# Requirements: {title}\n\n"
        "## Functional Requirements\n\n"
        f"{scenarios}\n\n"
        "## Non-Functional Requirements\n\n"
        f"{_md_list(_as_list(content.get('non_functional')))}\n\n"
        "## Acceptance Criteria\n\n"
        f"{_md_list(_as_list(content.get('acceptance_criteria')))}\n"
    )


def _render_tasks(title: str, tasks: list[dict[str, Any]]) -> str:
    lines = [f"# Tasks: {title}", ""]
    by_lane: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        by_lane.setdefault(t["category"], []).append(t)
    for lane in _LANE_ORDER:
        lane_tasks = by_lane.get(lane.value)
        if not lane_tasks:
            continue
        lines.append(f"## {lane.value.capitalize()}")
        lines.append("")
        for t in lane_tasks:
            deps = ", ".join(t["depends_on"]) or "—"
            lines.append(
                f"- [ ] **{t['key']}** {t['title']} "
                f"_(priority: {t['priority']}, depends on: {deps})_"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_architecture(title: str, content: dict[str, Any]) -> str:
    return (
        f"# Architecture: {title}\n\n"
        "## Context\n\n"
        f"{content.get('business_goal') or 'See proposal.'}\n\n"
        "## API Surface\n\n"
        f"{_md_list(_as_list(content.get('api')))}\n\n"
        "## Data Model\n\n"
        f"{_md_list(_as_list(content.get('database')))}\n\n"
        "## Cross-cutting Concerns\n\n"
        f"{_md_list(_as_list(content.get('non_functional')))}\n\n"
        "## Risks & Mitigations\n\n"
        f"{_md_list(_as_list(content.get('risks')))}\n"
    )


def _render_migration(title: str, content: dict[str, Any]) -> str:
    db = _as_list(content.get("database"))
    body = "\n".join(f"-- {line}" for line in db) or "-- No schema changes identified."
    return (
        f"# Migration Plan: {title}\n\n"
        "> Documentation only — a suggested DDL outline, not an executed script.\n\n"
        "## Proposed schema changes\n\n"
        "```sql\n"
        f"{body}\n"
        "```\n\n"
        "## Rollback\n\n"
        "- Reverse the statements above in dependency order.\n"
        "- Verify no data loss before applying in production.\n"
    )


def _render_checklist(title: str, content: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    lanes = sorted({t["category"] for t in tasks})
    lane_items = "\n".join(f"- [ ] {lane.capitalize()} tasks complete" for lane in lanes)
    acceptance = _md_list(
        [f"[ ] {c}" for c in _as_list(content.get("acceptance_criteria"))],
        empty="- [ ] Acceptance criteria verified",
    )
    return (
        f"# Delivery Checklist: {title}\n\n"
        "## Lanes\n\n"
        f"{lane_items}\n\n"
        "## Acceptance\n\n"
        f"{acceptance}\n\n"
        "## Release Gate\n\n"
        "- [ ] Review approved\n"
        "- [ ] Tests green\n"
        "- [ ] Deployed & monitored\n"
        "- [ ] Documentation updated\n"
    )


def build_bundle(title: str, content: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build every OpenSpec artifact from a Tech Spec content dict.

    Returns a mapping ``{ArtifactKind.value: {"title", "content", "data"}}``.
    """
    tasks = build_tasks(content)
    return {
        ArtifactKind.PROPOSAL.value: {
            "title": f"Proposal — {title}",
            "content": _render_proposal(title, content),
            "data": {},
        },
        ArtifactKind.REQUIREMENTS.value: {
            "title": f"Requirements — {title}",
            "content": _render_requirements(title, content),
            "data": {},
        },
        ArtifactKind.TASKS.value: {
            "title": f"Tasks — {title}",
            "content": _render_tasks(title, tasks),
            "data": {"tasks": tasks},
        },
        ArtifactKind.ARCHITECTURE.value: {
            "title": f"Architecture — {title}",
            "content": _render_architecture(title, content),
            "data": {},
        },
        ArtifactKind.MIGRATION.value: {
            "title": f"Migration — {title}",
            "content": _render_migration(title, content),
            "data": {},
        },
        ArtifactKind.CHECKLIST.value: {
            "title": f"Checklist — {title}",
            "content": _render_checklist(title, content, tasks),
            "data": {},
        },
    }
