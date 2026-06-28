-- =====================================================================
-- Phase 1 — Seed: system roles & permissions
-- =====================================================================

-- Permissions (resource:action)
insert into public.permissions (code, description) values
    ('project:read',   'View projects'),
    ('project:write',  'Create/update projects'),
    ('project:delete', 'Delete projects'),
    ('workspace:read', 'View workspaces'),
    ('workspace:write','Create/update workspaces'),
    ('workspace:delete','Delete workspaces'),
    ('ticket:read',    'View tickets'),
    ('ticket:write',   'Create/update tickets'),
    ('ticket:delete',  'Delete tickets'),
    ('prompt:read',    'View prompts'),
    ('prompt:write',   'Create/update prompts & versions'),
    ('prompt:delete',  'Delete prompts'),
    ('prompt:rollback','Roll back prompt to a previous version'),
    ('agent:read',     'View agents'),
    ('agent:write',    'Create/update agents'),
    ('agent:delete',   'Delete agents'),
    ('model:read',     'View models'),
    ('model:write',    'Create/update models'),
    ('model:delete',   'Delete models'),
    ('workflow:read',  'View workflows'),
    ('workflow:write', 'Create/update workflows'),
    ('workflow:delete','Delete workflows'),
    ('role:read',      'View roles & permissions'),
    ('role:write',     'Manage roles & permissions'),
    ('audit:read',     'View audit log'),
    ('event:read',     'View event log'),
    ('queue:read',     'View task queue')
on conflict (code) do nothing;

-- Roles
insert into public.roles (name, description, is_system) values
    ('admin',  'Full platform access', true),
    ('manager','Manage projects, workspaces, tickets and registries', true),
    ('member', 'Read-only access to most resources', true)
on conflict (name) do nothing;

-- admin -> all permissions
insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r cross join public.permissions p
where r.name = 'admin'
on conflict do nothing;

-- manager -> everything except role management
insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'manager'
  and p.code not in ('role:write')
on conflict do nothing;

-- member -> read-only permissions
insert into public.role_permissions (role_id, permission_id)
select r.id, p.id
from public.roles r join public.permissions p on true
where r.name = 'member'
  and p.code like '%:read'
on conflict do nothing;
