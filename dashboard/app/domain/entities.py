"""Domain entities as Pydantic models (framework-agnostic data shapes)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import (
    AgentAttemptPhase,
    AgentAttemptStatus,
    AgentSessionStatus,
    ArtifactKind,
    BackupKind,
    BackupStatus,
    DeployEnv,
    DeployStatus,
    DeployTrigger,
    GenerationStatus,
    HealthStatus,
    KnowledgeEdgeKind,
    KnowledgeKind,
    RegistryStatus,
    RepairGate,
    RepairResult,
    RepairSessionStatus,
    RunState,
    SpecBundleStatus,
    SpecStatus,
    TaskCategory,
    TaskState,
    TestCaseStatus,
    TestKind,
    TestPlanStatus,
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
    role: str | None = None
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


# =====================================================================
# Phase 6 — Autonomous coding agent
# =====================================================================
class AgentSession(_Entity):
    """One run of the coding-agent loop (plan -> code -> compile -> fix -> commit)."""

    id: UUID
    run_id: UUID
    bundle_id: UUID | None = None
    workspace_id: UUID | None = None
    status: AgentSessionStatus = AgentSessionStatus.PLANNING
    plan: dict = {}
    summary: str = ""
    attempts_count: int = 0
    last_error: str | None = None
    created_by: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentAttempt(_Entity):
    """A single attempt within the agent loop (one code/compile/fix iteration)."""

    id: UUID
    session_id: UUID
    iteration: int = 1
    phase: AgentAttemptPhase
    status: AgentAttemptStatus
    compile_output: str = ""
    files: list[dict] = []
    error: str | None = None
    created_at: datetime | None = None


# =====================================================================
# Phase 8 — Test generation
# =====================================================================
class TestPlan(_Entity):
    """A generated test plan derived from an OpenSpec bundle.

    Documentation only — describes the suites, cases, mocks, coverage targets,
    benchmarks and the rendered report. Never executed source code.
    """

    id: UUID
    bundle_id: UUID
    workspace_id: UUID | None = None
    title: str
    slug: str = ""
    status: TestPlanStatus = TestPlanStatus.DRAFT
    coverage_target: int = 80
    case_count: int = 0
    suite_count: int = 0
    error: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestSuite(_Entity):
    """One suite of a test plan (unit, integration, api, regression, ...)."""

    id: UUID
    plan_id: UUID
    kind: TestKind
    title: str
    framework: str = ""
    summary: str = ""
    mocks: list[str] = []
    data: dict = {}
    created_at: datetime | None = None


class TestCase(_Entity):
    """A single planned test case inside a suite (documentation only)."""

    id: UUID
    suite_id: UUID
    plan_id: UUID
    name: str
    given: str = ""
    when: str = ""
    then: str = ""
    kind: TestKind = TestKind.UNIT
    status: TestCaseStatus = TestCaseStatus.PLANNED
    created_at: datetime | None = None


# =====================================================================
# Phase 9 — Self-healing loop
# =====================================================================
class RepairSession(_Entity):
    """One self-healing run for a task run: receive errors -> fix loop -> commit."""

    id: UUID
    run_id: UUID
    bundle_id: UUID | None = None
    workspace_id: UUID | None = None
    status: RepairSessionStatus = RepairSessionStatus.RECEIVING
    errors: str = ""
    summary: str = ""
    iterations_count: int = 0
    max_iterations: int = 5
    last_error: str | None = None
    commit_sha: str | None = None
    created_by: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RepairStep(_Entity):
    """One gate within the loop (compile/review/test/fix/commit), pass or fail."""

    id: UUID
    session_id: UUID
    iteration: int = 1
    gate: RepairGate
    result: RepairResult
    output: str = ""
    files: list[dict] = []
    error: str | None = None
    created_at: datetime | None = None


# =====================================================================
# Phase 10 — Knowledge Graph
# =====================================================================
class KnowledgeNode(_Entity):
    """One node in the project knowledge graph.

    A small, typed fact about the project (an api, entity, table, rule,
    convention, …) so the agent can fetch only the relevant context instead of
    reading the whole source.
    """

    id: UUID
    workspace_id: UUID | None = None
    bundle_id: UUID | None = None
    kind: KnowledgeKind
    key: str
    title: str
    summary: str = ""
    tags: list[str] = []
    data: dict = {}
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KnowledgeEdge(_Entity):
    """A directed relationship between two knowledge nodes."""

    id: UUID
    workspace_id: UUID | None = None
    source_id: UUID
    target_id: UUID
    kind: KnowledgeEdgeKind = KnowledgeEdgeKind.RELATES_TO
    weight: float = 1.0
    created_at: datetime | None = None


# =====================================================================
# Phase 12 — Deploy & operate
# =====================================================================
class Deployment(_Entity):
    """One release of a bundle to an environment: build -> deploy -> healthy."""

    id: UUID
    workspace_id: UUID | None = None
    bundle_id: UUID | None = None
    environment: DeployEnv = DeployEnv.STAGING
    version: str
    image: str = ""
    commit_sha: str | None = None
    trigger: DeployTrigger = DeployTrigger.MANUAL
    status: DeployStatus = DeployStatus.PENDING
    replicas: int = 1
    health: HealthStatus = HealthStatus.DOWN
    previous_id: UUID | None = None
    summary: str = ""
    created_by: UUID | None = None
    deployed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Backup(_Entity):
    """A database/artifacts snapshot that a deployment can be restored from."""

    id: UUID
    workspace_id: UUID | None = None
    kind: BackupKind = BackupKind.FULL
    location: str = ""
    size_bytes: int = 0
    status: BackupStatus = BackupStatus.PENDING
    deployment_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


class WebhookEvent(_Entity):
    """A normalized GitHub/GitLab push/release event that may auto-deploy."""

    id: UUID
    workspace_id: UUID | None = None
    provider: DeployTrigger = DeployTrigger.GITHUB
    event: str = "push"
    ref: str = ""
    commit_sha: str | None = None
    deployment_id: UUID | None = None
    created_at: datetime | None = None
