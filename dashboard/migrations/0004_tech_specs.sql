-- =====================================================================
-- Phase 2 — Tech Spec Generation : schema, permissions & RLS
-- Run after: 0001 -> 0002 -> 0003. Idempotent.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type spec_status as enum
        ('draft', 'generating', 'ready', 'failed', 'approved', 'rejected');
exception when duplicate_object then null; end $$;

do $$ begin
    create type generation_status as enum ('pending', 'succeeded', 'failed');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Tech specs (free-text source) + versions (immutable generation history)
-- ---------------------------------------------------------------------
create table if not exists public.tech_specs (
    id               uuid primary key default gen_random_uuid(),
    workspace_id     uuid references public.workspaces (id) on delete cascade,
    ticket_id        uuid references public.tickets (id) on delete set null,
    title            text not null,
    -- the raw free-text ticket the AI analyzes
    source_text      text not null,
    status           spec_status not null default 'draft',
    current_version  int not null default 0,
    -- versioned prompt template used for generation (nullable = built-in default)
    prompt_id        uuid references public.prompts (id) on delete set null,
    -- model chosen dynamically per task (no hardcoded model)
    model_id         uuid references public.models (id) on delete set null,
    created_by       uuid references public.profiles (id) on delete set null,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create table if not exists public.tech_spec_versions (
    id               uuid primary key default gen_random_uuid(),
    spec_id          uuid not null references public.tech_specs (id) on delete cascade,
    version          int not null,
    status           generation_status not null default 'pending',
    -- structured Tech Spec document (feature, business_goal, api, ...): docs only
    content          jsonb not null default '{}'::jsonb,
    raw_output       text,
    model_id         uuid references public.models (id) on delete set null,
    model_key        text,
    provider         text,
    prompt_id        uuid references public.prompts (id) on delete set null,
    prompt_version   int,
    attempts         int not null default 1,
    error            text,
    notes            text,
    created_by       uuid references public.profiles (id) on delete set null,
    created_at       timestamptz not null default now(),
    unique (spec_id, version)
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_tech_specs_workspace on public.tech_specs (workspace_id);
create index if not exists idx_tech_specs_status on public.tech_specs (status);
create index if not exists idx_tech_spec_versions_spec
    on public.tech_spec_versions (spec_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('spec:read',     'View tech specs and their versions'),
    ('spec:write',    'Create/update tech specs'),
    ('spec:delete',   'Delete tech specs'),
    ('spec:generate', 'Run AI analysis to generate a tech spec version')
on conflict (code) do nothing;

-- admin -> all spec permissions
insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'admin' and p.code like 'spec:%'
on conflict do nothing;

-- manager -> all spec permissions
insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'manager' and p.code like 'spec:%'
on conflict do nothing;

-- member -> read-only
insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'member' and p.code = 'spec:read'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.tech_specs          enable row level security;
alter table public.tech_spec_versions  enable row level security;

drop policy if exists tech_specs_auth_read on public.tech_specs;
create policy tech_specs_auth_read on public.tech_specs
    for select to authenticated using (true);

drop policy if exists tech_spec_versions_auth_read on public.tech_spec_versions;
create policy tech_spec_versions_auth_read on public.tech_spec_versions
    for select to authenticated using (true);
