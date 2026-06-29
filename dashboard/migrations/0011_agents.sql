-- =====================================================================
-- Phase 11 — Multi-agent fleet : roles, fleet seed, permissions & RLS
-- Run after: 0001 -> ... -> 0010. Idempotent.
--
-- Staffs the orchestration lanes with a fleet of specialist agents
-- (backend, frontend, flutter, python, node, drupal, review, test, docs,
-- planner + generalist). The scheduler auto-assigns each task run to the
-- best specialist; a stack hint (flutter/dart, python, node, drupal/php)
-- beats the generic category lane.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Enum + role columns
-- ---------------------------------------------------------------------
do $$ begin
    create type agent_role as enum
        ('backend', 'frontend', 'flutter', 'python', 'node', 'drupal',
         'review', 'test', 'docs', 'planner', 'generalist');
exception when duplicate_object then null; end $$;

alter table public.agents    add column if not exists role agent_role;
alter table public.task_runs add column if not exists role agent_role;

create index if not exists idx_agents_role on public.agents (role);
create index if not exists idx_task_runs_role on public.task_runs (role);

-- ---------------------------------------------------------------------
-- Seed the specialist fleet (idempotent by slug)
-- ---------------------------------------------------------------------
insert into public.agents (name, slug, description, role, status, config) values
    ('Backend Agent',    'backend-agent',    'Services, endpoints, business logic', 'backend',    'active', '{"roles":["backend"],"stacks":["api","service","server"]}'),
    ('Frontend Agent',   'frontend-agent',   'Web UI, pages, components',           'frontend',   'active', '{"roles":["frontend"],"stacks":["web","ui","css"]}'),
    ('Flutter Agent',    'flutter-agent',    'Flutter / Dart mobile & desktop',     'flutter',    'active', '{"roles":["flutter"],"stacks":["flutter","dart","mobile"]}'),
    ('Python Agent',     'python-agent',     'Python services & scripts',           'python',     'active', '{"roles":["python"],"stacks":["python","fastapi","django"]}'),
    ('Node Agent',       'node-agent',       'Node.js / TypeScript runtimes',       'node',       'active', '{"roles":["node"],"stacks":["node","express","typescript"]}'),
    ('Drupal Agent',     'drupal-agent',     'Drupal / PHP CMS',                    'drupal',     'active', '{"roles":["drupal"],"stacks":["drupal","php","twig"]}'),
    ('Review Agent',     'review-agent',     'Code review & feedback',              'review',     'active', '{"roles":["review"],"stacks":["review","audit"]}'),
    ('Test Agent',       'test-agent',       'Test generation & QA',                'test',       'active', '{"roles":["test"],"stacks":["test","qa"]}'),
    ('Docs Agent',       'docs-agent',       'Documentation & changelogs',          'docs',       'active', '{"roles":["docs"],"stacks":["docs","readme"]}'),
    ('Planner Agent',    'planner-agent',    'Planning, breakdown, orchestration',  'planner',    'active', '{"roles":["planner"],"stacks":["plan","breakdown"]}'),
    ('Generalist Agent', 'generalist-agent', 'Fallback when no specialist matches', 'generalist', 'active', '{"roles":["generalist"],"stacks":[]}')
on conflict (slug) do update
    set role = excluded.role, description = excluded.description,
        status = excluded.status, config = excluded.config;

-- ---------------------------------------------------------------------
-- Permissions & role grants
-- ---------------------------------------------------------------------
insert into public.permissions (code, description) values
    ('fleet:manage', 'Seed and manage the specialist agent fleet'),
    ('fleet:assign', 'Auto-assign task runs to fleet specialists')
on conflict (code) do nothing;

insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name in ('admin', 'manager') and p.code like 'fleet:%'
on conflict do nothing;
