"""Task executor port (Phase 4).

The orchestrator owns scheduling, retry, timeout, dependencies and logging. The
*actual* work of a task is delegated to a :class:`TaskExecutor`. In production
the executor dispatches the task to an AI agent / the VS Code bridge (Phase 5)
and the result is pushed back asynchronously; for local runs and tests a
deterministic :class:`StubTaskExecutor` simulates execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ExecutionError(Exception):
    """Raised by an executor when a task attempt fails (retryable)."""


class ExecutionTimeout(ExecutionError):
    """Raised/returned when a task attempt exceeds its timeout."""


@dataclass
class ExecutionResult:
    """The outcome of a single successful task execution."""

    output: dict[str, Any] = field(default_factory=dict)


class TaskExecutor(ABC):
    """Port implemented by anything that can carry out a task run."""

    @abstractmethod
    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        """Run the task. Raise :class:`ExecutionError` to trigger a retry."""
        ...


class StubTaskExecutor(TaskExecutor):
    """Deterministic, offline executor used for local runs and tests."""

    def execute(self, task_run: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(
            output={
                "task_key": task_run.get("task_key"),
                "category": task_run.get("category"),
                "status": "done",
            }
        )
