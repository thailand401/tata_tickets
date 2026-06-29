-- =====================================================================
-- Phase 8 — Test generation : schema, permissions & RLS
-- Run after: 0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007. Idempotent.
--
-- A ready OpenSpec bundle is turned into a structured test plan: suites for
-- every kind (unit, integration, api, regression, edge case, mock, benchmark),
-- each with planned cases, plus a coverage target and a rendered report.
-- Documentation only — never executable source code.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------
do $$ begin
    create type test_plan_status as enum ('draft', 'generating', 'ready', 'failed');
exception when duplicate_object then null; end $$;

do $$ begin
    create type test_kind as enum
        ('unit', 'integration', 'api', 'regression', 'edge_case', 'mock', 'benchmark');
exception when duplicate_object then null; end $$;

do $$ begin
    create type test_case_status as enum ('planned', 'generated', 'skipped');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------
-- Test plans (one per generation) + suites + cases
-- ---------------------------------------------------------------------
create table if not exists public.test_plans (
    id              uuid primary key default gen_random_uuid(),
    bundle_id       uuid not null references public.spec_bundles (id) on delete cascade,
    workspace_id    uuid references public.workspaces (id) on delete cascade,
    title           text not null,
    slug            text,
    status          test_plan_status not null default 'draft',
    coverage_target int not null default 80,
    suite_count     int not null default 0,
    case_count      int not null default 0,
    -- rendered markdown report (documentation only)
    report          text not null default '',
    error           text,
    created_by      uuid references public.profiles (id) on delete set null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create table if not exists public.test_suites (
    id          uuid primary key default gen_random_uuid(),
    plan_id     uuid not null references public.test_plans (id) on delete cascade,
    kind        test_kind not null,
    title       text not null,
    framework   text not null default '',
    summary     text not null default '',
    -- mocked dependencies for this suite
    mocks       jsonb not null default '[]'::jsonb,
    -- structured payload (e.g. benchmark budgets)
    data        jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now(),
    unique (plan_id, kind)
);

create table if not exists public.test_cases (
    id          uuid primary key default gen_random_uuid(),
    suite_id    uuid not null references public.test_suites (id) on delete cascade,
    plan_id     uuid not null references public.test_plans (id) on delete cascade,
    name        text not null,
    given       text not null default '',
    "when"      text not null default '',
    then        text not null default '',
    kind        test_kind not null default 'unit',
    status      test_case_status not null default 'planned',
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
create index if not exists idx_test_plans_bundle on public.test_plans (bundle_id);
create index if not exists idx_test_plans_workspace on public.test_plans (workspace_id);
create index if not exists idx_test_suites_plan on public.test_suites (plan_id);
create index if not exists idx_test_cases_suite on public.test_cases (suite_id);
create index if not exists idx_test_cases_plan on public.test_cases (plan_id);

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('testgen:read',     'View generated test plans, suites and reports'),
    ('testgen:write',    'Create/update test plans'),
    ('testgen:delete',   'Delete test plans'),
    ('testgen:generate', 'Generate a test plan from an OpenSpec bundle')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager') and p.code like 'testgen:%'
on conflict do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'member' and p.code = 'testgen:read'
on conflict do nothing;

-- ---------------------------------------------------------------------
-- RLS (backstop; primary RBAC enforced in app layer via service_role)
-- ---------------------------------------------------------------------
alter table public.test_plans  enable row level security;
alter table public.test_suites enable row level security;
alter table public.test_cases  enable row level security;

drop policy if exists test_plans_auth_read on public.test_plans;
create policy test_plans_auth_read on public.test_plans
    for select to authenticated using (true);

drop policy if exists test_suites_auth_read on public.test_suites;
create policy test_suites_auth_read on public.test_suites
    for select to authenticated using (true);

drop policy if exists test_cases_auth_read on public.test_cases;
create policy test_cases_auth_read on public.test_cases
    for select to authenticated using (true);
