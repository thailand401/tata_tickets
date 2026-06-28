"""Tests for Tech Spec generation: structure, retry/history, compare, failure."""

from __future__ import annotations

import pytest

from app.application.services.tech_spec import TechSpecService, parse_spec_content
from app.core.exceptions import GenerationError, ValidationError
from app.domain.llm import LLMClient, LLMError, LLMRequest, LLMResponse
from app.infrastructure.llm import StubLLMClient
from tests.fakes import FakeRepository

_REQUIRED_FIELDS = [
    "feature",
    "business_goal",
    "functional_requirements",
    "non_functional",
    "api",
    "database",
    "acceptance_criteria",
    "risks",
    "dependencies",
    "estimate",
    "priority",
]


class _FailingLLM(LLMClient):
    provider = "failing"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        raise LLMError("provider unavailable")


class _BadJSONLLM(LLMClient):
    provider = "badjson"

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="not json at all", provider=self.provider, model_key="x")


@pytest.fixture(autouse=True)
def _allow_and_capture(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.application.services.tech_spec.record_audit", lambda **kw: None
    )
    monkeypatch.setattr(
        "app.application.services.tech_spec.record_event", lambda **kw: None
    )


def _make_service(llm: LLMClient) -> tuple[TechSpecService, FakeRepository]:
    specs = FakeRepository()
    service = TechSpecService(
        specs,
        versions=FakeRepository(),
        prompts=FakeRepository(),
        prompt_versions=FakeRepository(),
        models=FakeRepository(),
        llm=llm,
    )
    return service, specs


def _seed_spec(specs: FakeRepository, source: str = "Build a login page. Add 2FA.") -> str:
    row = specs.create(
        {"title": "Login", "source_text": source, "status": "draft", "current_version": 0}
    )
    return row["id"]


# -- parsing ---------------------------------------------------------------
def test_parse_spec_content_accepts_fenced_json() -> None:
    text = '```json\n{"feature": "X", "priority": "high"}\n```'
    content = parse_spec_content(text)
    assert content["feature"] == "X"
    assert content["priority"] == "high"


def test_parse_spec_content_rejects_non_json() -> None:
    with pytest.raises(ValidationError):
        parse_spec_content("totally not json")


# -- generation structure --------------------------------------------------
def test_generate_produces_full_structured_spec() -> None:
    service, specs = _make_service(StubLLMClient())
    spec_id = _seed_spec(specs)

    version = service.generate("actor-1", spec_id)

    assert version["status"] == "succeeded"
    assert version["version"] == 1
    content = version["content"]
    for field in _REQUIRED_FIELDS:
        assert field in content, field
    assert content["functional_requirements"]  # non-empty
    assert specs.get(spec_id)["status"] == "ready"
    assert specs.get(spec_id)["current_version"] == 1


# -- retry / history -------------------------------------------------------
def test_regenerate_appends_to_history() -> None:
    service, specs = _make_service(StubLLMClient())
    spec_id = _seed_spec(specs)

    service.generate("actor-1", spec_id)
    service.generate("actor-1", spec_id)

    history = service.list_versions("actor-1", spec_id)
    assert [h["version"] for h in history] == [2, 1]  # newest first
    assert specs.get(spec_id)["current_version"] == 2


def test_internal_retry_counts_attempts() -> None:
    """A flaky client that fails twice then succeeds is retried internally."""

    class _Flaky(LLMClient):
        provider = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: LLMRequest) -> LLMResponse:
            self.calls += 1
            if self.calls < 3:
                raise LLMError("transient")
            return StubLLMClient().complete(request)

    flaky = _Flaky()
    service, specs = _make_service(flaky)
    spec_id = _seed_spec(specs)

    version = service.generate("actor-1", spec_id, max_attempts=3)
    assert version["status"] == "succeeded"
    assert version["attempts"] == 3
    assert flaky.calls == 3


# -- compare ---------------------------------------------------------------
def test_compare_reports_changed_fields() -> None:
    service, specs = _make_service(StubLLMClient())
    spec_id = _seed_spec(specs, "Build a login page.")
    service.generate("actor-1", spec_id)

    # Change the source so a second generation differs, then regenerate.
    specs.update(spec_id, {"source_text": "Build a billing dashboard with exports."})
    service.generate("actor-1", spec_id)

    result = service.compare("actor-1", spec_id, 1, 2)
    assert result["diff"]["feature"]["changed"] is True
    assert result["a"]["version"] == 1
    assert result["b"]["version"] == 2


# -- failure path ----------------------------------------------------------
def test_generation_failure_records_failed_version() -> None:
    failing = _FailingLLM()
    service, specs = _make_service(failing)
    spec_id = _seed_spec(specs)

    with pytest.raises(GenerationError):
        service.generate("actor-1", spec_id, max_attempts=2)

    assert failing.calls == 2  # retried up to max_attempts
    history = service.list_versions("actor-1", spec_id)
    assert history[0]["status"] == "failed"
    assert history[0]["error"]
    assert specs.get(spec_id)["status"] == "failed"


def test_bad_json_response_fails_after_retries() -> None:
    service, specs = _make_service(_BadJSONLLM())
    spec_id = _seed_spec(specs)

    with pytest.raises(GenerationError):
        service.generate("actor-1", spec_id, max_attempts=2)

    history = service.list_versions("actor-1", spec_id)
    assert history[0]["status"] == "failed"
