"""Generic CRUD router factory bound to a CrudService."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.services.base import CrudService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace


def build_crud_router(
    *,
    prefix: str,
    tag: str,
    service_factory: Callable[[], CrudService],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("")
    def list_items(
        limit: int = 100,
        offset: int = 0,
        auth: AuthContext = Depends(get_auth),
        workspace_id: str | None = Depends(optional_workspace),
    ) -> list[dict[str, Any]]:
        return service_factory().list(
            auth.user_id, limit=limit, offset=offset, workspace_id=workspace_id
        )

    @router.get("/{item_id}")
    def get_item(
        item_id: str,
        auth: AuthContext = Depends(get_auth),
        workspace_id: str | None = Depends(optional_workspace),
    ) -> dict[str, Any]:
        return service_factory().get(auth.user_id, item_id, workspace_id=workspace_id)

    @router.post("", status_code=201)
    def create_item(
        body: create_schema,  # type: ignore[valid-type]
        auth: AuthContext = Depends(get_auth),
        workspace_id: str | None = Depends(optional_workspace),
    ) -> dict[str, Any]:
        return service_factory().create(
            auth.user_id,
            body.model_dump(exclude_unset=True),
            workspace_id=workspace_id,
        )

    @router.patch("/{item_id}")
    def update_item(
        item_id: str,
        body: update_schema,  # type: ignore[valid-type]
        auth: AuthContext = Depends(get_auth),
        workspace_id: str | None = Depends(optional_workspace),
    ) -> dict[str, Any]:
        return service_factory().update(
            auth.user_id,
            item_id,
            body.model_dump(exclude_unset=True),
            workspace_id=workspace_id,
        )

    @router.delete("/{item_id}", status_code=204)
    def delete_item(
        item_id: str,
        auth: AuthContext = Depends(get_auth),
        workspace_id: str | None = Depends(optional_workspace),
    ) -> None:
        service_factory().delete(auth.user_id, item_id, workspace_id=workspace_id)

    return router
