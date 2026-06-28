-- =====================================================================
-- Phase 1 — RLS policies (backstop; primary RBAC enforced in app layer)
-- Strategy:
--   * service_role (backend) bypasses RLS automatically.
--   * authenticated users get read access; writes flow through the
--     backend service key. These policies are a safety net.
-- =====================================================================

-- Enable RLS on all tables
alter table public.profiles          enable row level security;
alter table public.roles             enable row level security;
alter table public.permissions       enable row level security;
alter table public.role_permissions  enable row level security;
alter table public.projects          enable row level security;
alter table public.workspaces        enable row level security;
alter table public.user_roles        enable row level security;
alter table public.tickets           enable row level security;
alter table public.prompts           enable row level security;
alter table public.prompt_versions   enable row level security;
alter table public.models            enable row level security;
alter table public.agents            enable row level security;
alter table public.workflows         enable row level security;
alter table public.event_log         enable row level security;
alter table public.task_queue        enable row level security;
alter table public.audit_log         enable row level security;

-- Helper: a user can read their own profile; everyone authenticated can read registries.
-- Drop-and-create pattern keeps this migration idempotent.

-- profiles: a user can see/update their own row
drop policy if exists profiles_self_select on public.profiles;
create policy profiles_self_select on public.profiles
    for select to authenticated using (id = auth.uid());

drop policy if exists profiles_self_update on public.profiles;
create policy profiles_self_update on public.profiles
    for update to authenticated using (id = auth.uid());

-- Read-only access to shared registries for authenticated users
do $$
declare t text;
begin
    foreach t in array array[
        'roles','permissions','role_permissions','projects','workspaces',
        'user_roles','tickets','prompts','prompt_versions','models','agents',
        'workflows','event_log','task_queue','audit_log'
    ]
    loop
        execute format('drop policy if exists %I_auth_read on public.%I;', t, t);
        execute format(
            'create policy %I_auth_read on public.%I for select to authenticated using (true);',
            t, t
        );
    end loop;
end $$;

-- NOTE: No INSERT/UPDATE/DELETE policies are granted to `authenticated`.
-- All writes must go through the backend using the service_role key,
-- which centralizes RBAC + audit/event emission in the application layer.
