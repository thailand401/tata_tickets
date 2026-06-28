"""Realtime adapter: subscribe to Postgres changes via Supabase Realtime.

Phase 1 provides a thin polling-based fallback used by monitoring views,
plus a hook for native Supabase Realtime channels. The UI uses periodic
refresh (NiceGUI timer) which is sufficient for the foundation; native
channel wiring can replace it without changing the service layer.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.supabase.client import get_service_client


def fetch_recent(table: str, limit: int = 50, order_by: str = "created_at") -> list[dict[str, Any]]:
    """Fetch the most recent rows for a monitoring view."""
    client = get_service_client()
    res = (
        client.table(table)
        .select("*")
        .order(order_by, desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []
