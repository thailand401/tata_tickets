#!/usr/bin/env bash
# health.sh — probe every endpoint; non-zero exit if any required check fails.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd curl
BASE="http://localhost:${APP_PORT:-8080}"; rc=0
check() { local n="$1" u="$2"; if curl -fsS --max-time 5 "$u" >/dev/null 2>&1; then ok "$n"; else err "$n ($u)"; rc=1; fi; }

section "Health"
check "dashboard /health" "${BASE}/health"
check "dashboard /ready"  "${BASE}/ready"
check "dashboard /metrics" "${BASE}/metrics"
curl -fsS --max-time 5 "http://localhost:9090/-/healthy" >/dev/null 2>&1 && ok "prometheus" || warn "prometheus down (optional)"
curl -fsS --max-time 5 "http://localhost:3000/api/health" >/dev/null 2>&1 && ok "grafana" || warn "grafana down (optional)"
exit $(( rc ? EX_UNAVAILABLE : EX_OK ))
