# Services

Tata runs as **one process** (the dashboard) hosting the REST API and NiceGUI UI,
plus two optional containers (Prometheus, Grafana) and the VS Code extension
worker. Within the backend, "services" are application-layer classes, all sharing
the same lifecycle (started/stopped with the dashboard process).

## Process map

| Service | Port | Health | Start | Stop / Restart | Logs |
|---------|------|--------|-------|----------------|------|
| Dashboard (API+UI) | 8080 | `/health`, `/ready` | `python -m app.main` | Ctrl-C / re-run | stdout (structlog) |
| Prometheus | 9090 | `/-/healthy` | `docker compose up prometheus` | `docker compose restart prometheus` | `docker logs tata_prometheus` |
| Grafana | 3000 | `/api/health` | `docker compose up grafana` | `docker compose restart grafana` | `docker logs tata_grafana` |
| VS Code worker | — | extension status bar | `F5` / **Tata: Login** | close host | VS Code Output channel |

In Docker: `docker compose up`, `docker compose stop`, `docker compose restart dashboard`.

---

## Dashboard

- **Purpose** — Serve REST API (`/api/v1`) and the NiceGUI UI in one process.
- **Responsibilities** — auth, RBAC, CRUD, spec/openspec/orchestration, bridge, deploy, metrics.
- **Dependencies** — Supabase (Postgres + Auth); optional Prometheus/Grafana.
- **Port** — 8080.
- **Env** — `SUPABASE_*`, `APP_*`, `LOG_LEVEL`, `CORS_ORIGINS` ([ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)).
- **Health** — `GET /health` (live), `GET /ready` (ready), `GET /metrics` (Prometheus).
- **Start/Stop/Restart** — `python -m app.main` / Ctrl-C / re-run (or `docker compose ... dashboard`).
- **Logs** — structured JSON on stdout.

## Application services (in-process)

Each is a class under `app/application/services/`; all guard with RBAC and emit audit/events.

| Service | Purpose | Permission |
|---------|---------|-----------|
| `CrudService` (base) | generic CRUD + RBAC + audit/event | `<resource>:read/write/delete` |
| `TechSpecService` | free-text → versioned Tech Spec | `spec:read/write/generate` |
| `OpenSpecService` | Tech Spec → 6-doc bundle | `openspec:read/generate` |
| `OrchestratorService` | enqueue/run/resume/cancel task runs | `orchestration:read/write` |
| `AgentBridgeService` | pull task, push progress/log/commit/review/error/complete | `agent:bridge` |
| `CodingAgentService` | context + session/attempt persistence | `agent:bridge` |
| `RepairService` | self-heal sessions/steps → commit | `agent:bridge` |
| `TestGenService` | bundle → test plan | `testgen:read/write/generate` |
| `KnowledgeGraphService` | ingest/query graph, run context | `knowledge:read/write/ingest` |
| `AgentFleetService` | seed specialists, assign, roster, match | `fleet:manage/assign` |
| `DeployService` | deploy/health/rollback/scale/backup/restore | `deploy:read/write/rollback/scale/backup` |
| `PromptService` | versioned prompt library | `prompt:read/write/rollback` |
| `MonitoringService` | event/queue/audit reads | `event:read/queue:read/audit:read` |

## Prometheus

- **Purpose** — scrape `tata_*` metrics from the dashboard. **Port** 9090.
- **Config** — `monitoring/prometheus.yml`. **Health** — `/-/healthy`.

## Grafana

- **Purpose** — visualise metrics. **Port** 3000. **Health** — `/api/health`.
- **Env** — `GRAFANA_PASSWORD`. Provisioned from `monitoring/grafana/provisioning`.

## VS Code worker

- **Purpose** — pull tasks, run the coding agent, push results. **Health** — status bar.
- **Env (settings)** — `tata.dashboardUrl`, `tata.workspaceId`, `tata.compileCommand`, etc. See [AGENTS.md](AGENTS.md).
