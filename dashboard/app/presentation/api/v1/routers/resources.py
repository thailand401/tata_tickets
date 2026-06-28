"""CRUD routers for the standard resources (projects, workspaces, etc.)."""

from __future__ import annotations

from app.application.services.resources import (
    AgentService,
    ModelService,
    ProjectService,
    RoleService,
    TicketService,
    WorkflowService,
    WorkspaceService,
)
from app.presentation.api.v1.routers.crud_factory import build_crud_router
from app.presentation.api.v1.schemas import (
    AgentCreate,
    AgentUpdate,
    ModelCreate,
    ModelUpdate,
    ProjectCreate,
    ProjectUpdate,
    RoleCreate,
    RoleUpdate,
    TicketCreate,
    TicketUpdate,
    WorkflowCreate,
    WorkflowUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)

projects_router = build_crud_router(
    prefix="/projects",
    tag="projects",
    service_factory=ProjectService,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
)

workspaces_router = build_crud_router(
    prefix="/workspaces",
    tag="workspaces",
    service_factory=WorkspaceService,
    create_schema=WorkspaceCreate,
    update_schema=WorkspaceUpdate,
)

tickets_router = build_crud_router(
    prefix="/tickets",
    tag="tickets",
    service_factory=TicketService,
    create_schema=TicketCreate,
    update_schema=TicketUpdate,
)

models_router = build_crud_router(
    prefix="/models",
    tag="models",
    service_factory=ModelService,
    create_schema=ModelCreate,
    update_schema=ModelUpdate,
)

agents_router = build_crud_router(
    prefix="/agents",
    tag="agents",
    service_factory=AgentService,
    create_schema=AgentCreate,
    update_schema=AgentUpdate,
)

workflows_router = build_crud_router(
    prefix="/workflows",
    tag="workflows",
    service_factory=WorkflowService,
    create_schema=WorkflowCreate,
    update_schema=WorkflowUpdate,
)

roles_router = build_crud_router(
    prefix="/roles",
    tag="roles",
    service_factory=RoleService,
    create_schema=RoleCreate,
    update_schema=RoleUpdate,
)
