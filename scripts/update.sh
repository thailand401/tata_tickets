#!/usr/bin/env bash
# update.sh — pull latest, rebuild deps, migrate, restart. Zero-surprise upgrade.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd git
section "Update"
run git pull --ff-only
run "${SCRIPTS_DIR}/build.sh" --python
run "${SCRIPTS_DIR}/migrate.sh"
run "${SCRIPTS_DIR}/restart.sh" dashboard
ok "update complete"
