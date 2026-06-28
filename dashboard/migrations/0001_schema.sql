-- =====================================================================
-- Phase 1 — Dashboard Foundation : Schema
-- Target: Supabase Postgres (Cloud)
-- Run order: 0001 (schema) -> 0002 (rls) -> 0003 (seed)
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type ticket_status as enum ('open', 'in_progress', 'blocked', 'done', 'cancelled');
exception when duplicate_object then null; end $$;

do $$ begin
    create type ticket_priority as enum ('low', 'medium', 'high', 'critical');
exception when duplicate_object then null; end $$;

do $$ begin
    create type registry_status as enum ('draft', 'active', 'deprecated', 'archived');
exception when duplicate_object then null; end $$;

do $$ begin
    create type task_state as enum ('pending', 'running', 'succeeded', 'failed', 'retrying', 'dead');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Identity & access
-- ---------------------------------------------------------------------

-- Mirrors auth.users (Supabase). One row per user.
create table if not exists public.profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    email        text unique not null,
    full_name    text,
    avatar_url   text,
    is_active    boolean not null default true,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create table if not exists public.roles (
    id           uuid primary key default gen_random_uuid(),
    name         text unique not null,
    description  text,
    is_system    boolean not null default false,
    created_at   timestamptz not null default now()
);

create table if not exists public.permissions (
    id           uuid primary key default gen_random_uuid(),
    -- e.g. "project:read", "ticket:write", "agent:delete"
    code         text unique not null,
    description  text,
    created_at   timestamptz not null default now()
);

create table if not exists public.role_permissions (
    role_id        uuid not null references public.roles (id) on delete cascade,
    permission_id  uuid not null references public.permissions (id) on delete cascade,
    primary key (role_id, permission_id)
);

-- ---------------------------------------------------------------------
-- Projects & workspaces
-- ---------------------------------------------------------------------
create table if not exists public.projects (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    slug         text unique not null,
    description  text,
    is_active    boolean not null default true,
    created_by   uuid references public.profiles (id) on delete set null,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create table if not exists public.workspaces (
    id           uuid primary key default gen_random_uuid(),
    project_id   uuid not null references public.projects (id) on delete cascade,
    name         text not null,
    description  text,
    created_by   uuid references public.profiles (id) on delete set null,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (project_id, name)
);

-- Workspace-scoped role assignment (RBAC scope = workspace)
create table if not exists public.user_roles (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references public.profiles (id) on delete cascade,
    role_id       uuid not null references public.roles (id) on delete cascade,
    workspace_id  uuid references public.workspaces (id) on delete cascade,
    created_at    timestamptz not null default now(),
    -- workspace_id NULL == global assignment
    unique (user_id, role_id, workspace_id)
);

-- ---------------------------------------------------------------------
-- Tickets
-- ---------------------------------------------------------------------
create table if not exists public.tickets (
    id            uuid primary key default gen_random_uuid(),
    workspace_id  uuid not null references public.workspaces (id) on delete cascade,
    title         text not null,
    description   text,
    status        ticket_status not null default 'open',
    priority      ticket_priority not null default 'medium',
    assignee_id   uuid references public.profiles (id) on delete set null,
    created_by    uuid references public.profiles (id) on delete set null,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Prompt library (with versioning)
-- ---------------------------------------------------------------------
create table if not exists public.prompts (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    slug            text unique not null,
    description     text,
    status          registry_status not null default 'draft',
    current_version int not null default 0,
    created_by      uuid references public.profiles (id) on delete set null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create table if not exists public.prompt_versions (
    id           uuid primary key default gen_random_uuid(),
    prompt_id    uuid not null references public.prompts (id) on delete cascade,
    version      int not null,
    content      text not null,
    variables    jsonb not null default '{}'::jsonb,
    notes        text,
    created_by   uuid references public.profiles (id) on delete set null,
    created_at   timestamptz not null default now(),
    unique (prompt_id, version)
);

-- ---------------------------------------------------------------------
-- Registries: models, agents, workflows
-- ---------------------------------------------------------------------
create table if not exists public.models (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    -- provider: gemini | claude | gpt | local
    provider     text not null,
    model_key    text not null,
    config       jsonb not null default '{}'::jsonb,
    status       registry_status not null default 'active',
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (provider, model_key)
);

create table if not exists public.agents (
    id             uuid primary key default gen_random_uuid(),
    name           text not null,
    slug           text unique not null,
    description    text,
    -- dynamic capability config; no hardcoded model
    config         jsonb not null default '{}'::jsonb,
    default_model_id uuid references public.models (id) on delete set null,
    status         registry_status not null default 'draft',
    created_by     uuid references public.profiles (id) on delete set null,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

create table if not exists public.workflows (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    slug         text unique not null,
    description  text,
    -- event-driven step graph definition
    definition   jsonb not null default '{}'::jsonb,
    status       registry_status not null default 'draft',
    created_by   uuid references public.profiles (id) on delete set null,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Observability: event log, task queue, audit log
-- ---------------------------------------------------------------------
create table if not exists public.event_log (
    id            uuid primary key default gen_random_uuid(),
    event_type    text not null,
    source        text,
    workspace_id  uuid references public.workspaces (id) on delete set null,
    payload       jsonb not null default '{}'::jsonb,
    created_at    timestamptz not null default now()
);

create table if not exists public.task_queue (
    id            uuid primary key default gen_random_uuid(),
    queue         text not null default 'default',
    task_type     text not null,
    state         task_state not null default 'pending',
    attempts      int not null default 0,
    max_attempts  int not null default 3,
    payload       jsonb not null default '{}'::jsonb,
    last_error    text,
    available_at  timestamptz not null default now(),
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create table if not exists public.audit_log (
    id            uuid primary key default gen_random_uuid(),
    actor_id      uuid references public.profiles (id) on delete set null,
    action        text not null,        -- create | update | delete | rollback ...
    entity_type   text not null,        -- project | ticket | prompt ...
    entity_id     uuid,
    before        jsonb,
    after         jsonb,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_workspaces_project on public.workspaces (project_id);
create index if not exists idx_user_roles_user on public.user_roles (user_id);
create index if not exists idx_user_roles_ws on public.user_roles (workspace_id);
create index if not exists idx_tickets_workspace on public.tickets (workspace_id);
create index if not exists idx_tickets_status on public.tickets (status);
create index if not exists idx_prompt_versions_prompt on public.prompt_versions (prompt_id);
create index if not exists idx_event_log_type on public.event_log (event_type);
create index if not exists idx_event_log_created on public.event_log (created_at desc);
create index if not exists idx_task_queue_state on public.task_queue (state);
create index if not exists idx_audit_entity on public.audit_log (entity_type, entity_id);
create index if not exists idx_audit_created on public.audit_log (created_at desc);
