#!/usr/bin/env bash
# reset.sh — DESTRUCTIVE: stop everything, clean, drop venv/node_modules, reset DB.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
warn "This wipes venv, node_modules, caches and local DB volumes."
confirm "Reset local environment?" || die "cancelled"
run "${SCRIPTS_DIR}/stop.sh" all
run "${SCRIPTS_DIR}/clean.sh"
run rm -rf "${DASHBOARD_DIR}/.venv" "${EXTENSION_DIR}/node_modules"
have_cmd docker && compose down -v || true
have_cmd supabase && run supabase stop --no-backup || true
ok "reset complete — run scripts/bootstrap.sh to rebuild"
