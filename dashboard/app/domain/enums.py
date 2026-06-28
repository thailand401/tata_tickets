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
