# Tata Dashboard — AI Software Factory (Phase 1: Foundation)

Central management dashboard for the AI Software Factory platform. **Phase 1
delivers the foundation only — no AI logic.** It provides authentication,
RBAC, resource registries, CRUD, prompt versioning, and monitoring shells.

## Stack

| Concern        | Choice                                              |
|----------------|-----------------------------------------------------|
| Backend / API  | FastAPI (async REST + OpenAPI)                      |
| UI             | NiceGUI (pure Python, responsive, dark mode)        |
| Database       | Supabase Postgres (Cloud)                           |
| Auth           | Supabase Auth (JWT, verified server-side)           |
| Realtime       | Supabase Realtime + UI polling fallback             |
| Architecture   | Clean Architecture (domain/application/infra/presentation) |

## Architecture layers

```
app/
  core/            settings, logging, security (JWT), exceptions
  domain/          entities, enums, repository ports (no infra deps)
  application/     services (use cases), rbac, audit/event recorder
  infrastructure/  supabase client + repositories, auth, realtime
  presentation/
    api/v1/        FastAPI routers, schemas, dependencies, errors
    ui/            NiceGUI pages, theme, api client, session state
  main.py          mounts REST API + NiceGUI in one process
migrations/        SQL schema, RLS, seed
tests/             pytest (security, RBAC, services)
```

**Rule:** dependencies point inward. `domain` knows nothing about Supabase or
FastAPI. All writes flow through the application layer, which enforces RBAC and
emits audit + event records automatically.

## Setup

1. **Create a virtualenv & install:**
   ```bash
   cd dashboard
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   pip install -e ".[dev]"
   ```

2. **Configure environment:** copy `.env.example` to `.env` and fill in:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY` (service_role — **server only, keep secret**)
   - `SUPABASE_ANON_KEY` (used by the login flow)
   - `SUPABASE_JWT_SECRET` (Supabase → Settings → API → JWT Secret)

3. **Apply database migrations** in the Supabase SQL editor, in order:
   `migrations/0001_schema.sql`, `0002_rls.sql`, `0003_seed.sql`.

4. **Create a user** in Supabase Auth, then assign a role via the
   `user_roles` table (e.g. the seeded `admin` role) so RBAC grants access.

## Run

```bash
python -m app.main
```

- Dashboard UI: http://localhost:8080/
- REST API docs (OpenAPI): http://localhost:8080/docs
- Health check: http://localhost:8080/health

### Docker

```bash
docker compose up --build
```

## Tests

```bash
cd dashboard
pytest
```

Tests run fully offline (no live Supabase needed): JWT verification, the RBAC
engine, and CrudService orchestration (RBAC + audit/event emission) use fakes.

## REST API surface (v1)

- `POST /api/v1/auth/login`, `/auth/refresh`, `GET /auth/me`
- CRUD: `/projects`, `/workspaces`, `/tickets`, `/agents`, `/models`,
  `/workflows`, `/roles`
- Prompts: `/prompts` (+ `/{id}/versions`, `/{id}/rollback`)
- Monitoring: `/events`, `/queue`, `/audit`, `/permissions`

All endpoints (except login/refresh) require a `Bearer` access token.
Optional `X-Workspace-Id` header scopes RBAC to a workspace.

## Phase 2 — Tech Spec Generation

Phase 2 adds an AI step that turns a **free-text ticket** into a **standard
Tech Spec document** (documentation only — never source code). Generation is
versioned (full history), retries on transient failures, and any two versions
can be compared.

**Pipeline:** free text → model-agnostic LLM (`LLMClient` port) using a
versioned prompt template → validated structured spec → stored as an immutable
version.

**Standard spec fields:** `feature`, `business_goal`, `functional_requirements`,
`non_functional`, `api`, `database`, `acceptance_criteria`, `risks`,
`dependencies`, `estimate`, `priority`.

**REST surface:**

- CRUD: `/tech-specs` (+ `/{id}`)
- `POST /tech-specs/{id}/generate` — run AI analysis (call again to retry; each
  call is a new version). Internally retries transient LLM errors.
- `GET /tech-specs/{id}/versions`, `/{id}/versions/{version}` — history
- `GET /tech-specs/{id}/compare?a=&b=` — field-by-field version diff

**Model-agnostic LLM:** providers register via
`app/infrastructure/llm` (`register_provider`); no model is hardcoded. The
default is an offline deterministic `StubLLMClient`, so the pipeline runs and is
tested without external API keys. A real provider replaces it by config only.

**Prompt versioning:** a spec's `prompt_id` binds to the existing prompt library
(`prompts` + `prompt_versions`); its current version is used as the system
prompt. With no prompt bound, a built-in default template is used.

Apply migration `migrations/0004_tech_specs.sql` (adds `tech_specs`,
`tech_spec_versions`, the `spec:*` permissions, and RLS).

## Phase 3 — OpenSpec Generation

Turns a **ready Tech Spec version** into a standard **OpenSpec change bundle**
(documentation only): `proposal`, `requirements`, `tasks`, `architecture`,
`migration`, `checklist`. The `tasks` artifact is a structured dependency DAG
consumed by Phase 4. Deterministic builder (`app/application/openspec/`), so the
pipeline runs and tests offline. Apply `migrations/0005_openspec.sql`.

- `POST /api/v1/openspec/specs/{spec_id}/generate` — generate a bundle
- `GET /api/v1/openspec/bundles/{id}` — bundle + artifacts

## Phase 4 — Task Orchestration

Reads the OpenSpec `tasks` DAG, **classifies** each task (backend, frontend,
database, testing, review, devops, documentation), **auto-selects an agent**,
and schedules runs with **queue, retry, timeout, priority, dependency, parallel,
resume, cancel and logging**. The `TaskExecutor` port delegates the actual work
(offline `StubTaskExecutor` by default). Apply `migrations/0006_orchestration.sql`.

- `POST /api/v1/orchestration/bundles/{id}/enqueue` | `/run` | `/resume`
- `POST /api/v1/orchestration/runs/{id}/cancel`, `GET .../runs/{id}/logs`

## Phase 5 — VS Code Bridge

A bridge (no ticket management) between the dashboard and the editor. A worker
**pulls** the next ready task and **pushes** progress, logs, commits, reviews,
errors and completion, with polling-based realtime sync. Server:
`/api/v1/agent/*` (`agent:bridge` permission). Client: the TypeScript extension
in `../extension/`.

- `POST /api/v1/agent/tasks/next` — pull & claim
- `POST /api/v1/agent/tasks/{id}/{progress|log|commit|review|error|complete}`
- `GET /api/v1/agent/tasks/{id}` — realtime sync read

Full specifications live in [`../specs/`](../specs/README.md).

## Out of scope (later phases)

Node.js AI tool services and a distributed queue worker fleet. Phases 4–5
orchestrate and bridge tasks; running heavy tooling as independent Node.js
services remains future work.
