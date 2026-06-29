# Installation

Step-by-step setup per platform. All paths assume the repo root `tata_tickets/`.
After install, follow [GETTING_STARTED.md](GETTING_STARTED.md).

## Prerequisites (all platforms)

- Python 3.11+, Node.js 20+, git, Docker + Compose, VS Code 1.90+, Supabase CLI.

## Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm git curl
# Docker
curl -fsSL https://get.docker.com | sh
# Supabase CLI
curl -fsSL https://supabase.com/install.sh | sh

cd dashboard && python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd ../extension && npm install && npm run compile
```

## macOS

```bash
brew install python@3.11 node git supabase/tap/supabase
brew install --cask docker

cd dashboard && python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd ../extension && npm install && npm run compile
```

## Windows

Use PowerShell:

```powershell
winget install Python.Python.3.11 OpenJS.NodeJS Git.Git Docker.DockerDesktop
# Supabase CLI via scoop
scoop install supabase

cd dashboard; python -m venv .venv; .venv\Scripts\activate
pip install -e ".[dev]"
cd ..\extension; npm install; npm run compile
```

## Docker (recommended for running)

Runs the dashboard plus Prometheus + Grafana with one command:

```bash
cp dashboard/.env.example dashboard/.env   # fill Supabase values
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / `GRAFANA_PASSWORD`) |

See [DOCKER.md](DOCKER.md).

## WSL (Windows Subsystem for Linux)

```powershell
wsl --install -d Ubuntu      # restart, then inside Ubuntu:
```

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv nodejs npm git
# Use Docker Desktop with WSL integration enabled, then follow the Linux steps.
cd dashboard && python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Keep the repo under the Linux filesystem (`~/`) — not `/mnt/c` — for fast I/O.

## Verify

```bash
cd dashboard && pytest -q
python -m app.main && curl http://localhost:8080/health
```

Trouble? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
