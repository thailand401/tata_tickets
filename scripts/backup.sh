#!/usr/bin/env bash
# backup.sh — dump the Postgres DB to backups/ (timestamped, gzip). Idempotent.
# Uses SUPABASE_DB_URL or DATABASE_URL. Usage: scripts/backup.sh [out.sql.gz]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd pg_dump gzip
require_env SUPABASE_DB_URL
mkdir -p "${REPO_ROOT}/backups"
out="${REST_ARGS[0]:-${REPO_ROOT}/backups/tata-$(date +%Y%m%d-%H%M%S).sql.gz}"
section "Backup -> ${out}"
if [[ "${DRY_RUN}" == "1" ]]; then log "(dry) pg_dump ... | gzip > ${out}"; else
  pg_dump "${SUPABASE_DB_URL}" | gzip > "${out}"; fi
ok "backup written: ${out}"
