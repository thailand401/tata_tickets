"""Domain enums mirroring database enum types."""

from __future__ import annotations

from enum import Enum


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RegistryStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"


class ModelProvider(str, Enum):
    GEMINI = "gemini"
    CLAUDE = "claude"
    GPT = "gpt"
    LOCAL = "local"


class SpecStatus(str, Enum):
    """Lifecycle of a Tech Spec document."""

    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"


class GenerationStatus(str, Enum):
    """Outcome of a single AI generation attempt (a spec version)."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"
    GENERATE = "generate"
    ENQUEUE = "enqueue"
    DISPATCH = "dispatch"
    CANCEL = "cancel"
    RESUME = "resume"


# =====================================================================
# Phase 3 — OpenSpec generation
# =====================================================================
class SpecBundleStatus(str, Enum):
    """Lifecycle of an OpenSpec change bundle (a set of documents)."""

    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ArtifactKind(str, Enum):
    """The standard OpenSpec documents produced from a Tech Spec.

    Documentation only — never source code.
    """

    PROPOSAL = "proposal"
    REQUIREMENTS = "requirements"
    TASKS = "tasks"
    ARCHITECTURE = "architecture"
    MIGRATION = "migration"
    CHECKLIST = "checklist"


# =====================================================================
# Phase 4 — Task orchestration
# =====================================================================
class TaskCategory(str, Enum):
    """Execution lane a task is routed to (and the agent capability needed)."""

    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    TESTING = "testing"
    REVIEW = "review"
    DEVOPS = "devops"
    DOCUMENTATION = "documentation"


class RunState(str, Enum):
    """State machine for a single orchestrated task run."""

    PENDING = "pending"          # created, dependencies not yet satisfied check
    BLOCKED = "blocked"          # waiting on unfinished dependencies
    QUEUED = "queued"            # ready, waiting for a worker/agent slot
    RUNNING = "running"          # claimed/executing
    SUCCEEDED = "succeeded"
    FAILED = "failed"            # failed, may retry
    RETRYING = "retrying"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    DEAD = "dead"                # exhausted retries, terminal failure


# =====================================================================
# Phase 6 — Autonomous coding agent
# =====================================================================
class AgentSessionStatus(str, Enum):
    """Lifecycle of one run of the coding-agent loop for a task run."""

    PLANNING = "planning"
    CODING = "coding"
    COMPILING = "compiling"
    FIXING = "fixing"
    COMMITTING = "committing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentAttemptPhase(str, Enum):
    """Which step of the agent loop an attempt records."""

    PLAN = "plan"
    CODE = "code"
    COMPILE = "compile"
    FIX = "fix"
    COMMIT = "commit"


class AgentAttemptStatus(str, Enum):
    """Outcome of a single agent attempt."""

    PASS = "pass"
    FAIL = "fail"


# =====================================================================
# Phase 8 — Test generation
# =====================================================================
class TestPlanStatus(str, Enum):
    """Lifecycle of a generated test plan (documentation only)."""

    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class TestKind(str, Enum):
    """The categories of test suite produced from an OpenSpec bundle."""

    UNIT = "unit"
    INTEGRATION = "integration"
    API = "api"
    REGRESSION = "regression"
    EDGE_CASE = "edge_case"
    MOCK = "mock"
    BENCHMARK = "benchmark"


class TestCaseStatus(str, Enum):
    """Outcome a generated case is expected to assert (documentation only)."""

    PLANNED = "planned"
    GENERATED = "generated"
    SKIPPED = "skipped"


# =====================================================================
# Phase 9 — Self-healing loop (receive errors -> fix -> pass -> commit)
# =====================================================================
class RepairSessionStatus(str, Enum):
    """Lifecycle of one self-healing run: errors -> compile/review/test -> fix -> commit."""

    RECEIVING = "receiving"      # errors received, loop not yet started
    COMPILING = "compiling"      # building the changed code
    REVIEWING = "reviewing"      # static/AI review gate
    TESTING = "testing"          # test gate
    FIXING = "fixing"            # AI applying a fix before the next loop
    COMMITTING = "committing"    # all gates green, committing
    PASSED = "passed"            # committed + run state updated (terminal)
    FAILED = "failed"            # iterations exhausted / aborted (terminal)


class RepairGate(str, Enum):
    """Which gate a single repair step records as it loops to green."""

    COMPILE = "compile"
    REVIEW = "review"
    TEST = "test"
    FIX = "fix"
    COMMIT = "commit"


class RepairResult(str, Enum):
    """Outcome of a single repair step."""

    PASS = "pass"
    FAIL = "fail"


# =====================================================================
# Phase 10 — Knowledge Graph (relevant context, not whole source)
# =====================================================================
class KnowledgeKind(str, Enum):
    """The kinds of node stored in the project knowledge graph."""

    API = "api"                      # endpoints, contracts, surfaces
    ENTITY = "entity"                # domain models / data structures
    DATABASE = "database"            # tables, schemas, migrations
    ARCHITECTURE = "architecture"    # components, layers, decisions
    BUSINESS_RULE = "business_rule"  # requirements / constraints
    PROMPT = "prompt"                # versioned prompt templates
    CONVENTION = "convention"        # coding standards, patterns
    HISTORY = "history"              # changes, runs, past sessions
    DEPENDENCY = "dependency"        # external libs / services


class KnowledgeEdgeKind(str, Enum):
    """How two knowledge nodes relate (a directed edge source -> target)."""

    DEPENDS_ON = "depends_on"        # source needs target
    REFERENCES = "references"        # source mentions target
    IMPLEMENTS = "implements"        # source realises target
    OWNS = "owns"                    # source contains target
    DERIVED_FROM = "derived_from"    # source generated from target
    RELATES_TO = "relates_to"        # generic association


# =====================================================================
# Phase 11 — Multi-agent fleet (scheduler auto-assigns to specialists)
# =====================================================================
class AgentRole(str, Enum):
    """A specialist agent's role; the scheduler routes tasks to one of these."""

    BACKEND = "backend"          # services, endpoints, business logic
    FRONTEND = "frontend"        # web UI, pages, components
    FLUTTER = "flutter"          # Flutter / Dart mobile & desktop apps
    PYTHON = "python"            # Python services, scripts, data work
    NODE = "node"                # Node.js / TypeScript runtimes
    DRUPAL = "drupal"            # Drupal / PHP CMS work
    REVIEW = "review"            # code review & feedback
    TEST = "test"                # test generation & QA
    DOCS = "docs"                # documentation & changelogs
    PLANNER = "planner"          # planning, breakdown, orchestration
    GENERALIST = "generalist"    # fallback when no specialist matches


class AssignmentStatus(str, Enum):
    """Whether a task run has been matched to a fleet agent."""

    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


# =====================================================================
# Phase 12 — Deploy & operate (CI/CD, auto-deploy, health, scale, backup)
# =====================================================================
class DeployStatus(str, Enum):
    """State machine for one deployment of a bundle to an environment."""

    PENDING = "pending"          # queued, image not built yet
    BUILDING = "building"        # CI building the image
    DEPLOYING = "deploying"      # rolling the image out
    HEALTHY = "healthy"          # health check passed (live)
    DEGRADED = "degraded"        # health check failing
    FAILED = "failed"            # deploy failed
    ROLLED_BACK = "rolled_back"  # superseded / reverted to a previous release


class DeployTrigger(str, Enum):
    """What kicked off a deployment."""

    MANUAL = "manual"            # dashboard / CLI
    GITHUB = "github"            # GitHub push/release webhook
    GITLAB = "gitlab"            # GitLab push webhook
    AUTO = "auto"                # auto-deploy after green CI
    ROLLBACK = "rollback"        # created by a rollback


class DeployEnv(str, Enum):
    """Target environment for a deployment."""

    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class HealthStatus(str, Enum):
    """Outcome of a health check probe."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class BackupKind(str, Enum):
    """What a backup snapshot captures."""

    DATABASE = "database"
    ARTIFACTS = "artifacts"
    FULL = "full"


class BackupStatus(str, Enum):
    """Lifecycle of a backup snapshot."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    RESTORED = "restored"
