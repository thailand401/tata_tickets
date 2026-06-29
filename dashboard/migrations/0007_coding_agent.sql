-- =====================================================================
-- Phase 6 — Autonomous coding agent : schema, permissions & RLS
-- Run after: 0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006. Idempotent.
--
-- The agent runs inside the VS Code extension. It pulls a task (Phase 5),
-- gathers context, plans, generates code, compiles, fixes in a bounded loop
-- and commits. These tables persist the *session* and each *attempt* of that
-- loop so the dashboard can show what the agent did. Review is intentionally
-- skipped (the agent commits without a review step).
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type agent_session_status as enum
        ('planning', 'coding', 'compiling', 'fixing', 'committing',
         'succeeded', 'failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type agent_attempt_phase as enum
        ('plan', 'code', 'compile', 'fix', 'commit');
exception when duplicate_object then null; end $$;

do $$ begin
    create type agent_attempt_status as enum ('pass', 'fail');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Agent sessions (one run of the agent loop for a task run) + attempts
-- ---------------------------------------------------------------------
create table if not exists public.agent_sessions (
    id              uuid primary key default gen_random_uuid(),
    run_id          uuid not null references public.task_runs (id) on delete cascade,
    bundle_id       uuid references public.spec_bundles (id) on delete cascade,
    workspace_id    uuid references public.workspaces (id) on delete cascade,
    status          agent_session_status not null default 'planning',
    -- the structured plan the agent produced before coding
    plan            jsonb not null default '{}'::jsonb,
    summary         text not null default '',
    attempts_count  int not null default 0,
    last_error      text,
    created_by      uuid references public.profiles (id) on delete set null,
    started_at      timestamptz not null default now(),
    finished_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create table if not exists public.agent_attempts (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid not null references public.agent_sessions (id) on delete cascade,
    -- 1-based iteration of the code -> compile -> fix loop
    iteration       int not null default 1,
    phase           agent_attempt_phase not null,
    status          agent_attempt_status not null,
    -- captured compiler/test output for this attempt
    compile_output  text not null default '',
    -- files written this attempt: [{path, action}], no source bodies stored
    files           jsonb not null default '[]'::jsonb,
    error           text,
    created_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_agent_sessions_run on public.agent_sessions (run_id);
create index if not exists idx_agent_sessions_status on public.agent_sessions (status);
create index if not exists idx_agent_attempts_session on public.agent_attempts (session_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
-- The coding agent reuses the Phase 5 `agent:bridge` permission: the same
-- worker that pulls/pushes also drives the agent loop and records sessions.
-- (No new permission is introduced.)

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.agent_sessions enable row level security;
alter table public.agent_attempts enable row level security;

drop policy if exists agent_sessions_auth_read on public.agent_sessions;
create policy agent_sessions_auth_read on public.agent_sessions
    for select to authenticated using (true);

drop policy if exists agent_attempts_auth_read on public.agent_attempts;
create policy agent_attempts_auth_read on public.agent_attempts
    for select to authenticated using (true);
