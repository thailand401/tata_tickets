"""Audit-log and event-log emitters (write-side observability)."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.infrastructure.supabase.client import get_service_client

log = get_logger("recorder")


def _json_safe(value: Any) -> Any:
    """Best-effort conversion of values to JSON-serializable form."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def record_audit(
    *,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Persist an audit-log entry. Failures are logged, never raised."""
    try:
        get_service_client().table("audit_log").insert(
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "before": _json_safe(before),
                "after": _json_safe(after),
            }
        ).execute()
    except Exception as exc:  # observability must not break the request
        log.error("audit_write_failed", error=str(exc), entity_type=entity_type)


def record_event(
    *,
    event_type: str,
    source: str | None = None,
    workspace_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Persist an event-log entry. Failures are logged, never raised."""
    try:
        get_service_client().table("event_log").insert(
            {
                "event_type": event_type,
                "source": source,
                "workspace_id": workspace_id,
                "payload": _json_safe(payload or {}),
            }
        ).execute()
    except Exception as exc:
        log.error("event_write_failed", error=str(exc), event_type=event_type)
