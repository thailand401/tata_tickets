-- =====================================================================
-- Phase 12 — Deploy & operate : enums, deployments, backups, webhooks
-- Run after: 0001 -> ... -> 0011. Idempotent.
--
-- Ships the committed/self-healed code out: CI/CD + auto-deploy from
-- GitHub/GitLab webhooks, health checks, rollback to the last good release,
-- scale (replicas), backup/restore and metrics for Grafana. These tables are
-- the operational memory; the container roll-out itself lives in
-- docker-compose/CI. The app layer enforces RBAC; RLS is a backstop.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type deploy_status as enum
        ('pending', 'building', 'deploying', 'healthy', 'degraded', 'failed', 'rolled_back');
exception when duplicate_object then null; end $$;

do $$ begin
    create type deploy_trigger as enum
        ('manual', 'github', 'gitlab', 'auto', 'rollback');
exception when duplicate_object then null; end $$;

do $$ begin
    create type deploy_env as enum ('dev', 'staging', 'production');
exception when duplicate_object then null; end $$;

do $$ begin
    create type health_status as enum ('healthy', 'degraded', 'down');
exception when duplicate_object then null; end $$;

do $$ begin
    create type backup_kind as enum ('database', 'artifacts', 'full');
exception when duplicate_object then null; end $$;

do $$ begin
    create type backup_status as enum ('pending', 'running', 'complete', 'failed', 'restored');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Deployments (one versioned release of a bundle to an environment)
-- ---------------------------------------------------------------------
create table if not exists public.deployments (
    id           uuid primary key default gen_random_uuid(),
    workspace_id uuid references public.workspaces (id) on delete cascade,
    bundle_id    uuid references public.spec_bundles (id) on delete set null,
    environment  deploy_env not null default 'staging',
    version      text not null,
    image        text not null default '',
    commit_sha   text,
    trigger      deploy_trigger not null default 'manual',
    status       deploy_status not null default 'pending',
    replicas     int not null default 1,
    health       health_status not null default 'down',
    previous_id  uuid references public.deployments (id) on delete set null,
    summary      text not null default '',
    created_by   uuid references public.profiles (id) on delete set null,
    deployed_at  timestamptz,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Backups (database/artifacts snapshots used by restore/rollback)
-- ---------------------------------------------------------------------
create table if not exists public.backups (
    id            uuid primary key default gen_random_uuid(),
    workspace_id  uuid references public.workspaces (id) on delete cascade,
    kind          backup_kind not null default 'full',
    location      text not null default '',
    size_bytes    bigint not null default 0,
    status        backup_status not null default 'pending',
    deployment_id uuid references public.deployments (id) on delete set null,
    created_by    uuid references public.profiles (id) on delete set null,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Webhook events (normalized GitHub/GitLab pushes that may auto-deploy)
-- ---------------------------------------------------------------------
create table if not exists public.webhook_events (
    id            uuid primary key default gen_random_uuid(),
    workspace_id  uuid references public.workspaces (id) on delete cascade,
    provider      deploy_trigger not null default 'github',
    event         text not null default 'push',
    ref           text not null default '',
    commit_sha    text,
    deployment_id uuid references public.deployments (id) on delete set null,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_deployments_env on public.deployments (environment);
create index if not exists idx_deployments_status on public.deployments (status);
create index if not exists idx_backups_workspace on public.backups (workspace_id);
create index if not exists idx_webhook_events_provider on public.webhook_events (provider);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('deploy:read', 'View deployments, health and metrics'),
    ('deploy:write', 'Create deployments, run webhooks and health checks'),
    ('deploy:rollback', 'Roll back to a previous release'),
    ('deploy:scale', 'Change replica count'),
    ('deploy:backup', 'Create and restore backups')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager') and p.code like 'deploy:%'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.deployments    enable row level security;
alter table public.backups        enable row level security;
alter table public.webhook_events enable row level security;

drop policy if exists deployments_auth_read on public.deployments;
create policy deployments_auth_read on public.deployments
    for select to authenticated using (true);

drop policy if exists backups_auth_read on public.backups;
create policy backups_auth_read on public.backups
    for select to authenticated using (true);

drop policy if exists webhook_events_auth_read on public.webhook_events;
create policy webhook_events_auth_read on public.webhook_events
    for select to authenticated using (true);
