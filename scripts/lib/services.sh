#!/usr/bin/env bash
# =============================================================================
# scripts/lib/services.sh — per-service start/stop/status functions.
#
# One reusable function set covers every component (dashboard, supabase, redis,
# monitoring, workers, bridge). start.sh/stop.sh/status.sh dispatch here so the
# logic lives in exactly one place. Requires lib/common.sh to be sourced first.
# =============================================================================

PID_DIR="${REPO_ROOT}/.run"
LOG_DIR="${REPO_ROOT}/.logs"
mkdir -p "${PID_DIR}" "${LOG_DIR}" 2>/dev/null || true

_pid_file() { echo "${PID_DIR}/$1.pid"; }
_log_file() { echo "${LOG_DIR}/$1.log"; }

_is_up() { # _is_up <name>: pid file process alive?
  local p; p="$(_pid_file "$1")"; [[ -f "$p" ]] && kill -0 "$(cat "$p")" 2>/dev/null
}
_port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- ; }

# -- dashboard (FastAPI + NiceGUI, port 8080) --------------------------------
dashboard_start() {
  _is_up dashboard && { ok "dashboard already running"; return 0; }
  require_dir "${DASHBOARD_DIR}"
  info "starting dashboard on :${APP_PORT:-8080}"
  if [[ "${DRY_RUN}" == "1" ]]; then log "(dry) python -m app.main"; return 0; fi
  ( cd "${DASHBOARD_DIR}" && nohup "${PY:-python3}" -m app.main >"$(_log_file dashboard)" 2>&1 & echo $! >"$(_pid_file dashboard)" )
  ok "dashboard pid $(cat "$(_pid_file dashboard)")"
}
dashboard_stop() { _stop_named dashboard; }

# -- supabase (local stack) ---------------------------------------------------
supabase_start() {
  have_cmd supabase || { warn "supabase CLI not installed — skipping"; return 0; }
  info "starting supabase"; run supabase start || warn "supabase already running"
}
supabase_stop() { have_cmd supabase && run supabase stop || true; }

# -- redis (optional; container or local) ------------------------------------
redis_start() {
  if have_cmd redis-server; then
    _port_busy 6379 && { ok "redis already up"; return 0; }
    info "starting redis"; [[ "${DRY_RUN}" == "1" ]] || ( nohup redis-server >"$(_log_file redis)" 2>&1 & echo $! >"$(_pid_file redis)" )
  else warn "redis not installed — skipping (optional)"; fi
}
redis_stop() { _stop_named redis; }

# -- monitoring (prometheus + grafana via compose) ---------------------------
monitoring_start() { have_cmd docker && compose up -d prometheus grafana || warn "docker missing — skip monitoring"; }
monitoring_stop()  { have_cmd docker && compose stop prometheus grafana || true; }

# -- workers (orchestration consumers — optional module) ---------------------
workers_start() {
  [[ -f "${DASHBOARD_DIR}/app/application/orchestration/worker.py" ]] || { warn "no worker module — skip"; return 0; }
  info "starting worker"; [[ "${DRY_RUN}" == "1" ]] || ( cd "${DASHBOARD_DIR}" && nohup "${PY:-python3}" -m app.application.orchestration.worker >"$(_log_file worker)" 2>&1 & echo $! >"$(_pid_file worker)" )
}
workers_stop() { _stop_named worker; }

# -- bridge/agent/memory/prompt/review/test live inside dashboard+extension ---
bridge_status() { info "VS Code bridge runs in the editor (extension/) — open & Tata: Login"; }

require_dir() { [[ -d "$1" ]] || die "missing dir: $1"; }
_stop_named() {
  local n="$1" p; p="$(_pid_file "$n")"
  if [[ -f "$p" ]] && kill -0 "$(cat "$p")" 2>/dev/null; then
    run kill "$(cat "$p")"; rm -f "$p"; ok "$n stopped"
  else warn "$n not running"; rm -f "$p" 2>/dev/null || true; fi
}

# -- registry: targets -> start/stop fns -------------------------------------
SERVICES=(supabase redis dashboard monitoring workers)
service_start() { case "$1" in supabase) supabase_start;; redis) redis_start;; dashboard) dashboard_start;; monitoring) monitoring_start;; workers) workers_start;; *) die "unknown service: $1";; esac; }
service_stop()  { case "$1" in supabase) supabase_stop;; redis) redis_stop;; dashboard) dashboard_stop;; monitoring) monitoring_stop;; workers) workers_stop;; *) die "unknown service: $1";; esac; }
service_status() {
  local n="$1"
  if _is_up "$n"; then ok "$n: running (pid $(cat "$(_pid_file "$n")"))"; else warn "$n: stopped"; fi
}
