#!/usr/bin/env bash
# format.sh — auto-fix lint + import order (ruff). --ci: check only, no writes.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
require_cmd python3
cd "${DASHBOARD_DIR}"
PY="${DASHBOARD_DIR}/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
if [[ "${CI}" == "1" ]]; then section "ruff check"; run "$PY" -m ruff check app/; else
  section "ruff --fix"; run "$PY" -m ruff check --fix app/; run "$PY" -m ruff format app/; fi
ok "format complete"
