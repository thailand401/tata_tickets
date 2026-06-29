#!/usr/bin/env bash
# dev.sh — run the dashboard with hot-reload for local development.
# Starts Supabase if available, then uvicorn --reload. Ctrl-C to stop.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
source "${SCRIPTS_DIR}/lib/services.sh"
parse_common_flags "$@"
require_cmd python3
load_env
supabase_start
section "Dev server (reload) on :${APP_PORT:-8080}"
cd "${DASHBOARD_DIR}"
PY="${DASHBOARD_DIR}/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
run "$PY" -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8080}" --reload
