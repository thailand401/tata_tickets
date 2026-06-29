# FAQ

**What is Tata?** A dashboard that turns free-text tickets into documented,
orchestrated, editor-bridged work: Tech Spec → OpenSpec → tasks → agent → deploy.

**Do I need API keys?** No. Stub LLM and stub executor run the whole pipeline
offline. Add a real provider via `register_provider` for production.

**One process or many?** One: FastAPI serves API + UI on 8080. Prometheus/Grafana
are optional containers; the agent runs in VS Code.

**Where do agents run?** Generation agents are server-side; coding/self-heal loops
run in the extension and use the dashboard as a bridge.

**Does it write code automatically?** Phases 2–3 produce documents only. The
coding agent (Phase 6) writes code locally in your workspace and commits — no push.

**How are tasks routed?** A keyword classifier picks a lane; the fleet scheduler
assigns a specialist (stack/activity > category > generalist).

**How do I deploy?** Push to `develop`/`main`; CI tests, CD builds + auto-deploys
via webhook. See [DEPLOYMENT.md](DEPLOYMENT.md).

**How do I add a permission?** Insert into `permissions`, grant to a role; codes
are `resource:action`. See [DATABASE.md](DATABASE.md).

**Default roles?** admin (all), manager (all but role:write), member (read-only).

**How do I run tests?** `cd dashboard && pytest -q` — fully offline.

**Where are logs/metrics?** stdout (structlog), `/audit`, `/events`, `/metrics`.
See [LOGGING.md](LOGGING.md).

More: [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [ARCHITECTURE.md](ARCHITECTURE.md).
