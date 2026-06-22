#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ark/workspace/dehps"
WORKER_DIR="$REPO_ROOT/apps/worker-python"
LOG_DIR="$REPO_ROOT/runtime/logs"
PID_FILE="$LOG_DIR/training-supervisor-kdj-ridge-neural.pid"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mkdir -p "$LOG_DIR"
cd "$WORKER_DIR"

log() {
  printf '%s %s\n' "$(date -Is)" "$*"
}

is_training_pid_active() {
  local pid="$1"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_training_supervisor.py"
}

if [[ -s "$PID_FILE" ]]; then
  pid="$(tr -d '[:space:]' < "$PID_FILE")"
  if is_training_pid_active "$pid"; then
    log "training supervisor already running pid=$pid"
    exit 0
  fi
fi

latest_issue="$(
  .venv/bin/python - <<'PY'
from dehps.db import get_connection

with get_connection() as conn:
    row = conn.execute("SELECT max(issue) FROM ssq_history").fetchone()
print(row[0] or "")
PY
)"

stamp="$(date +%Y%m%d-%H%M%S)"
run_log="$LOG_DIR/training-supervisor-kdj-ridge-neural-target-inversion-$stamp.log"

setsid bash -lc '
  set -euo pipefail
  pid_file="$0"
  as_of_issue="$1"
  printf "%s\n" "$$" > "$pid_file"
  args=(
    scripts/run_training_supervisor.py
    --duration-hours 0
    --train-window 900
    --eval-window 100
    --top-n 10000
    --workers 10
    --train-mode expanding
    --history-scope current_regime_default
    --regime-years 10
    --progress-interval 10
    --max-configs-per-round 28
    --memory-budget-gb 20
    --write-status-json
    --enable-weight-kdj-advisor
    --enable-ridge-kdj-advisor
    --enable-neural-kdj-advisor
    --target-weight-inversion-max-candidates 4
    --target-weight-inversion-max-targets 100
    --target-weight-inversion-max-deltas-per-target 8
    --cpu-threads 1
  )
  if [[ -n "$as_of_issue" ]]; then
    args+=(--as-of-issue "$as_of_issue")
  fi
  exec .venv/bin/python "${args[@]}"
' "$PID_FILE" "$latest_issue" > "$run_log" 2>&1 < /dev/null &

launcher_pid="$!"
sleep 1
started_pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
if is_training_pid_active "$started_pid"; then
  log "started training supervisor pid=$started_pid launcher_pid=$launcher_pid as_of_issue=${latest_issue:-auto} log=$run_log"
  exit 0
fi

log "failed to start training supervisor launcher_pid=$launcher_pid log=$run_log"
tail -n 40 "$run_log" >&2 || true
exit 1
