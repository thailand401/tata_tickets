#!/usr/bin/env bash
# install.sh — install OS-level prerequisites on Ubuntu 24.04 (apt). Idempotent.
# Installs only what's missing: python3.11, venv, pip, node/npm, curl, git,
# postgresql-client, docker. Run with sudo for system packages.
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
parse_common_flags "$@"
have_cmd apt-get || die "install.sh targets Ubuntu/Debian (apt). Use scripts/setup.sh for app deps."
SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
pkgs=(python3 python3-venv python3-pip nodejs npm curl git postgresql-client ca-certificates)
need=(); for p in python3 npm curl git psql; do have_cmd "$p" || need+=("$p"); done
section "System packages"
if ((${#need[@]})); then run $SUDO apt-get update; run $SUDO apt-get install -y "${pkgs[@]}"; else ok "core tools present"; fi
have_cmd docker || { warn "docker missing — installing"; run $SUDO sh -c 'curl -fsSL https://get.docker.com | sh'; }
have_cmd supabase || warn "supabase CLI optional: https://supabase.com/docs/guides/cli"
ok "system install complete — next: scripts/setup.sh"
