"""Aggregate all v1 routers under a single APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.v1.routers import (
    agent_bridge,
    auth,
    deploy,
    fleet,
    knowledge,
    monitoring,
    openspec,
    orchestration,
    prompts,
    resources,
    self_heal,
    tech_specs,
    testgen,
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
api_router.include_router(self_heal.router)
api_router.include_router(testgen.router)
api_router.include_router(knowledge.router)
api_router.include_router(fleet.router)
api_router.include_router(deploy.router)
api_router.include_router(resources.models_router)
api_router.include_router(resources.agents_router)
api_router.include_router(resources.workflows_router)
api_router.include_router(resources.roles_router)
api_router.include_router(monitoring.router)
