"""In-memory fake repository for service-layer tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.domain.repositories import Repository


class FakeRepository(Repository):
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        rows = list(self._store.values())
        for k, v in (filters or {}).items():
            rows = [r for r in rows if r.get(k) == v]
        if order_by is not None:
            rows.sort(
                key=lambda r: (r.get(order_by) is None, r.get(order_by)),
                reverse=descending,
            )
        return rows[offset : offset + limit]

    def get(self, entity_id: str) -> dict[str, Any] | None:
        return self._store.get(entity_id)

    def find_one(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        for r in self._store.values():
            if all(r.get(k) == v for k, v in filters.items()):
                return r
        return None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        row = dict(data)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._store[row["id"]] = row
        return row

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self._store[entity_id]
        row.update(data)
        return row

    def delete(self, entity_id: str) -> None:
        self._store.pop(entity_id, None)
