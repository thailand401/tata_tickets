#!/usr/bin/env bash
# bootstrap.sh — one-shot fresh setup: deps -> env -> migrate -> seed -> health.
# Wraps the other scripts so a new dev goes from clone to running in one command.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
section "Bootstrap Tata"
run "${SCRIPTS_DIR}/setup.sh"
run "${SCRIPTS_DIR}/check-env.sh" || warn "fill ${ENV_FILE} then re-run migrate/seed"
have_cmd supabase && run "${SCRIPTS_DIR}/start.sh" supabase || true
[[ -n "${SUPABASE_DB_URL:-}" ]] && { run "${SCRIPTS_DIR}/migrate.sh"; run "${SCRIPTS_DIR}/seed.sh"; } || warn "set SUPABASE_DB_URL to migrate"
ok "bootstrap done — start with: make dev"
