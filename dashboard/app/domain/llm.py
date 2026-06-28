"""LLM port: a model-agnostic completion interface.

The platform is model-agnostic — Gemini, Claude, GPT and local models are all
addressed through this single port. Concrete providers live in the
infrastructure layer and are selected dynamically per task (no hardcoded
model). The application layer depends only on this abstraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    """A single chat message. role is one of system | user | assistant."""

    role: str
    content: str


@dataclass
class LLMRequest:
    """A provider-agnostic completion request."""

    messages: list[LLMMessage]
    model_key: str = ""
    temperature: float = 0.2
    max_tokens: int | None = None
    # Hint that the response should be a JSON object.
    json_response: bool = True


@dataclass
class LLMResponse:
    """A provider-agnostic completion response."""

    text: str
    provider: str
    model_key: str
    raw: dict = field(default_factory=dict)


class LLMError(Exception):
    """Raised by an LLM client when a completion fails (retryable)."""


class LLMClient(ABC):
    """Port implemented by every concrete LLM provider adapter."""

    provider: str = ""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run a single completion. Raise LLMError on failure."""
        ...
