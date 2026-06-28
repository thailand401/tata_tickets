"""Aggregate all v1 routers under a single APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.v1.routers import (
    agent_bridge,
    auth,
    monitoring,
    openspec,
    orchestration,
    prompts,
    resources,
    tech_specs,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(resources.projects_router)
api_router.include_router(resources.workspaces_router)
api_router.include_router(resources.tickets_router)
api_router.include_router(prompts.router)
api_router.include_router(tech_specs.router)
api_router.include_router(openspec.router)
api_router.include_router(orchestration.router)
api_router.include_router(agent_bridge.router)
api_router.include_router(resources.models_router)
api_router.include_router(resources.agents_router)
api_router.include_router(resources.workflows_router)
api_router.include_router(resources.roles_router)
api_router.include_router(monitoring.router)
