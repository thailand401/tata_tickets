#!/usr/bin/env bash
# logs.sh — tail logs for a service. Local pid-logs or docker compose logs.
# Usage: scripts/logs.sh [dashboard|worker|redis|prometheus|grafana|all]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
source "${SCRIPTS_DIR}/lib/services.sh"
parse_common_flags "$@"
target="${REST_ARGS[0]:-all}"
case "$target" in
  prometheus|grafana|dashboard-container) compose logs -f "${target%-container}" ;;
  all) info "tailing local logs in ${LOG_DIR}"; run tail -n 100 -f "${LOG_DIR}"/*.log ;;
  *) f="${LOG_DIR}/${target}.log"; [[ -f "$f" ]] || die "no log: $f"; run tail -n 100 -f "$f" ;;
esac
