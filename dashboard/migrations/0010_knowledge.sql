-- =====================================================================
-- Phase 10 — Knowledge Graph : schema, permissions & RLS
-- Run after: 0001 -> ... -> 0009. Idempotent.
--
-- A typed graph of the project's facts so the agent can fetch only the
-- *relevant* context instead of reading the whole source. Nodes capture
-- api / entity / database / architecture / business_rule / prompt /
-- convention / history / dependency; edges capture how they relate
-- (depends_on, references, implements, owns, derived_from, relates_to).
-- The graph is ingested deterministically from an OpenSpec bundle.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type knowledge_kind as enum
        ('api', 'entity', 'database', 'architecture', 'business_rule',
         'prompt', 'convention', 'history', 'dependency');
exception when duplicate_object then null; end $$;

do $$ begin
    create type knowledge_edge_kind as enum
        ('depends_on', 'references', 'implements', 'owns',
         'derived_from', 'relates_to');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Nodes (one typed fact) + edges (directed relationships)
-- ---------------------------------------------------------------------
create table if not exists public.kg_nodes (
    id            uuid primary key default gen_random_uuid(),
    workspace_id  uuid references public.workspaces (id) on delete cascade,
    bundle_id     uuid references public.spec_bundles (id) on delete cascade,
    kind          knowledge_kind not null,
    -- stable, dedupe-friendly key, unique per workspace
    key           text not null,
    title         text not null,
    summary       text not null default '',
    tags          jsonb not null default '[]'::jsonb,
    -- small structured payload (not whole source bodies)
    data          jsonb not null default '{}'::jsonb,
    created_by    uuid references public.profiles (id) on delete set null,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    unique (workspace_id, key)
);

create table if not exists public.kg_edges (
    id            uuid primary key default gen_random_uuid(),
    workspace_id  uuid references public.workspaces (id) on delete cascade,
    source_id     uuid not null references public.kg_nodes (id) on delete cascade,
    target_id     uuid not null references public.kg_nodes (id) on delete cascade,
    kind          knowledge_edge_kind not null default 'relates_to',
    weight        real not null default 1.0,
    created_at    timestamptz not null default now(),
    unique (source_id, target_id, kind)
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_kg_nodes_workspace on public.kg_nodes (workspace_id);
create index if not exists idx_kg_nodes_bundle on public.kg_nodes (bundle_id);
create index if not exists idx_kg_nodes_kind on public.kg_nodes (kind);
create index if not exists idx_kg_edges_source on public.kg_edges (source_id);
create index if not exists idx_kg_edges_target on public.kg_edges (target_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('knowledge:read',   'Query the knowledge graph and fetch relevant context'),
    ('knowledge:write',  'Create/update knowledge nodes and edges'),
    ('knowledge:delete', 'Delete knowledge nodes'),
    ('knowledge:ingest', 'Ingest an OpenSpec bundle into the knowledge graph')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager') and p.code like 'knowledge:%'
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'member' and p.code = 'knowledge:read'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.kg_nodes enable row level security;
alter table public.kg_edges enable row level security;

drop policy if exists kg_nodes_auth_read on public.kg_nodes;
create policy kg_nodes_auth_read on public.kg_nodes
    for select to authenticated using (true);

drop policy if exists kg_edges_auth_read on public.kg_edges;
create policy kg_edges_auth_read on public.kg_edges
    for select to authenticated using (true);
