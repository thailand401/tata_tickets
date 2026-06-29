#!/usr/bin/env bash
# =============================================================================
# scripts/lib/common.sh — shared helpers for every Tata DevOps script.
#
# Source this at the top of a script:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
#
# Provides: strict mode, colored logging, global flags (--verbose/--dry-run/
# --ci/--help), dependency checks, env loading/validation, run() wrapper, exit
# codes. Modular & reusable so individual scripts stay small and DRY.
# =============================================================================

# ---- strict mode ------------------------------------------------------------
set -Eeuo pipefail

# ---- exit codes (sysexits-inspired) ----------------------------------------
readonly EX_OK=0          # success
readonly EX_ERR=1         # generic failure
readonly EX_USAGE=64      # bad CLI usage
readonly EX_DEPS=69       # missing dependency
readonly EX_CONFIG=78     # bad/missing configuration
readonly EX_UNAVAILABLE=70 # a service/health check failed

# ---- repo layout ------------------------------------------------------------
# REPO_ROOT resolves regardless of where the script is invoked from.
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(cd "${LIB_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPTS_DIR}/.." && pwd)"
DASHBOARD_DIR="${REPO_ROOT}/dashboard"
EXTENSION_DIR="${REPO_ROOT}/extension"
MIGRATIONS_DIR="${DASHBOARD_DIR}/migrations"
ENV_FILE="${ENV_FILE:-${DASHBOARD_DIR}/.env}"
ENV_EXAMPLE="${DASHBOARD_DIR}/.env.example"
export REPO_ROOT DASHBOARD_DIR EXTENSION_DIR MIGRATIONS_DIR ENV_FILE ENV_EXAMPLE

# ---- runtime flags (overridable via env or CLI) ----------------------------
VERBOSE="${VERBOSE:-0}"
DRY_RUN="${DRY_RUN:-0}"
CI="${CI:-0}"

# ---- colors (auto-disabled when not a TTY or in CI) ------------------------
if [[ -t 1 && "${CI}" != "1" && "${NO_COLOR:-0}" != "1" ]]; then
  C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GRN=$'\033[32m'
  C_YLW=$'\033[33m'; C_BLU=$'\033[34m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_DIM=""; C_BOLD=""
fi

_ts() { date +'%H:%M:%S'; }
log()   { printf '%s %s\n' "${C_DIM}[$(_ts)]${C_RESET}" "$*"; }
info()  { printf '%s %s\n' "${C_BLU}[info]${C_RESET}" "$*"; }
ok()    { printf '%s %s\n' "${C_GRN}[ ok ]${C_RESET}" "$*"; }
warn()  { printf '%s %s\n' "${C_YLW}[warn]${C_RESET}" "$*" >&2; }
err()   { printf '%s %s\n' "${C_RED}[fail]${C_RESET}" "$*" >&2; }
debug() { [[ "${VERBOSE}" == "1" ]] && printf '%s %s\n' "${C_DIM}[dbg ]${C_RESET}" "$*" >&2 || true; }
die()   { err "$*"; exit "${EX_ERR}"; }

# Consistent error trap with the offending command + line number.
trap 'err "aborted at line ${LINENO}: ${BASH_COMMAND}"' ERR

# ---- common flag parsing ----------------------------------------------------
# Consumes the global flags from "$@" and leaves the rest in REST_ARGS.
parse_common_flags() {
  REST_ARGS=()
  while (($#)); do
    case "$1" in
      -v|--verbose)  VERBOSE=1 ;;
      -n|--dry-run)  DRY_RUN=1 ;;
      --ci)          CI=1 ;;
      -h|--help)     usage 2>/dev/null || true; exit "${EX_OK}" ;;
      --)            shift; REST_ARGS+=("$@"); break ;;
      *)             REST_ARGS+=("$1") ;;
    esac
    shift
  done
  export VERBOSE DRY_RUN CI
}

# ---- command runner: respects dry-run + verbose ----------------------------
run() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '%s %s\n' "${C_YLW}[dry ]${C_RESET}" "$*"; return 0
  fi
  debug "+ $*"
  "$@"
}

# ---- dependency helpers -----------------------------------------------------
have_cmd() { command -v "$1" >/dev/null 2>&1; }
require_cmd() {
  local missing=0
  for c in "$@"; do
    if ! have_cmd "$c"; then err "missing dependency: $c"; missing=1; fi
  done
  [[ "$missing" == "0" ]] || exit "${EX_DEPS}"
}

# ---- env loading & validation ----------------------------------------------
load_env() {
  if [[ -f "${ENV_FILE}" ]]; then
    set -a; # shellcheck disable=SC1090
    source "${ENV_FILE}"; set +a
    debug "loaded env from ${ENV_FILE}"
  else
    warn "no env file at ${ENV_FILE} (run scripts/check-env.sh)"
  fi
}
require_env() {
  local missing=0
  for v in "$@"; do
    if [[ -z "${!v:-}" ]]; then err "required env var unset: $v"; missing=1; fi
  done
  [[ "$missing" == "0" ]] || exit "${EX_CONFIG}"
}

# ---- misc -------------------------------------------------------------------
confirm() { # confirm "message" — auto-yes in CI/dry-run
  [[ "${CI}" == "1" || "${DRY_RUN}" == "1" ]] && return 0
  read -r -p "${1:-Proceed?} [y/N] " a; [[ "$a" =~ ^[Yy]$ ]]
}
section() { printf '\n%s== %s ==%s\n' "${C_BOLD}" "$*" "${C_RESET}"; }
compose() { run docker compose -f "${REPO_ROOT}/docker-compose.yml" "$@"; }

cd "${REPO_ROOT}"
