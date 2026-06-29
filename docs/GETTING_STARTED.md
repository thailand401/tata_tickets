# Getting Started

This guide takes a developer with **no prior knowledge** from a clean machine to
a running Tata stack: dashboard, Supabase, and the VS Code worker.

## 1. Required software

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.11+ | Dashboard backend (API + UI) |
| Node.js | 20+ | VS Code extension build |
| Docker + Compose | latest | Run dashboard + Prometheus + Grafana |
| Supabase CLI | latest | Local Postgres + Auth (or use Supabase cloud) |
| VS Code | 1.90+ | Run the extension and the coding agent |
| git | 2.30+ | Clone and commit |

Per-OS install instructions are in [INSTALLATION.md](INSTALLATION.md).

## 2. Clone the repository

```bash
git clone <your-fork-url> tata_tickets
cd tata_tickets
```

## 3. Install dependencies

```bash
# Backend
cd dashboard
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Extension
cd ../extension
npm install
npm run compile
cd ..
```

## 4. Configure environment

Create `dashboard/.env` (see [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md)):

```dotenv
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
APP_ENV=development
APP_PORT=8080
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:8080
```

The stack runs fully **offline** with stub providers, but Supabase URL + JWT
secret are required so login and persistence work.

## 5. Start Supabase

```bash
supabase start                     # prints URL, anon key, service key, JWT secret
```

Apply migrations in order (psql against the printed DB URL):

```bash
for f in dashboard/migrations/00*.sql; do psql "$SUPABASE_DB_URL" -f "$f"; done
```

Copy the printed keys into `dashboard/.env`. See [SUPABASE.md](SUPABASE.md).

## 6. Start the Python server

```bash
cd dashboard
source .venv/bin/activate
python -m app.main                 # serves API + UI on http://localhost:8080
```

## 7. Start the Node services (VS Code extension)

Open `extension/` in VS Code and press `F5` to launch the Extension Development
Host. Set `tata.dashboardUrl` to `http://localhost:8080`, then run
**Tata: Login**.

## 8. Start the dashboard

The dashboard UI is served by the same process at `http://localhost:8080`. Log
in with a Supabase user. For monitoring run `docker compose up prometheus grafana`
(Grafana on `http://localhost:3000`).

## 9. Verify installation

```bash
curl http://localhost:8080/health     # {"status":"ok",...}
curl http://localhost:8080/ready      # {"status":"ready",...}
curl http://localhost:8080/metrics    # tata_up 1 ...
cd dashboard && pytest -q             # full offline suite passes
```

Open `http://localhost:8080` for the UI and `/docs` for OpenAPI. You're ready —
continue with [WORKFLOW.md](WORKFLOW.md).
