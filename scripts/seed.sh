#!/usr/bin/env bash
# seed.sh — apply only the seed migration (0003) idempotently.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd psql
require_env SUPABASE_DB_URL
seed="${MIGRATIONS_DIR}/0003_seed.sql"
[[ -f "$seed" ]] || die "seed not found: $seed"
section "Seeding"; run psql "${SUPABASE_DB_URL}" -v ON_ERROR_STOP=1 -f "$seed"
ok "seed complete"
