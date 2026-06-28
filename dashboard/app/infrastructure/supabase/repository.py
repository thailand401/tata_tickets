"""Generic Supabase-backed repository implementing the Repository port."""

from __future__ import annotations

from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.repositories import Repository


class SupabaseRepository(Repository):
    """CRUD repository over a single Supabase table using the service client."""

    def __init__(self, client: Client, table: str) -> None:
        self._client = client
        self._table = table

    def _t(self):
        return self._client.table(self._table)

    def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        query = self._t().select("*")
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        if order_by:
            query = query.order(order_by, desc=descending)
        query = query.range(offset, offset + limit - 1)
        return query.execute().data or []

    def get(self, entity_id: str) -> dict[str, Any] | None:
        res = self._t().select("*").eq("id", entity_id).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None

    def find_one(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        query = self._t().select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        rows = query.limit(1).execute().data or []
        return rows[0] if rows else None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            res = self._t().insert(data).execute()
        except APIError as exc:
            raise self._map_error(exc) from exc
        rows = res.data or []
        if not rows:
            raise NotFoundError(f"Insert into {self._table} returned no row")
        return rows[0]

    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            res = self._t().update(data).eq("id", entity_id).execute()
        except APIError as exc:
            raise self._map_error(exc) from exc
        rows = res.data or []
        if not rows:
            raise NotFoundError(f"{self._table} id={entity_id} not found")
        return rows[0]

    def delete(self, entity_id: str) -> None:
        self._t().delete().eq("id", entity_id).execute()

    @staticmethod
    def _map_error(exc: APIError) -> Exception:
        # Postgres unique violation
        if getattr(exc, "code", None) == "23505":
            return ConflictError(exc.message or "Unique constraint violation")
        return exc
