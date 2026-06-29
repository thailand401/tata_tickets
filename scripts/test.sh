#!/usr/bin/env bash
# test.sh — run the offline pytest suite. Extra args pass through to pytest.
# Usage: scripts/test.sh [--ci] [-- pytest args]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
require_cmd python3
cd "${DASHBOARD_DIR}"
PY="${DASHBOARD_DIR}/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
section "pytest"
run "$PY" -m pytest -q ${REST_ARGS[@]+"${REST_ARGS[@]}"}
ok "tests passed"
