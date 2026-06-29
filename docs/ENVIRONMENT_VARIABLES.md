# Environment Variables

Settings load from `dashboard/.env` (or real env vars) via pydantic-settings;
names are case-insensitive. Source: `app/core/settings.py`.

## Backend (`dashboard/.env`)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `SUPABASE_URL` | `""` | yes | Supabase project/API URL |
| `SUPABASE_SERVICE_KEY` | `""` | yes | Service-role key (server-side, bypasses RLS) |
| `SUPABASE_ANON_KEY` | `""` | yes | Anon key (login/auth) |
| `SUPABASE_JWT_SECRET` | `""` | yes | HS256 secret to verify access tokens |
| `APP_NAME` | `Tata Dashboard` | no | Display/app name |
| `APP_ENV` | `development` | no | `development`/`production`; prod disables reload |
| `APP_HOST` | `0.0.0.0` | no | Bind host |
| `APP_PORT` | `8080` | no | Bind port |
| `LOG_LEVEL` | `INFO` | no | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `CORS_ORIGINS` | `http://localhost:8080` | no | Comma-separated allowed origins |

`is_production` is true when `APP_ENV` is `production`/`prod`.

## Compose / monitoring

| Variable | Default | Used by | Description |
|----------|---------|---------|-------------|
| `GRAFANA_PASSWORD` | `admin` | grafana | Grafana admin password |

## CI/CD (GitHub Actions secrets)

| Secret | Used by | Description |
|--------|---------|-------------|
| `GITHUB_TOKEN` | cd.yml | GHCR image push (auto-provided) |
| `DEPLOY_URL` | cd.yml | Dashboard base URL for the auto-deploy webhook |
| `DEPLOY_TOKEN` | cd.yml | Bearer token for the webhook call |

## Example `.env`

```dotenv
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=eyJhbGciOi...anon
SUPABASE_SERVICE_KEY=eyJhbGciOi...service
SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-chars
APP_NAME=Tata Dashboard
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8080
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:8080,http://localhost:3000
```

## Extension settings (VS Code)

Configured in settings, not `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `tata.dashboardUrl` | `http://localhost:8080` | Dashboard base URL |
| `tata.categories` | `[]` | Lanes this worker pulls (empty = any) |
| `tata.workspaceId` | `""` | Scope pulled tasks |
| `tata.syncIntervalMs` | `5000` | Realtime polling interval |
| `tata.codingStandardPath` | `CODING_STANDARD.md` | Standard the agent reads |
| `tata.compileCommand` | `""` | Build command (required to run agent) |
| `tata.testCommand` | `""` | Optional verify command |
| `tata.maxFixIterations` | `5` | Max code→compile→fix loops |
| `tata.commitMessageTemplate` | `feat({category}): {task_key} {title}` | Commit template |
| `tata.autoCommit` | `true` | Commit on success (no push) |

Never commit `.env` or keys. See [SUPABASE.md](SUPABASE.md) for where to find values.
