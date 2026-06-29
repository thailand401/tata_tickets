#!/usr/bin/env bash
# setup.sh — create the Python venv, install app deps, build the extension.
# Idempotent: reuses an existing venv. No sudo required.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
require_cmd python3
section "Python venv"
[[ -d "${DASHBOARD_DIR}/.venv" ]] || run python3 -m venv "${DASHBOARD_DIR}/.venv"
PY="${DASHBOARD_DIR}/.venv/bin/python"
run "$PY" -m pip install --upgrade pip
run "$PY" -m pip install -e "${DASHBOARD_DIR}[dev]"
if [[ -d "${EXTENSION_DIR}" ]] && have_cmd npm; then section "Extension"; ( cd "${EXTENSION_DIR}" && run npm ci && run npm run compile ); fi
ok "setup complete — next: scripts/check-env.sh && scripts/migrate.sh"
