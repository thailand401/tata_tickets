#!/usr/bin/env bash
# deploy.sh — build, push and roll out production via compose.prod. Idempotent.
# Usage: scripts/deploy.sh [--ci|--dry-run|--verbose]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"; load_env
require_cmd docker
section "Production deploy"
run "${SCRIPTS_DIR}/test.sh" --ci
run "${SCRIPTS_DIR}/build.sh" --image
run "${SCRIPTS_DIR}/migrate.sh"
compose -f "${REPO_ROOT}/docker-compose.prod.yml" up -d --build
run "${SCRIPTS_DIR}/health.sh" || die "health check failed — investigate before serving traffic"
ok "deployed"
