#!/usr/bin/env bash
# stop.sh — stop one or all Tata services. Idempotent.
# Usage: scripts/stop.sh [service...] [--verbose|--dry-run|--ci]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
source "${SCRIPTS_DIR}/lib/services.sh"
usage() { echo "Usage: $0 [supabase|redis|dashboard|monitoring|workers|all]"; }

parse_common_flags "$@"
targets=(all); ((${#REST_ARGS[@]})) && targets=("${REST_ARGS[@]}")
[[ "${targets[*]}" == "all" ]] && targets=(workers dashboard monitoring redis supabase)

section "Stopping: ${targets[*]}"
for t in "${targets[@]}"; do service_stop "$t"; done
ok "stop complete"
