"""Repository ports (abstract interfaces). Infrastructure provides implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Repository(ABC):
    """Generic CRUD port over a single table-backed resource.

    Implementations return/accept plain dicts; the application layer maps
    these to domain entities. This keeps the port free of any concrete
    serialization framework.
    """

    @abstractmethod
    def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get(self, entity_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def delete(self, entity_id: str) -> None:
        ...

    @abstractmethod
    def find_one(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        ...
