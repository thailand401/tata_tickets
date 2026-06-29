# Workflow

The end-to-end pipeline turns a free-text ticket into deployed, self-healed code.
Every stage is offline-capable (stub LLM / stub executor) and fully audited.

## Full pipeline

```mermaid
flowchart TD
    A[Ticket: free text] -->|POST tech-specs + generate| B[Tech Spec<br/>structured, versioned]
    B -->|POST openspec generate| C[OpenSpec bundle<br/>proposal/requirements/tasks/<br/>architecture/migration/checklist]
    C -->|POST orchestration enqueue| D[task_runs DAG]
    D -->|fleet assign| E[specialist agents]
    E -->|extension pull| F[VS Code worker]
    F -->|run agent| G[plan -> code -> compile -> fix -> commit]
    G -->|errors?| H[self-heal: gates -> green]
    H -->|complete| I[run SUCCEEDED]
    C -->|testgen generate| J[test plan]
    C -->|knowledge ingest| K[knowledge graph]
    I -->|deploy| L[dev/staging/prod]
```

## Step by step

1. **Create a ticket** — `POST /api/v1/tickets`.
2. **Generate Tech Spec** — `POST /tech-specs` then `POST /tech-specs/{id}/generate` (versioned, status `ready`).
3. **Generate OpenSpec** — `POST /openspec/specs/{spec_id}/generate` → 6 artifacts.
4. **Ingest knowledge** — `POST /knowledge/bundles/{id}/ingest` for relevant context.
5. **Generate tests** — `POST /testgen/bundles/{id}/generate` (documentation).
6. **Enqueue** — `POST /orchestration/bundles/{id}/enqueue` → `task_runs` with classification.
7. **Assign fleet** — `POST /fleet/bundles/{id}/assign` to specialists.
8. **Bridge** — extension `Pull Next Task`, then `Run Autonomous Agent`.
9. **Agent loop** — plan/code/compile/fix/commit; pushes progress/log/commit.
10. **Self-heal** — on failure, gates loop to green then commit; run → `succeeded`.
11. **Deploy** — manual or webhook auto-deploy; health/rollback/scale.

## Run state machine

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> blocked: deps unmet
    pending --> queued: ready
    blocked --> queued: deps done
    queued --> running: claimed
    running --> succeeded
    running --> failed
    failed --> retrying
    retrying --> running
    running --> timed_out
    failed --> dead: retries exhausted
    queued --> cancelled
    succeeded --> [*]
    dead --> [*]
    cancelled --> [*]
```

## Agent loop & self-heal

```mermaid
flowchart LR
    P[plan] --> C[code] --> B[compile]
    B -->|fail| X[fix] --> B
    B -->|pass| T[test]
    T -->|fail| X
    T -->|pass| M[commit]
    M --> S[SUCCEEDED]
```

Continue with [AGENTS.md](AGENTS.md) for agent details and
[API_REFERENCE.md](API_REFERENCE.md) for the exact calls.
