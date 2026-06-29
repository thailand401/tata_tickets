# Logging

Tata uses **structlog** for structured logs (`app/core/logging.py`), configured
at startup from `LOG_LEVEL`. Output goes to stdout — captured by Docker, CI, and
log aggregators.

## Configure

```dotenv
LOG_LEVEL=INFO   # DEBUG | INFO | WARNING | ERROR
```

`get_logger("name")` yields a bound logger; events are key-value:

```python
log = get_logger("orchestrator")
log.info("run_enqueued", bundle_id=b, count=12)
```

## Where to look

| Service | Logs |
|---------|------|
| Dashboard | stdout (`docker logs tata_dashboard`) |
| Prometheus | `docker logs tata_prometheus` |
| Grafana | `docker logs tata_grafana` |
| Extension | VS Code Output → Tata |

## Layers

- **App logs** — stdout via structlog.
- **Audit log** — DB `audit_log` (`GET /audit`).
- **Event log** — DB `event_log` (`GET /events`).
- **Metrics** — `/metrics` → Prometheus → Grafana.

Failures in audit/event recording are logged, never raised, so observability never
breaks a request. See [EVENT_SYSTEM.md](EVENT_SYSTEM.md), [DEPLOYMENT.md](DEPLOYMENT.md).
