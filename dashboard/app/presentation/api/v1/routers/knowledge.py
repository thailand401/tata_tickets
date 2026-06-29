"""Knowledge-graph router (Phase 10): ingest a bundle, query relevant context.

The graph stores typed facts (api / entity / database / architecture /
business_rule / prompt / convention / history / dependency) and the edges
between them. ``/context`` returns only the relevant subgraph for a task run so
the agent never has to read the whole source.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.application.services.knowledge import KnowledgeGraphService
from app.core.security import AuthContext
from app.presentation.api.v1.dependencies import get_auth, optional_workspace
from app.presentation.api.v1.schemas import (
    KnowledgeIngest,
    KnowledgeLinkIn,
    KnowledgeNodeIn,
    KnowledgeNodeUpdate,
    KnowledgeQuery,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/bundles/{bundle_id}/ingest", status_code=201)
def ingest(
    bundle_id: str,
    body: KnowledgeIngest,
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> dict[str, Any]:
    return KnowledgeGraphService().ingest(
        auth.user_id, bundle_id, workspace_id=body.workspace_id or workspace_id
    )


@router.post("/query")
def query(body: KnowledgeQuery, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return KnowledgeGraphService().query(
        auth.user_id, text=body.text, kinds=body.kinds, bundle_id=body.bundle_id,
        workspace_id=body.workspace_id, limit=body.limit, hops=body.hops,
    )


@router.get("/tasks/{run_id}/context")
def context(
    run_id: str, limit: int = 8, hops: int = 1, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    return KnowledgeGraphService().context(auth.user_id, run_id, limit=limit, hops=hops)


@router.get("/nodes")
def list_nodes(
    auth: AuthContext = Depends(get_auth),
    workspace_id: str | None = Depends(optional_workspace),
) -> list[dict[str, Any]]:
    return KnowledgeGraphService().list(auth.user_id, workspace_id=workspace_id)


@router.post("/nodes", status_code=201)
def create_node(body: KnowledgeNodeIn, auth: AuthContext = Depends(get_auth)) -> dict:
    return KnowledgeGraphService().create(auth.user_id, body.model_dump())


@router.get("/nodes/{node_id}")
def get_node(node_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return KnowledgeGraphService().get(auth.user_id, node_id)


@router.patch("/nodes/{node_id}")
def update_node(
    node_id: str, body: KnowledgeNodeUpdate, auth: AuthContext = Depends(get_auth)
) -> dict[str, Any]:
    data = body.model_dump(exclude_none=True)
    return KnowledgeGraphService().update(auth.user_id, node_id, data)


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: str, auth: AuthContext = Depends(get_auth)) -> None:
    KnowledgeGraphService().delete(auth.user_id, node_id)


@router.post("/edges", status_code=201)
def link(body: KnowledgeLinkIn, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
    return KnowledgeGraphService().link(
        auth.user_id, body.source_id, body.target_id, kind=body.kind, weight=body.weight
    )
