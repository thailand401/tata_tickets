# Project Structure

The repository has three deployable parts — the **dashboard** (Python), the
**extension** (TypeScript), and **monitoring** (Prometheus/Grafana) — plus
specs and docs. This is the canonical map of every important folder.

```text
tata_tickets/
  dashboard/          Python FastAPI + NiceGUI + Supabase  (port 8080)
  extension/          VS Code extension (TypeScript) — task bridge + agent
  monitoring/         Prometheus config + Grafana provisioning
  specs/              Phase specifications (1..12)
  docs/               This documentation set
  docker-compose.yml  dashboard + prometheus + grafana
  .github/workflows/  ci.yml (lint/type/test), cd.yml (build/deploy)
  .gitlab-ci.yml      GitLab CI/CD equivalent
```

## `dashboard/` — backend (API + UI)

```text
dashboard/
  Dockerfile           python:3.11-slim, non-root, HEALTHCHECK
  pyproject.toml       deps + ruff/mypy/pytest config
  app/
    main.py            FastAPI app: mounts REST + NiceGUI; /health /ready /metrics
    core/              settings, security (JWT), logging, exceptions
    domain/            entities, enums, ports (llm, repositories)
    application/       services + cross-cutting (rbac, recorder, retry)
      services/        tech_spec, openspec, orchestrator, agent_bridge,
                       coding_agent, self_heal, testgen, knowledge, fleet,
                       deploy, prompt, resources, monitoring, base (CRUD)
      orchestration/   classifier (lanes), scheduler (specialists), executor
      openspec/        builder (6 documents)
      knowledge/       builder (graph nodes/edges)
      testgen/         builder (test suites)
      deploy/          pipeline (CI/CD, health, scale, metrics)
    infrastructure/    auth (Supabase), realtime, llm/ (registry+stub), supabase/
    presentation/      api/v1 (routers, schemas, deps, errors) + ui/ (NiceGUI)
  migrations/          0001..0012 SQL (apply in order)
  tests/               offline pytest suite per phase
```

Mapping to other docs: services → [SERVICES.md](SERVICES.md); routers →
[API_REFERENCE.md](API_REFERENCE.md); migrations → [DATABASE.md](DATABASE.md).

## `extension/` — VS Code bridge & agent

```text
extension/
  package.json   commands, settings (tata.*), engine ^1.90
  tsconfig.json
  src/
    extension.ts  activate, command registration, status bar, secrets
    api.ts        DashboardClient — REST client, TaskRun interface
    realtime.ts   polling sync of the active task
    agent/        context, llm, apply, compile, git, agent (loop)
```

## `monitoring/`

```text
monitoring/
  prometheus.yml                 scrape config (dashboard /metrics)
  grafana/provisioning/
    datasources/                 Prometheus datasource
    dashboards/                  preloaded dashboards
```

## `specs/` and `docs/`

`specs/` holds the per-phase design specs (`overview.md`, `phase-1..12`). `docs/`
holds operational and developer documentation (this set). There is no separate
`backend/`, `agents/`, `prompts/`, `scripts/`, or `configs/` folder — those
concerns live inside `dashboard/app/` (backend, agents, prompts) and the repo
root (`docker-compose.yml`, `.github/`). The closest mappings are:

| Generic name | Where it lives here |
|--------------|---------------------|
| backend | `dashboard/app/` |
| dashboard | `dashboard/` (UI under `app/presentation/ui/`) |
| services | `dashboard/app/application/services/` |
| agents | `extension/src/agent/` + fleet in `app/application/services/fleet.py` |
| extensions | `extension/` |
| prompts | `app/application/services/prompt.py` + DB `prompts` table |
| scripts | `python -m app.main`, `pytest`, `npm` (see README) |
| docker | `dashboard/Dockerfile`, `docker-compose.yml` |
| configs | `app/core/settings.py`, `.env`, `monitoring/` |
| docs | `docs/` |
