#!/usr/bin/env bash
# build.sh — build all artifacts: Python wheel deps, extension JS, Docker image.
# Usage: scripts/build.sh [--image|--python|--extension|--all] [flags]
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
usage() { echo "Usage: $0 [--all|--python|--extension|--image] [--verbose|--dry-run|--ci]"; }
parse_common_flags "$@"
what="${REST_ARGS[0]:---all}"

build_python() { require_cmd python3; cd "${DASHBOARD_DIR}"; run python3 -m pip install -e ".[dev]"; ok "python deps built"; }
build_ext() { [[ -d "${EXTENSION_DIR}" ]] || return 0; require_cmd npm; cd "${EXTENSION_DIR}"; run npm ci; run npm run compile; ok "extension built"; }
build_image() { require_cmd docker; run docker build -t tata/dashboard "${DASHBOARD_DIR}"; ok "image built"; }

section "Build ${what}"
case "$what" in
  --python) build_python ;; --extension) build_ext ;; --image) build_image ;;
  --all) build_python; build_ext; have_cmd docker && build_image || warn "docker missing — skip image" ;;
  *) usage; exit "${EX_USAGE}" ;;
esac
