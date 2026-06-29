#!/usr/bin/env bash
# restart.sh — stop then start services (default: all).
# Usage: scripts/restart.sh [service...] [flags]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
section "Restart: ${REST_ARGS[*]:-all}"
run "${SCRIPTS_DIR}/stop.sh"  ${REST_ARGS[@]+"${REST_ARGS[@]}"}
run "${SCRIPTS_DIR}/start.sh" ${REST_ARGS[@]+"${REST_ARGS[@]}"}
ok "restart complete"
