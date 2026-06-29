# Troubleshooting

Common problems and fixes. Check `docker compose logs -f dashboard` and
`GET /health` first.

## Supabase connection
- **Symptom**: 500s, "JWT secret is not configured", empty data.
- **Fix**: ensure `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` are set in `dashboard/.env`; restart. Verify `supabase status` and that migrations ran. Test: `curl $SUPABASE_URL/rest/v1/`.

## Python API failure
- **Symptom**: server won't start / import errors.
- **Fix**: activate venv, `pip install -e ".[dev]"`. Check `python -m app.main` logs. Port busy → see port conflicts. 500s → check structlog output.

## Node service failure (extension)
- **Symptom**: commands missing, "cannot connect".
- **Fix**: `cd extension && npm install && npm run compile`; press F5; set `tata.dashboardUrl`; run **Tata: Login**. VS Code Output → Tata for errors.

## Authentication failure
- **Symptom**: 401 unauthenticated / 403 forbidden.
- **Fix**: re-login for a fresh token; ensure `Authorization: Bearer` header; 403 = missing permission, grant via role (`/roles`). JWT secret must match Supabase.

## VS Code extension agent
- **Symptom**: "agent cannot run".
- **Fix**: set `tata.compileCommand`; ensure `CODING_STANDARD.md` exists or adjust path; raise `tata.maxFixIterations`.

## Docker issues
- **Symptom**: unhealthy/restart loop.
- **Fix**: `docker compose logs dashboard`; confirm `.env`; health = `curl /health`; rebuild `docker compose up --build`.

## Port conflicts
- **Symptom**: bind error on 8080/9090/3000.
- **Fix**: free the port or remap in `docker-compose.yml`; set `APP_PORT`. Find: `lsof -i :8080`.

## Permission issues
- **Symptom**: file write / non-root errors.
- **Fix**: container runs uid 1000; ensure mounted volumes are writable; never run service key client-side.

Still stuck? See [FAQ.md](FAQ.md), [SUPABASE.md](SUPABASE.md), [DEPLOYMENT.md](DEPLOYMENT.md).
