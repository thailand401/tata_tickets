# Changelog

All notable changes. Format based on Keep a Changelog; versioning is per phase.

## [0.1.0] — Foundation through Deploy

### Phase 1 — Foundation
- Auth (Supabase JWT), RBAC (workspace-scoped), CRUD resources, audit/event logs, monitoring. Migrations 0001–0003.

### Phase 2 — Tech Spec
- Free-text → versioned structured spec; generate/versions/compare. Migration 0004.

### Phase 3 — OpenSpec
- Spec → 6 documents (proposal, requirements, tasks DAG, architecture, migration, checklist). Migration 0005.

### Phase 4 — Orchestration
- Tasks DAG → task_runs with retry/timeout/priority/deps/parallel/resume/cancel. Migration 0006.

### Phase 5 — VS Code bridge
- Extension pulls tasks, pushes progress/log/commit/review/error/complete; polling sync.

### Phase 6 — Coding agent
- plan→code→compile→fix→commit (no push); sessions/attempts. Migration 0007.

### Phase 8 — Test generation
- 7-kind test plan from bundle (docs only). Migration 0008.

### Phase 9 — Self-heal
- compile/review/test gates loop to green then commit. Migration 0009.

### Phase 10 — Knowledge graph
- Typed nodes/edges; relevant context per run. Migration 0010.

### Phase 11 — Multi-agent fleet
- Scheduler auto-assigns specialists; seed/roster/assign/match. Migration 0011.

### Phase 12 — Deploy & operate
- CI/CD, webhooks, health, rollback, scale, backup/restore, Prometheus/Grafana. Migration 0012.

### Phase 13 — Docs & DX
- Complete `docs/` set with diagrams, API reference, runbooks.
