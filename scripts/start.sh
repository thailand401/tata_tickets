#!/usr/bin/env bash
# start.sh — start one or all Tata services. Idempotent: re-running is safe.
# Usage: scripts/start.sh [service...] [--verbose|--dry-run|--ci]
#   service: supabase|redis|dashboard|monitoring|workers|all (default: all)
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
source "${SCRIPTS_DIR}/lib/services.sh"
usage() { echo "Usage: $0 [supabase|redis|dashboard|monitoring|workers|all] [--verbose|--dry-run|--ci]"; }

parse_common_flags "$@"
targets=(all); ((${#REST_ARGS[@]})) && targets=("${REST_ARGS[@]}")
load_env
[[ "${targets[*]}" == "all" ]] && targets=("${SERVICES[@]}")

section "Starting: ${targets[*]}"
for t in "${targets[@]}"; do service_start "$t"; done
ok "start complete"
