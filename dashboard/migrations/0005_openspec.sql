-- =====================================================================
-- Phase 3 — OpenSpec generation : schema, permissions & RLS
-- Run after: 0001 -> 0002 -> 0003 -> 0004. Idempotent.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type spec_bundle_status as enum
        ('draft', 'generating', 'ready', 'failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type artifact_kind as enum
        ('proposal', 'requirements', 'tasks', 'architecture', 'migration', 'checklist');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Spec bundles (an OpenSpec change set) + artifacts (the documents)
-- ---------------------------------------------------------------------
create table if not exists public.spec_bundles (
    id            uuid primary key default gen_random_uuid(),
    spec_id       uuid not null references public.tech_specs (id) on delete cascade,
    spec_version  int not null,
    workspace_id  uuid references public.workspaces (id) on delete cascade,
    title         text not null,
    slug          text,
    status        spec_bundle_status not null default 'draft',
    error         text,
    created_by    uuid references public.profiles (id) on delete set null,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create table if not exists public.spec_artifacts (
    id          uuid primary key default gen_random_uuid(),
    bundle_id   uuid not null references public.spec_bundles (id) on delete cascade,
    kind        artifact_kind not null,
    title       text not null,
    -- markdown document body (documentation only — never source code)
    content     text not null default '',
    -- structured payload, e.g. the task DAG for the 'tasks' artifact
    data        jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now(),
    unique (bundle_id, kind)
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_spec_bundles_spec on public.spec_bundles (spec_id);
create index if not exists idx_spec_bundles_workspace on public.spec_bundles (workspace_id);
create index if not exists idx_spec_artifacts_bundle on public.spec_artifacts (bundle_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('openspec:read',     'View OpenSpec bundles and artifacts'),
    ('openspec:write',    'Create/update OpenSpec bundles'),
    ('openspec:delete',   'Delete OpenSpec bundles'),
    ('openspec:generate', 'Generate an OpenSpec bundle from a tech spec')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager') and p.code like 'openspec:%'
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'member' and p.code = 'openspec:read'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.spec_bundles   enable row level security;
alter table public.spec_artifacts enable row level security;

drop policy if exists spec_bundles_auth_read on public.spec_bundles;
create policy spec_bundles_auth_read on public.spec_bundles
    for select to authenticated using (true);

drop policy if exists spec_artifacts_auth_read on public.spec_artifacts;
create policy spec_artifacts_auth_read on public.spec_artifacts
    for select to authenticated using (true);
