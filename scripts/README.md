# scripts/ — Tata operations toolkit

Production-ready, idempotent Bash scripts to build, run, monitor, and deploy the
AI Software Factory. Linux-first (Ubuntu 24.04 LTS). All share `lib/common.sh`
(strict mode, colored logs, env validation) and `lib/services.sh`.

## Common flags
`--verbose` · `--dry-run` · `--ci` · `--help` — accepted by every script.

## First run
```bash
sudo scripts/install.sh   # apt prerequisites
scripts/setup.sh          # venv + deps
scripts/bootstrap.sh      # env -> migrate -> seed
make dev                  # run with reload
```

## Catalog
| Lifecycle | Build/Ops | Quality/DB | Setup |
|-----------|-----------|------------|-------|
| start stop restart | build clean reset | lint test format | install setup |
| status logs health | backup restore | migrate seed | bootstrap |
| dev | deploy update | check-env | |

Use `make help` for the task runner. Compose: `docker-compose.{dev,prod}.yml`.
