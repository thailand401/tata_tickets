"""Concrete LLM clients and a config-driven provider registry.

Adding a new provider is config-only: implement :class:`LLMClient` and call
:func:`register_provider`. No model is hardcoded anywhere — the caller selects
a provider/model per task.

The default registered provider is :class:`StubLLMClient`, a fully offline
deterministic analyzer. It lets the whole Tech Spec pipeline run (and be
tested) without any external API keys, and is transparently replaced by a real
provider once one is registered for that provider name.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from app.core.logging import get_logger
from app.domain.enums import TicketPriority
from app.domain.llm import LLMClient, LLMRequest, LLMResponse

log = get_logger("llm")

_PROVIDERS: dict[str, Callable[[], LLMClient]] = {}


def register_provider(name: str, factory: Callable[[], LLMClient]) -> None:
    """Register a provider factory under a provider name (e.g. "claude")."""
    _PROVIDERS[name.lower()] = factory


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Resolve a client for ``provider``, falling back to the offline stub."""
    key = (provider or "").lower()
    factory = _PROVIDERS.get(key)
    if factory is None:
        if key:
            log.info("llm_provider_fallback", requested=key, used="stub")
        return StubLLMClient()
    return factory()


# ---------------------------------------------------------------------------
# Offline deterministic analyzer
# ---------------------------------------------------------------------------
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_PRIORITY_HINTS = {
    TicketPriority.CRITICAL: ("critical", "urgent", "asap", "outage", "security"),
    TicketPriority.HIGH: ("high", "important", "deadline", "blocker", "must"),
    TicketPriority.LOW: ("nice to have", "low", "minor", "someday", "optional"),
}


def _clean_lines(text: str) -> list[str]:
    parts = [p.strip(" -*\t") for p in _SENTENCE_SPLIT.split(text)]
    return [p for p in parts if p]


def _detect_priority(text: str) -> TicketPriority:
    low = text.lower()
    for priority, hints in _PRIORITY_HINTS.items():
        if any(h in low for h in hints):
            return priority
    return TicketPriority.MEDIUM


def _estimate(sentences: list[str]) -> str:
    points = min(13, max(1, len(sentences)))
    return f"~{points} story points"


class StubLLMClient(LLMClient):
    """Deterministic, offline Tech Spec analyzer.

    It derives a complete, structured spec from the free-text source carried in
    the last user message. The output is valid JSON matching the Tech Spec
    contract, so the application layer can parse it exactly as it would a real
    model response.
    """

    provider = "stub"

    def complete(self, request: LLMRequest) -> LLMResponse:
        source = ""
        for msg in reversed(request.messages):
            if msg.role == "user" and msg.content.strip():
                source = msg.content.strip()
                break

        sentences = _clean_lines(source) or ["Unspecified requirement"]
        feature = sentences[0][:120]
        priority = _detect_priority(source)

        spec = {
            "feature": feature,
            "business_goal": (
                f"Deliver '{feature}' to address the stated need and create "
                "measurable user/business value."
            ),
            "functional_requirements": sentences,
            "non_functional": [
                "Performance: responses within acceptable latency under load",
                "Security: authenticated access and least-privilege authorization",
                "Reliability: graceful error handling and retry on transient failures",
                "Observability: actions are logged and auditable",
            ],
            "api": [
                "POST /resource — create the entity described by the feature",
                "GET /resource/{id} — fetch a single entity",
                "GET /resource — list entities with pagination",
            ],
            "database": [
                "resource(id uuid pk, created_at timestamptz, updated_at timestamptz)",
                "Indexes on frequently queried/filter columns",
            ],
            "acceptance_criteria": [
                f"Given the requirement '{s}', the outcome is verifiable."
                for s in sentences
            ],
            "risks": [
                "Ambiguous or incomplete requirements in the source ticket",
                "Scope creep beyond the stated feature",
            ],
            "dependencies": [
                "Authentication/authorization platform",
                "Persistence layer (database) availability",
            ],
            "estimate": _estimate(sentences),
            "priority": priority.value,
        }

        text = json.dumps(spec, ensure_ascii=False, indent=2)
        return LLMResponse(
            text=text,
            provider=self.provider,
            model_key=request.model_key or "stub-analyzer",
            raw={"source_chars": len(source)},
        )


# Always have a working default provider available.
register_provider("stub", StubLLMClient)
