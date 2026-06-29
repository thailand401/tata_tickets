#!/usr/bin/env bash
# migrate.sh — apply SQL migrations 0001..NNNN in order. Idempotent (CREATE IF
# NOT EXISTS / ON CONFLICT). Usage: scripts/migrate.sh [flags]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd psql
require_env SUPABASE_DB_URL
section "Migrations"
shopt -s nullglob
files=("${MIGRATIONS_DIR}"/[0-9]*.sql)
[[ ${#files[@]} -gt 0 ]] || die "no migrations in ${MIGRATIONS_DIR}"
for f in "${files[@]}"; do info "apply $(basename "$f")"; run psql "${SUPABASE_DB_URL}" -v ON_ERROR_STOP=1 -f "$f"; done
ok "migrations applied (${#files[@]})"
