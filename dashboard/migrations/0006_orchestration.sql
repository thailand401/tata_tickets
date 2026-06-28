-- =====================================================================
-- Phase 4 — Task orchestration : schema, permissions & RLS
-- Run after: 0001 -> 0002 -> 0003 -> 0004 -> 0005. Idempotent.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type task_category as enum
        ('backend', 'frontend', 'database', 'testing', 'review', 'devops', 'documentation');
exception when duplicate_object then null; end $$;

do $$ begin
    create type run_state as enum
        ('pending', 'blocked', 'queued', 'running', 'succeeded',
         'failed', 'retrying', 'timed_out', 'cancelled', 'dead');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Task runs (orchestrated execution of one OpenSpec task) + logs
-- ---------------------------------------------------------------------
create table if not exists public.task_runs (
    id              uuid primary key default gen_random_uuid(),
    bundle_id       uuid not null references public.spec_bundles (id) on delete cascade,
    workspace_id    uuid references public.workspaces (id) on delete cascade,
    task_key        text not null,
    title           text not null default '',
    category        task_category not null,
    state           run_state not null default 'pending',
    priority        ticket_priority not null default 'medium',
    -- dependency DAG: keys of task_runs (same bundle) that must succeed first
    depends_on      jsonb not null default '[]'::jsonb,
    agent_id        uuid references public.agents (id) on delete set null,
    agent_slug      text,
    attempts        int not null default 0,
    max_attempts    int not null default 3,
    timeout_seconds int not null default 300,
    payload         jsonb not null default '{}'::jsonb,
    result          jsonb not null default '{}'::jsonb,
    last_error      text,
    claimed_by      uuid references public.profiles (id) on delete set null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (bundle_id, task_key)
);

create table if not exists public.task_logs (
    id          uuid primary key default gen_random_uuid(),
    run_id      uuid not null references public.task_runs (id) on delete cascade,
    level       text not null default 'info',
    -- log | progress | commit | review | error | state
    kind        text not null default 'log',
    message     text not null default '',
    data        jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_task_runs_bundle on public.task_runs (bundle_id);
create index if not exists idx_task_runs_state on public.task_runs (state);
create index if not exists idx_task_runs_category on public.task_runs (category);
create index if not exists idx_task_logs_run on public.task_logs (run_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('orchestration:read',    'View task runs and logs'),
    ('orchestration:write',   'Enqueue tasks for orchestration'),
    ('orchestration:execute', 'Run, resume and cancel orchestrated tasks')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager') and p.code like 'orchestration:%'
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'member' and p.code = 'orchestration:read'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- Agent bridge permission (Phase 5) — a worker pulls & pushes task updates
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('agent:bridge', 'Pull tasks and push progress/logs/commits/reviews/errors')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager', 'member') and p.code = 'agent:bridge'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.task_runs enable row level security;
alter table public.task_logs enable row level security;

drop policy if exists task_runs_auth_read on public.task_runs;
create policy task_runs_auth_read on public.task_runs
    for select to authenticated using (true);

drop policy if exists task_logs_auth_read on public.task_logs;
create policy task_logs_auth_read on public.task_logs
    for select to authenticated using (true);
