#!/usr/bin/env bash
# status.sh — show running state + listening ports for every service.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
source "${SCRIPTS_DIR}/lib/services.sh"
parse_common_flags "$@"; load_env

section "Service status"
for s in "${SERVICES[@]}"; do service_status "$s"; done
section "Ports"
for p in "${APP_PORT:-8080}" 9090 3000 54321 6379; do
  if _port_busy "$p"; then ok "port $p: listening"; else warn "port $p: free"; fi
done
bridge_status
