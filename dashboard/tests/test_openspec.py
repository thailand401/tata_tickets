"""Phase 3 tests: OpenSpec bundle generation from a ready Tech Spec version."""

from __future__ import annotations

import pytest

from app.application.openspec.builder import build_bundle, build_tasks
from app.application.services.openspec import OpenSpecService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.enums import ArtifactKind
from tests.fakes import FakeRepository

_CONTENT = {
    "feature": "User login with 2FA",
    "business_goal": "Let users sign in securely.",
    "functional_requirements": ["Login with email/password", "Verify a 2FA code"],
    "non_functional": ["Latency < 200ms", "Audit all sign-ins"],
    "api": ["POST /auth/login", "POST /auth/2fa/verify"],
    "database": ["users(id, email)", "mfa_secrets(user_id, secret)"],
    "acceptance_criteria": ["Valid creds + code -> session", "Bad code -> rejected"],
    "risks": ["Brute force on codes"],
    "dependencies": ["Email provider"],
    "estimate": "~8 story points",
    "priority": "high",
}


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.openspec.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.openspec.record_event", lambda **k: None)


def _make_service():
    bundles = FakeRepository()
    artifacts = FakeRepository()
    specs = FakeRepository()
    versions = FakeRepository()
    service = OpenSpecService(
        bundles, artifacts=artifacts, specs=specs, spec_versions=versions
    )
    return service, bundles, artifacts, specs, versions


def _seed_ready_spec(specs: FakeRepository, versions: FakeRepository) -> str:
    spec = specs.create({"title": "Login", "source_text": "x", "status": "ready"})
    versions.create(
        {"spec_id": spec["id"], "version": 1, "status": "succeeded", "content": _CONTENT}
    )
    return spec["id"]


# -- pure builder ----------------------------------------------------------
def test_build_bundle_produces_all_six_artifacts() -> None:
    bundle = build_bundle("Login", _CONTENT)
    assert set(bundle.keys()) == {k.value for k in ArtifactKind}
    for art in bundle.values():
        assert art["title"]
        assert art["content"]


def test_build_tasks_forms_a_dependency_dag() -> None:
    tasks = build_tasks(_CONTENT)
    keys = {t["key"] for t in tasks}
    categories = {t["category"] for t in tasks}
    # Every lane is represented.
    assert categories == {
        "database", "backend", "frontend", "testing", "review", "devops", "documentation"
    }
    # Database tasks are roots; backend depends on database.
    db = [t for t in tasks if t["category"] == "database"]
    be = [t for t in tasks if t["category"] == "backend"]
    assert all(t["depends_on"] == [] for t in db)
    assert all(set(t["depends_on"]) <= keys for t in tasks)
    assert all(set(t["depends_on"]) & {d["key"] for d in db} for t in be)


# -- service ---------------------------------------------------------------
def test_generate_creates_ready_bundle_with_artifacts() -> None:
    service, bundles, artifacts, specs, versions = _make_service()
    spec_id = _seed_ready_spec(specs, versions)

    result = service.generate("actor-1", spec_id)

    assert result["status"] == "ready"
    assert result["spec_version"] == 1
    assert len(result["artifacts"]) == len(ArtifactKind)
    stored = artifacts.list(filters={"bundle_id": result["id"]})
    assert {a["kind"] for a in stored} == {k.value for k in ArtifactKind}
    # The tasks artifact carries the structured DAG.
    tasks_art = artifacts.find_one({"bundle_id": result["id"], "kind": "tasks"})
    assert tasks_art["data"]["tasks"]


def test_generate_requires_a_succeeded_version() -> None:
    service, bundles, artifacts, specs, versions = _make_service()
    spec = specs.create({"title": "Empty", "source_text": "x", "status": "draft"})

    with pytest.raises(ValidationError):
        service.generate("actor-1", spec["id"])


def test_generate_unknown_spec_raises() -> None:
    service, *_ = _make_service()
    with pytest.raises(NotFoundError):
        service.generate("actor-1", "missing")
