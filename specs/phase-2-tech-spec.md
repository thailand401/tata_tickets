# Phase 2 — Tech Spec Generation

## Goal

Turn a **free-text ticket** into a **structured, versioned Tech Spec** via AI
analysis. The output is **documentation only — never source code**. Generation
keeps full history, uses a versioned prompt template, retries on transient LLM
failures, and supports comparing any two versions.

### Structured Tech Spec contract (`TechSpecContent`)

The LLM must return a single JSON object with exactly these keys:

| Field | Type |
|-------|------|
| `feature` | string |
| `business_goal` | string |
| `functional_requirements` | string[] |
| `non_functional` | string[] |
| `api` | string[] |
| `database` | string[] |
| `acceptance_criteria` | string[] |
| `risks` | string[] |
| `dependencies` | string[] |
| `estimate` | string |
| `priority` | one of `low` / `medium` / `high` / `critical` |

The response is parsed (`parse_spec_content`), code fences stripped, and
validated against `TechSpecContent`; a non-conforming response raises
`ValidationError`.

## Design

```
tickets / free text
        │  create
        ▼
tech_specs ──1:N── tech_spec_versions   (immutable generation history)
        │
        ▼
TechSpecService.generate(spec_id)
        │   - resolve prompt (versioned, or DEFAULT_SPEC_PROMPT)
        │   - resolve model dynamically (model_id; no hardcoding)
        │   - call LLM via port, with_retry on transient errors
        │   - parse + validate → structured content
        ▼
new tech_spec_versions row (status=succeeded) ; tech_specs.current_version++
```

- **Service:** `app/application/services/tech_spec.py` →
  `TechSpecService(CrudService)` (`resource="spec"`, `entity_type="tech_spec"`).
- **Model-agnostic:** the model is selected per generation via `model_id`; the
  prompt template comes from the versioned prompt library (`prompt_id`) or the
  built-in `DEFAULT_SPEC_PROMPT`. Both choices are recorded on the version row.
- **LLM port:** generation goes through the `LLMClient` port
  (`app/domain/llm.py`); the offline `StubLLMClient` makes the phase fully
  testable without external services.
- **Retry:** transient `LLMError`s are retried via `with_retry` up to
  `max_attempts`; the attempt count is stored on the version.

## Versioning & compare

Each successful generation appends an immutable `tech_spec_versions` row
(`unique (spec_id, version)`), capturing the structured `content`, `raw_output`,
the `model_id`/`model_key`/`provider`, `prompt_id`/`prompt_version`, `attempts`,
and any `error`. `compare(spec_id, a, b)` produces a field-by-field diff across
the `TechSpecContent` fields between two versions.

## Data model (`migrations/0004_tech_specs.sql`)

- `tech_specs(id, workspace_id, ticket_id, title, source_text, status,
  current_version, prompt_id, model_id, …)` with
  `spec_status ∈ {draft, generating, ready, failed, approved, rejected}`.
- `tech_spec_versions(id, spec_id, version, status, content, raw_output,
  model_id, model_key, provider, prompt_id, prompt_version, attempts, error, …)`,
  `generation_status ∈ {pending, succeeded, failed}`, unique `(spec_id, version)`.
- Permissions `spec:{read, write, delete, generate}` — admin/manager full,
  member read-only. RLS read backstop for authenticated users.

## REST API

| Method & path | Description |
|---------------|-------------|
| `GET    /api/v1/tech-specs` | List specs |
| `POST   /api/v1/tech-specs` | Create a spec from free text |
| `GET    /api/v1/tech-specs/{spec_id}` | One spec |
| `PATCH  /api/v1/tech-specs/{spec_id}` | Update spec metadata / source text |
| `DELETE /api/v1/tech-specs/{spec_id}` | Delete a spec |
| `POST   /api/v1/tech-specs/{spec_id}/generate` | Run AI analysis → new version |
| `GET    /api/v1/tech-specs/{spec_id}/versions` | Version history |
| `GET    /api/v1/tech-specs/{spec_id}/versions/{version}` | One version |
| `GET    /api/v1/tech-specs/{spec_id}/compare?a=&b=` | Field-by-field diff |

`generate` body: `{ model_id, prompt_id, temperature, max_attempts, notes }`
(all optional; `model_id`/`prompt_id` null = dynamic / default).

## Failure handling

If the LLM call or validation fails after retries, the version is recorded as
`failed` (with `error`), the spec is marked `failed`, a `spec.failed` event is
recorded, and a `GenerationError` (502) is raised. Success records a
`spec.generated` event and a `generate` audit entry, and advances
`current_version` with the spec status set to `ready`.

## Tests — `tests/test_tech_spec.py`

Covers spec CRUD, `parse_spec_content` (valid JSON, code-fence stripping,
invalid JSON / contract → `ValidationError`), generation producing a `succeeded`
version with structured content, model/prompt selection recorded on the version,
retry-then-success, exhausted retries → `failed` + `GenerationError`, version
history ordering, and `compare` diffs.
