"""Deploy pipeline (Phase 12): pure, deterministic CI/CD & ops helpers.

Phases 6/9 ship committed, self-healed code. Phase 12 ships it *out*: a webhook
(GitHub/GitLab) or a manual trigger becomes a versioned deployment, health
checks flip it healthy/degraded, rollback reverts to the last good release,
scale changes replicas, and metrics feed Grafana. Everything here is pure and
deterministic — no I/O, no clock, no model — so the whole pipeline is testable
offline and reproducible.
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import DeployEnv, DeployTrigger, HealthStatus

# Branches that auto-deploy after green CI, mapped to their environment.
_BRANCH_ENV: dict[str, DeployEnv] = {
    "main": DeployEnv.PRODUCTION,
    "master": DeployEnv.PRODUCTION,
    "develop": DeployEnv.STAGING,
    "staging": DeployEnv.STAGING,
}


def branch_of(ref: str) -> str:
    """Strip ``refs/heads/`` (or tags) and return the short branch name."""
    return (ref or "").rsplit("/", 1)[-1]


def branch_environment(ref: str) -> DeployEnv:
    """Map a git ref to its target environment (unknown branches -> dev)."""
    return _BRANCH_ENV.get(branch_of(ref), DeployEnv.DEV)


def should_deploy(ref: str) -> bool:
    """Only deployable branches auto-deploy; feature branches never do."""
    return branch_of(ref) in _BRANCH_ENV


def parse_webhook(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a GitHub or GitLab push/release webhook to a common shape.

    Returns ``{provider, event, ref, branch, commit_sha, deployable}``. The two
    providers nest the same facts differently; this flattens them so the rest of
    the pipeline never branches on provider again.
    """
    p = (provider or "").lower()
    if p == DeployTrigger.GITLAB.value:
        ref = payload.get("ref", "")
        sha = payload.get("checkout_sha") or payload.get("after") or ""
        event = (payload.get("object_kind") or "push").replace("_", "")
    else:  # github (default)
        ref = payload.get("ref", "")
        sha = payload.get("after") or (payload.get("head_commit") or {}).get("id") or ""
        event = "release" if payload.get("release") else "push"
    return {
        "provider": p or DeployTrigger.GITHUB.value,
        "event": event,
        "ref": ref,
        "branch": branch_of(ref),
        "commit_sha": sha or None,
        "deployable": should_deploy(ref),
    }


def next_version(env: DeployEnv | str, sequence: int) -> str:
    """A monotonic, deterministic version: ``<env>-<seq>-<2-digit>`` build no.

    No timestamps, so two runs of the same sequence yield the same version.
    """
    e = env.value if isinstance(env, DeployEnv) else str(env)
    return f"{e}-{sequence + 1:04d}"


def image_tag(repo: str, version: str, commit_sha: str | None = None) -> str:
    """Container image reference for a release (short sha when available)."""
    short = (commit_sha or "")[:7]
    return f"{repo}:{version}-{short}" if short else f"{repo}:{version}"


def scale_plan(current: int, desired: int) -> dict[str, Any]:
    """Compute a scaling action without applying it (1..50 replica guardrail)."""
    target = max(1, min(int(desired), 50))
    delta = target - int(current)
    action = "up" if delta > 0 else "down" if delta < 0 else "none"
    return {"from": int(current), "to": target, "delta": delta, "action": action}


def health_summary(probes: list[dict[str, Any]] | None) -> HealthStatus:
    """Combine probe outcomes into one status (any down -> degraded/down)."""
    rows = probes or []
    if not rows:
        return HealthStatus.DOWN
    ok = sum(1 for r in rows if r.get("ok"))
    if ok == len(rows):
        return HealthStatus.HEALTHY
    return HealthStatus.DOWN if ok == 0 else HealthStatus.DEGRADED


def metrics_snapshot(
    deployments: list[dict[str, Any]], backups: list[dict[str, Any]]
) -> dict[str, int]:
    """Aggregate operational counters for the metrics endpoint / Grafana."""
    healthy = sum(1 for d in deployments if d.get("status") == "healthy")
    failed = sum(1 for d in deployments if d.get("status") == "failed")
    rolled = sum(1 for d in deployments if d.get("status") == "rolled_back")
    replicas = sum(int(d.get("replicas", 0)) for d in deployments if d.get("status") == "healthy")
    return {
        "deployments_total": len(deployments),
        "deployments_healthy": healthy,
        "deployments_failed": failed,
        "deployments_rolled_back": rolled,
        "replicas_running": replicas,
        "backups_total": len(backups),
    }


def render_prometheus(metrics: dict[str, int]) -> str:
    """Render counters in Prometheus text exposition format for scraping."""
    lines: list[str] = []
    for key, value in metrics.items():
        lines.append(f"# TYPE tata_{key} gauge")
        lines.append(f"tata_{key} {value}")
    return "\n".join(lines) + "\n"
