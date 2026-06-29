#!/usr/bin/env bash
# clean.sh — remove caches & build artifacts. Safe: never touches source/.env.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
section "Cleaning caches & artifacts"
run find "${DASHBOARD_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} +
for d in .pytest_cache .mypy_cache .ruff_cache tata_dashboard.egg-info; do
  [[ -e "${DASHBOARD_DIR}/$d" ]] && run rm -rf "${DASHBOARD_DIR}/$d"
done
[[ -d "${EXTENSION_DIR}/out" ]] && run rm -rf "${EXTENSION_DIR}/out"
run rm -rf "${REPO_ROOT}/.logs" "${REPO_ROOT}/.run"
ok "clean done"
