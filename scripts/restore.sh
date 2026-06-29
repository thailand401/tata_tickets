#!/usr/bin/env bash
# restore.sh — restore a gzip dump into Postgres. Usage: scripts/restore.sh <file.sql.gz>
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd psql gzip
require_env SUPABASE_DB_URL
file="${REST_ARGS[0]:-}"; [[ -f "$file" ]] || die "usage: $0 <backup.sql.gz>"
warn "Restoring ${file} into the configured database."
confirm "Overwrite current data?" || die "cancelled"
if [[ "${DRY_RUN}" == "1" ]]; then log "(dry) gunzip -c ${file} | psql"; else
  gunzip -c "$file" | psql "${SUPABASE_DB_URL}"; fi
ok "restore complete"
