"""Prompt router: CRUD plus version listing, version creation and rollback."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.prompt import PromptService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth
from app.presentation.api.v1.schemas import (
    PromptCreate,
    PromptRollback,
    PromptUpdate,
    PromptVersionCreate,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("")
def list_prompts(
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth),
) -> list[dict[str, Any]]:
    return PromptService().list(auth.user_id, limit=limit, offset=offset)


@router.get("/{prompt_id}")
def get_prompt(prompt_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return PromptService().get(auth.user_id, prompt_id)


@router.post("", status_code=201)
def create_prompt(
    body: PromptCreate, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return PromptService().create(auth.user_id, body.model_dump(exclude_unset=True))


@router.patch("/{prompt_id}")
def update_prompt(
    prompt_id: str, body: PromptUpdate, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return PromptService().update(
        auth.user_id, prompt_id, body.model_dump(exclude_unset=True)
    )


@router.delete("/{prompt_id}", status_code=204)
def delete_prompt(prompt_id: str, auth: AuthContext = Depends(get_auth)) -> None:
    PromptService().delete(auth.user_id, prompt_id)


# -- versions --------------------------------------------------------------
@router.get("/{prompt_id}/versions")
def list_versions(
    prompt_id: str, auth: AuthContext = Depends(get_auth)
) -> list[dict[str, Any]]:
    return PromptService().list_versions(auth.user_id, prompt_id)


@router.post("/{prompt_id}/versions", status_code=201)
def add_version(
    prompt_id: str,
    body: PromptVersionCreate,
    auth: AuthContext = Depends(get_auth),
) -> dict[str, Any]:
    return PromptService().add_version(
        auth.user_id,
        prompt_id,
        content=body.content,
        variables=body.variables,
        notes=body.notes,
    )


@router.post("/{prompt_id}/rollback", status_code=201)
def rollback(
    prompt_id: str,
    body: PromptRollback,
    auth: AuthContext = Depends(get_auth),
) -> dict[str, Any]:
    return PromptService().rollback(auth.user_id, prompt_id, body.version)
