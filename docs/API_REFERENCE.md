# API Reference

Base URL: `http://localhost:8080`. All business endpoints are under `/api/v1`.
Interactive OpenAPI docs: `/docs`. Request bodies are JSON; responses are JSON
rows/objects.

## Authentication

All `/api/v1` endpoints (except `/auth/login` and `/auth/refresh`) require a
bearer token; many accept an optional workspace header.

```
Authorization: Bearer <access_token>
X-Workspace-Id: <workspace-uuid>   # optional, scopes RBAC
```

## Error responses

Errors share one shape:

```json
{ "error": { "code": "forbidden", "message": "Missing permission: spec:write" } }
```

| Code | Status | When |
|------|--------|------|
| `unauthenticated` | 401 | missing/invalid token |
| `forbidden` | 403 | missing permission |
| `not_found` | 404 | unknown id |
| `conflict` | 409 | invalid state transition |
| `validation_error` | 422 | bad body |
| `generation_failed` | 502 | LLM exhausted retries |
| `internal_error` | 500 | unexpected |

## System

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | liveness `{status:"ok"}` |
| GET | `/ready` | readiness |
| GET | `/metrics` | Prometheus text |

## Auth — `/api/v1/auth`

| Method | Path | Body | Notes |
|--------|------|------|-------|
| POST | `/auth/login` | `{email,password}` | returns access/refresh tokens + user |
| POST | `/auth/refresh` | `{refresh_token}` | new tokens |
| GET | `/auth/me` | — | current user |

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@tata.io","password":"secret"}'
```

## Resources (CRUD) — projects, workspaces, tickets, models, agents, workflows, roles

Each has `GET /{plural}`, `GET /{plural}/{id}`, `POST /{plural}`, `PATCH /{plural}/{id}`, `DELETE /{plural}/{id}`. Permission `<resource>:read|write|delete`.

```bash
curl -X POST http://localhost:8080/api/v1/tickets -H "Authorization: Bearer $T" \
  -H 'Content-Type: application/json' \
  -d '{"workspace_id":"<ws>","title":"Add export","priority":"high"}'
```

## Prompts — `/api/v1/prompts`

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/prompts` | list/create |
| GET/PATCH/DELETE | `/prompts/{id}` | read/update/delete |
| GET/POST | `/prompts/{id}/versions` | list/add version |
| POST | `/prompts/{id}/rollback` | `{version}` rollback |

## Tech Specs — `/api/v1/tech-specs`

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/tech-specs` | list/create |
| GET/PATCH/DELETE | `/tech-specs/{id}` | read/update/delete |
| POST | `/tech-specs/{id}/generate` | generate version (`model_id, prompt_id, temperature, max_attempts, notes`) |
| GET | `/tech-specs/{id}/versions` | history |
| GET | `/tech-specs/{id}/versions/{v}` | one version |
| GET | `/tech-specs/{id}/compare?a=1&b=2` | diff |

## OpenSpec — `/api/v1/openspec`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/openspec/bundles` | list |
| GET | `/openspec/bundles/{id}` | bundle + artifacts |
| GET | `/openspec/bundles/{id}/artifacts` | artifacts |
| GET | `/openspec/bundles/{id}/artifacts/{kind}` | one doc |
| GET | `/openspec/specs/{spec_id}/bundles` | bundles for spec |
| POST | `/openspec/specs/{spec_id}/generate` | `{spec_version}` → bundle |

## Orchestration — `/api/v1/orchestration`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/bundles/{id}/enqueue` | `{max_attempts,timeout_seconds}` → runs |
| POST | `/bundles/{id}/run` | `{max_parallel}` |
| POST | `/bundles/{id}/resume` | resume |
| GET | `/bundles/{id}/runs` | list runs |
| GET | `/runs/{id}` | run |
| GET | `/runs/{id}/logs?limit=200` | logs |
| POST | `/runs/{id}/cancel` | cancel |

## Agent bridge — `/api/v1/agent` (Phase 5/6)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/tasks/next` | claim next ready task (204 if none) |
| GET | `/tasks/{id}` | sync run |
| POST | `/tasks/{id}/progress` | `{percent,message,data}` |
| POST | `/tasks/{id}/log` | `{level,message,data}` |
| POST | `/tasks/{id}/commit` | `{sha,message,branch,url}` |
| POST | `/tasks/{id}/review` | `{status,summary,data}` |
| POST | `/tasks/{id}/error` | `{message,retry,data}` |
| POST | `/tasks/{id}/complete` | `{summary,result}` |
| GET | `/tasks/{id}/context` | coding context |
| POST | `/tasks/{id}/agent/session` | start session |
| GET | `/agent/sessions/{sid}` | get session |
| POST | `/agent/sessions/{sid}/plan` | record plan |
| POST | `/agent/sessions/{sid}/attempt` | record attempt |
| POST | `/agent/sessions/{sid}/finish` | finish |

## Self-heal — `/api/v1/agent` (Phase 9)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/tasks/{id}/repair/session` | `{errors,max_iterations}` |
| GET | `/repair/sessions/{sid}` | session |
| POST | `/repair/sessions/{sid}/step` | gate step |
| POST | `/repair/sessions/{sid}/finish` | `{status,commit_sha,summary}` |

## Test generation — `/api/v1/testgen`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/bundles/{id}/generate` | `{coverage_target}` |
| GET | `/bundles/{id}/plans` · `/plans/{id}` · `/plans/{id}/suites` · `/suites/{id}/cases` | read |

## Knowledge — `/api/v1/knowledge`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/bundles/{id}/ingest` | build graph |
| POST | `/query` | `{text,kinds,bundle_id,limit,hops}` |
| GET | `/tasks/{id}/context?limit=8&hops=1` | run context |
| CRUD | `/nodes`, `/nodes/{id}` | nodes |
| POST | `/edges` | link nodes |

## Fleet — `/api/v1/fleet`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/seed` | seed specialists |
| GET | `/roster` | active fleet |
| POST | `/bundles/{id}/assign` | assign specialists |
| POST | `/match` | `{title,category}` preview |

## Deploy — `/api/v1/deploy`

| Method | Path | Purpose |
|--------|------|---------|
| POST/GET | `/deployments` | deploy / list |
| POST | `/deployments/{id}/health` | `{probes}` |
| POST | `/deployments/{id}/rollback` | revert |
| POST | `/deployments/{id}/scale` | `{replicas}` (1..50) |
| POST | `/webhook` | `{provider,payload}` auto-deploy |
| POST | `/backups`, `/backups/{id}/restore` | backup/restore |
| GET | `/metrics` | counters |

## Monitoring — `/api/v1`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/events` | event log |
| GET | `/queue` | task queue |
| GET | `/audit` | audit log |
| GET | `/permissions` | catalog |
