"""Request schemas for the REST API (responses are returned as dicts/rows)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.domain.enums import (
    RegistryStatus,
    SpecStatus,
    TicketPriority,
    TicketStatus,
)


# -- auth ------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


# -- projects / workspaces -------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str | None = None
    is_active: bool = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class WorkspaceCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# -- tickets ---------------------------------------------------------------
class TicketCreate(BaseModel):
    workspace_id: str
    title: str = Field(min_length=1)
    description: str | None = None
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee_id: str | None = None


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: str | None = None


# -- prompts ---------------------------------------------------------------
class PromptCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str | None = None
    status: RegistryStatus = RegistryStatus.DRAFT


class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: RegistryStatus | None = None


class PromptVersionCreate(BaseModel):
    content: str = Field(min_length=1)
    variables: dict = Field(default_factory=dict)
    notes: str | None = None


class PromptRollback(BaseModel):
    version: int = Field(ge=1)


# -- models / agents / workflows ------------------------------------------
class ModelCreate(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_key: str = Field(min_length=1)
    config: dict = Field(default_factory=dict)
    status: RegistryStatus = RegistryStatus.ACTIVE


class ModelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: RegistryStatus | None = None


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str | None = None
    config: dict = Field(default_factory=dict)
    default_model_id: str | None = None
    status: RegistryStatus = RegistryStatus.DRAFT


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    default_model_id: str | None = None
    status: RegistryStatus | None = None


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    description: str | None = None
    definition: dict = Field(default_factory=dict)
    status: RegistryStatus = RegistryStatus.DRAFT


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict | None = None
    status: RegistryStatus | None = None


# -- roles -----------------------------------------------------------------
class RoleCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


# -- tech specs ------------------------------------------------------------
class TechSpecCreate(BaseModel):
    title: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    workspace_id: str | None = None
    ticket_id: str | None = None
    prompt_id: str | None = None
    model_id: str | None = None


class TechSpecUpdate(BaseModel):
    title: str | None = None
    source_text: str | None = None
    status: SpecStatus | None = None
    prompt_id: str | None = None
    model_id: str | None = None


class TechSpecGenerate(BaseModel):
    model_id: str | None = None
    prompt_id: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_attempts: int = Field(default=3, ge=1, le=5)
    notes: str | None = None


# -- openspec (Phase 3) ----------------------------------------------------
class OpenSpecGenerate(BaseModel):
    spec_version: int | None = Field(default=None, ge=1)


# -- orchestration (Phase 4) -----------------------------------------------
class OrchestrationEnqueue(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)


class OrchestrationRun(BaseModel):
    max_parallel: int = Field(default=4, ge=1, le=32)


# -- agent bridge (Phase 5) ------------------------------------------------
class AgentPull(BaseModel):
    categories: list[str] | None = None


class AgentProgress(BaseModel):
    percent: int = Field(default=0, ge=0, le=100)
    message: str = ""
    data: dict = Field(default_factory=dict)


class AgentLog(BaseModel):
    level: str = "info"
    message: str = Field(min_length=1)
    data: dict = Field(default_factory=dict)


class AgentCommit(BaseModel):
    sha: str = Field(min_length=1)
    message: str = ""
    branch: str | None = None
    url: str | None = None


class AgentReview(BaseModel):
    status: str = Field(min_length=1)  # approved | changes_requested | commented
    summary: str = ""
    data: dict = Field(default_factory=dict)


class AgentError(BaseModel):
    message: str = Field(min_length=1)
    retry: bool = True
    data: dict = Field(default_factory=dict)


class AgentComplete(BaseModel):
    summary: str = ""
    result: dict = Field(default_factory=dict)


# -- coding agent (Phase 6) ------------------------------------------------
class AgentPlanIn(BaseModel):
    plan: dict = Field(default_factory=dict)


class AgentAttemptIn(BaseModel):
    iteration: int = Field(default=1, ge=0)
    phase: str = Field(min_length=1)  # plan | code | compile | fix | commit
    status: str = Field(min_length=1)  # pass | fail
    compile_output: str = ""
    files: list[dict] = Field(default_factory=list)
    error: str | None = None


class AgentSessionFinish(BaseModel):
    status: str = Field(min_length=1)  # succeeded | failed
    summary: str = ""


# -- test generation (Phase 8) ---------------------------------------------
class TestGenGenerate(BaseModel):
    coverage_target: int = Field(default=80, ge=0, le=100)


# -- self-healing loop (Phase 9) -------------------------------------------
class RepairStart(BaseModel):
    errors: str = Field(default="", description="The build/test errors received")
    max_iterations: int = Field(default=5, ge=1, le=20)


class RepairStepIn(BaseModel):
    iteration: int = Field(default=1, ge=0)
    gate: str = Field(min_length=1)  # compile | review | test | fix | commit
    result: str = Field(min_length=1)  # pass | fail
    output: str = ""
    files: list[dict] = Field(default_factory=list)
    error: str | None = None


class RepairFinish(BaseModel):
    status: str = Field(min_length=1)  # passed | failed
    commit_sha: str | None = None
    summary: str = ""


# -- knowledge graph (Phase 10) --------------------------------------------
class KnowledgeIngest(BaseModel):
    workspace_id: str | None = None


class KnowledgeNodeIn(BaseModel):
    kind: str = Field(min_length=1)  # api|entity|database|architecture|...
    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    workspace_id: str | None = None
    bundle_id: str | None = None


class KnowledgeNodeUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    data: dict | None = None


class KnowledgeLinkIn(BaseModel):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    kind: str = "relates_to"
    weight: float = Field(default=1.0, ge=0)


class KnowledgeQuery(BaseModel):
    text: str = ""
    kinds: list[str] | None = None
    bundle_id: str | None = None
    workspace_id: str | None = None
    limit: int = Field(default=8, ge=1, le=50)
    hops: int = Field(default=1, ge=0, le=3)


# -- agent fleet (Phase 11) ------------------------------------------------
class FleetSeed(BaseModel):
    workspace_id: str | None = None


class FleetAssign(BaseModel):
    workspace_id: str | None = None


class FleetMatch(BaseModel):
    title: str = Field(min_length=1)
    category: str = "backend"


# -- deploy & operate (Phase 12) -------------------------------------------
class DeployIn(BaseModel):
    bundle_id: str | None = None
    environment: str = "staging"  # dev | staging | production
    commit_sha: str | None = None
    trigger: str = "manual"
    repo: str = "ghcr.io/tata/dashboard"
    workspace_id: str | None = None


class HealthCheckIn(BaseModel):
    probes: list[dict] = Field(default_factory=list)  # [{name, ok}]


class ScaleIn(BaseModel):
    replicas: int = Field(default=1, ge=1, le=50)


class WebhookIn(BaseModel):
    provider: str = "github"  # github | gitlab
    payload: dict = Field(default_factory=dict)
    workspace_id: str | None = None


class BackupIn(BaseModel):
    kind: str = "full"  # database | artifacts | full
    location: str = ""
    workspace_id: str | None = None


class RestoreIn(BaseModel):
    workspace_id: str | None = None
