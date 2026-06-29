"""Phase 12 tests: deploy & operate — CI/CD, webhooks, health, rollback, scale."""

from __future__ import annotations

import pytest

from app.application.deploy.pipeline import (
    branch_environment,
    health_summary,
    image_tag,
    metrics_snapshot,
    next_version,
    parse_webhook,
    render_prometheus,
    scale_plan,
    should_deploy,
)
from app.application.services.deploy import DeployService
from app.core.exceptions import NotFoundError, OrchestrationError
from app.domain.enums import DeployEnv, DeployStatus, HealthStatus
from tests.fakes import FakeRepository


@pytest.fixture(autouse=True)
def _allow_and_silence(monkeypatch):
    monkeypatch.setattr("app.application.rbac.rbac.require", lambda *a, **k: None)
    monkeypatch.setattr("app.application.services.deploy.record_audit", lambda **k: None)
    monkeypatch.setattr("app.application.services.deploy.record_event", lambda **k: None)


def _make():
    deps, backups, hooks = FakeRepository(), FakeRepository(), FakeRepository()
    return DeployService(deps, backups=backups, webhooks=hooks), deps, backups, hooks


# -- pipeline: pure & deterministic ----------------------------------------
def test_branch_environment_and_deployable() -> None:
    assert branch_environment("refs/heads/main") is DeployEnv.PRODUCTION
    assert branch_environment("refs/heads/develop") is DeployEnv.STAGING
    assert branch_environment("refs/heads/feature/x") is DeployEnv.DEV
    assert should_deploy("refs/heads/main") and not should_deploy("refs/heads/feature/x")


def test_next_version_is_deterministic() -> None:
    assert next_version(DeployEnv.PRODUCTION, 0) == "production-0001"
    assert next_version(DeployEnv.PRODUCTION, 0) == next_version("production", 0)


def test_image_tag_uses_short_sha() -> None:
    assert image_tag("repo", "staging-0001", "abcdef1234") == "repo:staging-0001-abcdef1"
    assert image_tag("repo", "staging-0001") == "repo:staging-0001"


def test_parse_webhook_github_and_gitlab() -> None:
    gh = parse_webhook("github", {"ref": "refs/heads/main", "after": "deadbeef"})
    assert gh["branch"] == "main" and gh["commit_sha"] == "deadbeef" and gh["deployable"]
    gl = parse_webhook("gitlab", {"ref": "refs/heads/develop", "checkout_sha": "cafe"})
    assert gl["provider"] == "gitlab" and gl["branch"] == "develop" and gl["deployable"]


def test_scale_plan_clamps_and_directions() -> None:
    assert scale_plan(1, 3)["action"] == "up" and scale_plan(3, 1)["action"] == "down"
    assert scale_plan(2, 2)["action"] == "none"
    assert scale_plan(1, 999)["to"] == 50 and scale_plan(1, 0)["to"] == 1


def test_health_summary_and_metrics_render() -> None:
    assert health_summary([{"ok": True}, {"ok": True}]) is HealthStatus.HEALTHY
    assert health_summary([{"ok": True}, {"ok": False}]) is HealthStatus.DEGRADED
    assert health_summary([]) is HealthStatus.DOWN
    text = render_prometheus(metrics_snapshot([{"status": "healthy", "replicas": 2}], []))
    assert "tata_deployments_healthy 1" in text and "tata_replicas_running 2" in text


# -- service: deploy / health / rollback / scale ---------------------------
def test_deploy_creates_versioned_deployment() -> None:
    service, deps, *_ = _make()
    d = service.deploy("u", environment="production", commit_sha="abc1234")
    assert d["version"] == "production-0001" and d["status"] == DeployStatus.DEPLOYING.value
    assert deps.get(d["id"]) is not None


def test_health_check_flips_status() -> None:
    service, *_ = _make()
    d = service.deploy("u", environment="staging")
    ok = service.health_check("u", d["id"], probes=[{"ok": True}])
    assert ok["status"] == DeployStatus.HEALTHY.value
    bad = service.health_check("u", d["id"], probes=[{"ok": False}])
    assert bad["status"] == DeployStatus.DEGRADED.value


def test_rollback_reverts_to_previous_healthy() -> None:
    service, *_ = _make()
    first = service.deploy("u", environment="production")
    service.health_check("u", first["id"], probes=[{"ok": True}])
    second = service.deploy("u", environment="production")
    restored = service.rollback("u", second["id"])
    assert restored["id"] == first["id"] and restored["status"] == DeployStatus.HEALTHY.value


def test_rollback_without_history_errors() -> None:
    service, *_ = _make()
    only = service.deploy("u", environment="dev")
    with pytest.raises(OrchestrationError):
        service.rollback("u", only["id"])


def test_scale_changes_replicas() -> None:
    service, *_ = _make()
    d = service.deploy("u")
    out = service.scale("u", d["id"], replicas=4)
    assert out["deployment"]["replicas"] == 4 and out["plan"]["action"] == "up"


def test_webhook_auto_deploys_main_only() -> None:
    service, deps, _, hooks = _make()
    res = service.handle_webhook("u", provider="github",
                                 payload={"ref": "refs/heads/main", "after": "sha1"})
    assert res["deployment"] is not None
    feat = service.handle_webhook("u", provider="github",
                                  payload={"ref": "refs/heads/feature", "after": "sha2"})
    assert feat["deployment"] is None
    assert len(hooks.list()) == 2


def test_backup_restore_and_metrics() -> None:
    service, *_ = _make()
    service.deploy("u")
    b = service.backup("u", kind="database")
    assert b["status"] == "complete"
    assert service.restore("u", b["id"])["status"] == "restored"
    with pytest.raises(NotFoundError):
        service.restore("u", "missing")
    assert service.metrics("u")["deployments_total"] == 1
