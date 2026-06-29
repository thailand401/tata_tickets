#!/usr/bin/env bash
# check-env.sh — ensure dashboard/.env exists & required vars are set. Creates
# .env from .env.example when missing. CI mode fails hard on placeholders.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
REQUIRED=(SUPABASE_URL SUPABASE_SERVICE_KEY SUPABASE_ANON_KEY SUPABASE_JWT_SECRET)
OPTIONAL=(SUPABASE_DB_URL APP_PORT LOG_LEVEL CORS_ORIGINS GRAFANA_PASSWORD)

if [[ ! -f "${ENV_FILE}" ]]; then
  [[ -f "${ENV_EXAMPLE}" ]] || die "no ${ENV_EXAMPLE} to copy from"
  run cp "${ENV_EXAMPLE}" "${ENV_FILE}"; warn "created ${ENV_FILE} — fill in real values"
fi
load_env
section "Required"; rc=0
for v in "${REQUIRED[@]}"; do
  val="${!v:-}"; if [[ -z "$val" || "$val" == your-* ]]; then err "$v missing/placeholder"; rc=1; else ok "$v set"; fi
done
section "Optional"; for v in "${OPTIONAL[@]}"; do [[ -n "${!v:-}" ]] && ok "$v=${!v}" || warn "$v unset"; done
exit $(( rc ? EX_CONFIG : EX_OK ))
