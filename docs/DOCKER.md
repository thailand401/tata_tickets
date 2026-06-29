# Docker

Compose runs three services: dashboard, Prometheus, Grafana. Image is
`python:3.11-slim`, non-root, with a HEALTHCHECK.

## Services

| Service | Image | Port | Health |
|---------|-------|------|--------|
| dashboard | `ghcr.io/tata/dashboard` (build `./dashboard`) | 8080 | `curl /health` |
| prometheus | `prom/prometheus` | 9090 | `/-/healthy` |
| grafana | `grafana/grafana` | 3000 | `/api/health` |

## Run

```bash
docker compose up --build      # all three
docker compose up dashboard    # API+UI only
docker compose ps              # status
docker compose logs -f dashboard
docker compose down            # stop (keep grafana_data volume)
```

## Dockerfile highlights

- deps installed first for caching; app + migrations copied after.
- runs as uid 1000 `tata`; `EXPOSE 8080`; `CMD python -m app.main`.
- HEALTHCHECK: `curl -fsS http://localhost:8080/health` every 30s.

## Compose highlights

- `dashboard` reads `./dashboard/.env`, restart `unless-stopped`, start-first updates with rollback.
- `grafana` uses `GRAFANA_PASSWORD`, provisioned from `monitoring/grafana/provisioning`, data in `grafana_data`.
- all on the `tata` bridge network.

## Build image directly

```bash
docker build -t tata/dashboard ./dashboard
docker run --env-file dashboard/.env -p 8080:8080 tata/dashboard
```

See [DEPLOYMENT.md](DEPLOYMENT.md), [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md).
