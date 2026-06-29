# Models

Tata is **model-agnostic**: LLM providers are selected per task via a port, and
nothing is hardcoded. The default registered provider is an offline,
deterministic stub so the whole pipeline runs and tests without API keys.

## Provider registry

`infrastructure/llm/client.py` keeps a name → factory map. `get_llm_client(provider)`
returns the matching client or falls back to `StubLLMClient`.

| Provider | Enum | Notes |
|----------|------|-------|
| Gemini | `gemini` | Google models |
| Claude | `claude` | Anthropic models |
| GPT | `gpt` | OpenAI models |
| Local | `local` | self-hosted |
| Stub | `stub` | offline default analyzer |

```python
from app.infrastructure.llm.client import register_provider
register_provider("claude", lambda: MyClaudeClient())
```

## Model registry (DB)

The `models` table records `name, provider, model_key, config, status`
(unique per provider+model_key). Manage via `/api/v1/models`:

```bash
curl -X POST http://localhost:8080/api/v1/models -H "Authorization: Bearer $T" \
  -d '{"name":"Claude Sonnet","provider":"claude","model_key":"claude-3-5-sonnet"}'
```

Tech Spec generation references a `model_id`; the call resolves provider/model_key.

## Stub behaviour

`StubLLMClient` derives a complete Tech Spec from the ticket text (feature,
requirements, NFR, API, DB, acceptance, risks, estimate, priority) as valid JSON,
so the application parses it exactly like a real response. Priority is inferred
from keywords (critical/high/low); estimate from sentence count.

## Choosing a model

`temperature`, `max_attempts`, `prompt_id` are per-generation. Failures retry up
to `max_attempts`; exhaustion → `502 generation_failed`. See
[PROMPTS.md](PROMPTS.md), [AGENTS.md](AGENTS.md).
