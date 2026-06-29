#!/usr/bin/env bash
# lint.sh — ruff (app) + mypy (non-blocking) + tsc typecheck for the extension.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
require_cmd python3
cd "${DASHBOARD_DIR}"
PY="${DASHBOARD_DIR}/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
section "ruff"; run "$PY" -m ruff check app/
section "mypy (non-blocking)"; "$PY" -m mypy app/ || warn "mypy reported issues"
if [[ -d "${EXTENSION_DIR}" ]] && have_cmd npm; then
  section "tsc"; ( cd "${EXTENSION_DIR}" && run npm run compile ); fi
ok "lint complete"
