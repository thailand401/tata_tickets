-- =====================================================================
-- Phase 9 — Self-healing loop : schema & RLS
-- Run after: 0001 -> ... -> 0008. Idempotent.
--
-- When a task's first draft (Phase 6) fails, the agent feeds the errors back in
-- and drives one bounded loop: receive errors -> compile -> review -> test ->
-- fix -> loop -> pass -> commit -> update run state. These tables persist the
-- *session* and each gate *step* of that loop. The loop runs in the VS Code
-- extension; the server records it and, on pass, flips the run to succeeded.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type repair_session_status as enum
        ('receiving', 'compiling', 'reviewing', 'testing', 'fixing',
         'committing', 'passed', 'failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type repair_gate as enum
        ('compile', 'review', 'test', 'fix', 'commit');
exception when duplicate_object then null; end $$;

do $$ begin
    create type repair_result as enum ('pass', 'fail');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Repair sessions (one self-healing run for a task run) + steps
-- ---------------------------------------------------------------------
create table if not exists public.repair_sessions (
    id               uuid primary key default gen_random_uuid(),
    run_id           uuid not null references public.task_runs (id) on delete cascade,
    bundle_id        uuid references public.spec_bundles (id) on delete cascade,
    workspace_id     uuid references public.workspaces (id) on delete cascade,
    status           repair_session_status not null default 'receiving',
    -- the build/test errors received that opened the loop
    errors           text not null default '',
    summary          text not null default '',
    iterations_count int not null default 0,
    max_iterations   int not null default 5,
    last_error       text,
    commit_sha       text,
    created_by       uuid references public.profiles (id) on delete set null,
    started_at       timestamptz not null default now(),
    finished_at      timestamptz,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

create table if not exists public.repair_steps (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references public.repair_sessions (id) on delete cascade,
    -- 1-based iteration of the compile -> review -> test -> fix loop
    iteration   int not null default 1,
    gate        repair_gate not null,
    result      repair_result not null,
    -- captured compiler/review/test output for this step
    output      text not null default '',
    -- files written this step: [{path, action}], no source bodies stored
    files       jsonb not null default '[]'::jsonb,
    error       text,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_repair_sessions_run on public.repair_sessions (run_id);
create index if not exists idx_repair_sessions_status on public.repair_sessions (status);
create index if not exists idx_repair_steps_session on public.repair_steps (session_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
-- The self-healing loop reuses the Phase 5 `agent:bridge` permission: the same
-- worker that pulls/pushes drives the loop and records sessions. No new
-- permission is introduced.

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.repair_sessions enable row level security;
alter table public.repair_steps    enable row level security;

drop policy if exists repair_sessions_auth_read on public.repair_sessions;
create policy repair_sessions_auth_read on public.repair_sessions
    for select to authenticated using (true);

drop policy if exists repair_steps_auth_read on public.repair_steps;
create policy repair_steps_auth_read on public.repair_steps
    for select to authenticated using (true);
