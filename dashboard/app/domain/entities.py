"""Domain entities as Pydantic models (framework-agnostic data shapes)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import (
    ArtifactKind,
    GenerationStatus,
    RegistryStatus,
    RunState,
    SpecBundleStatus,
    SpecStatus,
    TaskCategory,
    TaskState,
    TicketPriority,
    TicketStatus,
)

class _Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Profile(_Entity):
    id: UUID
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Role(_Entity):
    id: UUID
    name: str
    description: str | None = None
    is_system: bool = False
    created_at: datetime | None = None


class Permission(_Entity):
    id: UUID
    code: str
    description: str | None = None
    created_at: datetime | None = None


class Project(_Entity):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    is_active: bool = True
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Workspace(_Entity):
    id: UUID
    project_id: UUID
    name: str
    description: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Ticket(_Entity):
    id: UUID
    workspace_id: UUID
    title: str
    description: str | None = None
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Prompt(_Entity):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    status: RegistryStatus = RegistryStatus.DRAFT
    current_version: int = 0
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PromptVersion(_Entity):
    id: UUID
    prompt_id: UUID
    version: int
    content: str
    variables: dict = {}
    notes: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


class Model(_Entity):
    id: UUID
    name: str
    provider: str
    model_key: str
    config: dict = {}
    status: RegistryStatus = RegistryStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Agent(_Entity):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    config: dict = {}
    default_model_id: UUID | None = None
    status: RegistryStatus = RegistryStatus.DRAFT
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Workflow(_Entity):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    definition: dict = {}
    status: RegistryStatus = RegistryStatus.DRAFT
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EventLogEntry(_Entity):
    id: UUID
    event_type: str
    source: str | None = None
    workspace_id: UUID | None = None
    payload: dict = {}
    created_at: datetime | None = None


class TaskQueueItem(_Entity):
    id: UUID
    queue: str = "default"
    task_type: str
    state: TaskState = TaskState.PENDING
    attempts: int = 0
    max_attempts: int = 3
    payload: dict = {}
    last_error: str | None = None
    available_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AuditLogEntry(_Entity):
    id: UUID
    actor_id: UUID | None = None
    action: str
    entity_type: str
    entity_id: UUID | None = None
    before: dict | None = None
    after: dict | None = None
    created_at: datetime | None = None


class TechSpecContent(_Entity):
    """Structured Tech Spec produced by AI analysis of a free-text ticket.

    This is documentation only — never source code. Every field is part of
    the standard spec contract returned by the LLM and validated here.
    """

    feature: str = ""
    business_goal: str = ""
    functional_requirements: list[str] = []
    non_functional: list[str] = []
    api: list[str] = []
    database: list[str] = []
    acceptance_criteria: list[str] = []
    risks: list[str] = []
    dependencies: list[str] = []
    estimate: str = ""
    priority: TicketPriority = TicketPriority.MEDIUM


class TechSpec(_Entity):
    """A Tech Spec request: the free-text source plus generation metadata."""

    id: UUID
    workspace_id: UUID | None = None
    ticket_id: UUID | None = None
    title: str
    source_text: str
    status: SpecStatus = SpecStatus.DRAFT
    current_version: int = 0
    prompt_id: UUID | None = None
    model_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TechSpecVersion(_Entity):
    """An immutable AI generation attempt; the history of a Tech Spec."""

    id: UUID
    spec_id: UUID
    version: int
    status: GenerationStatus = GenerationStatus.PENDING
    content: dict = {}
    raw_output: str | None = None
    model_id: UUID | None = None
    model_key: str | None = None
    provider: str | None = None
    prompt_id: UUID | None = None
    prompt_version: int | None = None
    attempts: int = 1
    error: str | None = None
    notes: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


# =====================================================================
# Phase 3 — OpenSpec generation
# =====================================================================
class ProposalTask(_Entity):
    """A single structured task inside an OpenSpec ``tasks`` artifact.

    This is the contract Phase 4 (orchestration) consumes: a stable key, a
    category lane, a priority and a dependency list forming a DAG.
    """

    key: str
    title: str
    category: TaskCategory
    description: str = ""
    acceptance: str = ""
    depends_on: list[str] = []
    priority: TicketPriority = TicketPriority.MEDIUM


class SpecArtifact(_Entity):
    """One generated OpenSpec document (markdown, documentation only)."""

    id: UUID
    bundle_id: UUID
    kind: ArtifactKind
    title: str
    content: str = ""
    # Structured payload (e.g. the task list for the ``tasks`` artifact).
    data: dict = {}
    created_at: datetime | None = None


class SpecBundle(_Entity):
    """An OpenSpec change bundle generated from a ready Tech Spec version."""

    id: UUID
    spec_id: UUID
    spec_version: int
    workspace_id: UUID | None = None
    title: str
    slug: str = ""
    status: SpecBundleStatus = SpecBundleStatus.DRAFT
    error: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# =====================================================================
# Phase 4 — Task orchestration
# =====================================================================
class TaskRun(_Entity):
    """An orchestrated execution of one OpenSpec task (the Phase 4 unit)."""

    id: UUID
    bundle_id: UUID
    workspace_id: UUID | None = None
    task_key: str
    title: str
    category: TaskCategory
    state: RunState = RunState.PENDING
    priority: TicketPriority = TicketPriority.MEDIUM
    depends_on: list[str] = []
    agent_id: UUID | None = None
    agent_slug: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: int = 300
    payload: dict = {}
    result: dict = {}
    last_error: str | None = None
    claimed_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskLog(_Entity):
    """A log/progress line pushed for a task run (by orchestrator or agent)."""

    id: UUID
    run_id: UUID
    level: str = "info"
    kind: str = "log"  # log | progress | commit | review | error | state
    message: str = ""
    data: dict = {}
    created_at: datetime | None = None
