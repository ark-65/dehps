#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ark/workspace/dehps"
WORKER_DIR="$REPO_ROOT/apps/worker-python"
LOG_DIR="$REPO_ROOT/runtime/logs"
PID_FILE="$LOG_DIR/training-supervisor-kdj-ridge-neural.pid"
WEIGHT_KDJ_BUDGET_SHARE="${DEHPS_WEIGHT_KDJ_BUDGET_SHARE:-0.22}"
NEURAL_KDJ_BUDGET_SHARE="${DEHPS_NEURAL_KDJ_BUDGET_SHARE:-0.20}"
TRAINING_WORKERS="${DEHPS_TRAINING_WORKERS:-16}"
RESEARCH_LANE_WORKERS="${DEHPS_RESEARCH_LANE_WORKERS:-$TRAINING_WORKERS}"
RESEARCH_PROFILE="${DEHPS_RESEARCH_PROFILE:-idle-optimization-default}"
RESEARCH_TRAIN_MODE="${DEHPS_RESEARCH_TRAIN_MODE:-expanding}"
RESEARCH_TRAIN_WINDOW="${DEHPS_RESEARCH_TRAIN_WINDOW:-900}"
RESEARCH_EVAL_WINDOW="${DEHPS_RESEARCH_EVAL_WINDOW:-100}"
RESEARCH_TOP_N="${DEHPS_RESEARCH_TOP_N:-10000}"
RESEARCH_HISTORY_SCOPE="${DEHPS_RESEARCH_HISTORY_SCOPE:-current_regime_default}"
RESEARCH_REGIME_YEARS="${DEHPS_RESEARCH_REGIME_YEARS:-10}"
RESEARCH_RANDOM_SEEDS="${DEHPS_RESEARCH_RANDOM_SEEDS:-}"
RESEARCH_TASKS="${DEHPS_RESEARCH_TASKS:-training-diagnostics,walk-forward,weight-grid,analytic-null-baseline}"
MAX_CONFIGS_PER_ROUND="${DEHPS_MAX_CONFIGS_PER_ROUND:-96}"
MEMORY_BUDGET_GB="${DEHPS_MEMORY_BUDGET_GB:-24}"
NEURAL_KDJ_HIDDEN_UNITS="${DEHPS_NEURAL_KDJ_HIDDEN_UNITS:-8}"
NEURAL_KDJ_EPOCHS="${DEHPS_NEURAL_KDJ_EPOCHS:-120}"
TARGET_INVERSION_MAX_CANDIDATES="${DEHPS_TARGET_INVERSION_MAX_CANDIDATES:-8}"
TARGET_INVERSION_MAX_DELTAS="${DEHPS_TARGET_INVERSION_MAX_DELTAS:-12}"
PROGRESS_INTERVAL="${DEHPS_PROGRESS_INTERVAL:-5}"
FORWARD_SHADOW_CAPTURE="true"
FORWARD_SHADOW_WORKERS="${DEHPS_FORWARD_SHADOW_WORKERS:-8}"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

mkdir -p "$LOG_DIR"
cd "$WORKER_DIR"

log() {
  printf '%s %s\n' "$(date -Is)" "$*"
}

if [[ ! "$FORWARD_SHADOW_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
  log "invalid production forward shadow worker count value=$FORWARD_SHADOW_WORKERS"
  exit 1
fi

is_training_pid_active() {
  local pid="$1"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_training_supervisor.py"
}

training_pid_environment_value() {
  local pid="$1"
  local key="$2"
  [[ -r "/proc/$pid/environ" ]] || return 1
  tr '\0' '\n' < "/proc/$pid/environ" \
    | awk -F= -v expected_key="$key" '$1 == expected_key {sub(/^[^=]*=/, ""); print; exit}'
}

training_pid_shadow_contract_valid() {
  local pid="$1"
  local observed_capture
  local observed_workers
  observed_capture="$(training_pid_environment_value "$pid" DEHPS_FORWARD_SHADOW_CAPTURE || true)"
  observed_workers="$(training_pid_environment_value "$pid" DEHPS_FORWARD_SHADOW_WORKERS || true)"
  [[ "$observed_capture" == "$FORWARD_SHADOW_CAPTURE" \
    && "$observed_workers" == "$FORWARD_SHADOW_WORKERS" ]]
}

discover_training_pid() {
  local pid
  pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
  if is_training_pid_active "$pid"; then
    printf '%s\n' "$pid"
    return 0
  fi
  pid="$(.venv/bin/python - <<'PY'
from dehps.runtime.heavy_job import describe_heavy_job_owner

status = describe_heavy_job_owner()
metadata = status.metadata or {}
if status.active and metadata.get("owner") == "training-supervisor":
    print(metadata.get("pid") or "")
PY
)"
  if is_training_pid_active "$pid"; then
    printf '%s\n' "$pid"
    return 0
  fi
  return 1
}

latest_db_issue() {
  .venv/bin/python - <<'PY'
from dehps.db import get_connection

with get_connection() as conn:
    row = conn.execute("SELECT max(issue) FROM ssq_history").fetchone()
print(row[0] or "")
PY
}

latest_weight_kdj_signal_issue() {
  .venv/bin/python - <<'PY'
from dehps.db import get_connection
from dehps.storage.postgres_store import CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID

with get_connection() as conn:
    table = conn.execute("SELECT to_regclass('public.training_weight_signals')").fetchone()
    if not table or not table[0]:
        print("")
    else:
        row = conn.execute(
            "SELECT max(issue) FROM training_weight_signals WHERE signal_run_id = %s",
            (CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,),
        ).fetchone()
        print((row and row[0]) or "")
PY
}

next_complete_prediction_issue() {
  local history_issue="$1"
  .venv/bin/python - "$history_issue" <<'PY'
import sys
from dehps.db import get_connection

history_issue = str(sys.argv[1] or "")
with get_connection() as conn:
    table = conn.execute(
        "SELECT to_regclass('public.training_next_candidates_current')"
    ).fetchone()
    if not table or not table[0]:
        print("")
        raise SystemExit(0)
    row = conn.execute(
        """
        SELECT next_issue
        FROM training_next_candidates_current
        WHERE line_key IN ('static_100', 'dynamic_kdj', 'dynamic_kdj_near')
          AND next_issue ~ '^[0-9]+$'
          AND next_issue::BIGINT > %s::BIGINT
        GROUP BY next_issue
        HAVING count(DISTINCT line_key) = 3
        ORDER BY next_issue::BIGINT
        LIMIT 1
        """,
        (history_issue,),
    ).fetchone()
print((row and row[0]) or "")
PY
}

mark_training_supervisor_waiting() {
  local pid="$1"
  local history_issue="$2"
  local pending_issue
  pending_issue="$(next_complete_prediction_issue "$history_issue")"
  if [[ -z "$pending_issue" ]]; then
    log "cannot mark supervisor waiting: no complete future prediction issue history_issue=${history_issue:-none}"
    return 1
  fi
  if .venv/bin/python scripts/mark_training_supervisor_waiting.py \
    --expected-pid "$pid" \
    --history-issue "$history_issue" \
    --pending-issue "$pending_issue"; then
    log "marked supervisor waiting pid=$pid history_issue=$history_issue pending_issue=$pending_issue"
    return 0
  fi
  log "failed to mark supervisor waiting pid=$pid history_issue=$history_issue pending_issue=$pending_issue"
  return 1
}

refresh_weight_kdj_signals() {
  local latest_issue="$1"
  local signal_issue
  local stamp
  local refresh_log
  signal_issue="$(latest_weight_kdj_signal_issue)"
  if [[ -n "$latest_issue" && "$signal_issue" == "$latest_issue" ]]; then
    log "weight KDJ signals already current issue=$latest_issue"
    return 0
  fi
  if [[ "$signal_issue" =~ ^[0-9]+$ && "$latest_issue" =~ ^[0-9]+$ && "$signal_issue" -gt "$latest_issue" ]]; then
    log "weight KDJ signal issue is ahead of history signal_issue=$signal_issue latest_issue=$latest_issue; refusing refresh"
    return 1
  fi
  stamp="$(date +%Y%m%d-%H%M%S)"
  refresh_log="$LOG_DIR/weight-kdj-incremental-$stamp.log"
  log "refreshing weight KDJ signals signal_issue=${signal_issue:-none} latest_issue=${latest_issue:-none} log=$refresh_log"
  if ! .venv/bin/python scripts/generate_weight_kdj_signals.py \
    --mode incremental \
    --signal-run-id weight-kdj-recent-1000-v1 \
    --issues 1000 \
    --allow-partial \
    --chunk-size 25 \
    --train-window 900 \
    --top-n 10000 \
    --heavy-job-lock-timeout-seconds 0 \
    --cpu-threads 1 \
    > "$refresh_log" 2>&1; then
    log "weight KDJ signal refresh failed log=$refresh_log"
    tail -n 40 "$refresh_log" >&2 || true
    return 1
  fi
  signal_issue="$(latest_weight_kdj_signal_issue)"
  if [[ -z "$latest_issue" || "$signal_issue" != "$latest_issue" ]]; then
    log "weight KDJ signal refresh incomplete signal_issue=${signal_issue:-none} latest_issue=${latest_issue:-none} log=$refresh_log"
    return 1
  fi
  log "weight KDJ signal refresh completed issue=$signal_issue log=$refresh_log"
}

unresolved_data_conflict_count() {
  .venv/bin/python - <<'PY'
from dehps.db import get_connection
from dehps.storage.postgres_store import ensure_ssq_data_conflicts_resolution_schema

with get_connection() as conn:
    table = conn.execute("SELECT to_regclass('public.ssq_data_conflicts')").fetchone()
    if not table or not table[0]:
        print(0)
    else:
        ensure_ssq_data_conflicts_resolution_schema(conn)
        row = conn.execute(
            "SELECT count(*) FROM ssq_data_conflicts WHERE resolved_at IS NULL"
        ).fetchone()
        print(int((row and row[0]) or 0))
PY
}

training_pid_as_of_issue() {
  local pid="$1"
  ps -p "$pid" -o args= 2>/dev/null | awk '
    {
      for (i = 1; i <= NF; i++) {
        if ($i == "--as-of-issue" && i < NF) {
          print $(i + 1)
          exit
        }
        if ($i ~ /^--as-of-issue=/) {
          sub(/^--as-of-issue=/, "", $i)
          print $i
          exit
        }
      }
    }
  '
}

stop_training_pid() {
  local pid="$1"
  local pgid
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"
  log "stopping stale training supervisor pid=$pid"
  if [[ "$pgid" == "$pid" ]]; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
  else
    kill "$pid" 2>/dev/null || true
  fi
  for _ in $(seq 1 60); do
    if ! is_training_pid_active "$pid" && { [[ -z "$pgid" ]] || ! pgrep -g "$pgid" >/dev/null 2>&1; }; then
      return 0
    fi
    sleep 1
  done
  log "training supervisor pid=$pid pgid=${pgid:-unknown} did not stop after SIGTERM"
  return 1
}

watch_recommends_supervisor_restart() {
  local pid="$1"
  local watch_file
  local reason_file
  local reason
  watch_file="$(mktemp "$LOG_DIR/training-watch-summary.XXXXXX.json")"
  reason_file="$(mktemp "$LOG_DIR/training-watch-restart-guard.XXXXXX.txt")"
  if ! .venv/bin/python scripts/watch_training_progress.py --limit 5 > "$watch_file"; then
    log "training watch check failed; keeping supervisor pid=$pid"
    rm -f "$watch_file" "$reason_file"
    return 1
  fi
  if .venv/bin/python scripts/training_watch_restart_guard.py \
    --expected-pid "$pid" \
    < "$watch_file" \
    > "$reason_file"; then
    reason="$(tr -d '\n' < "$reason_file")"
    log "training watch requested supervisor restart pid=$pid reason=${reason:-unknown}"
    rm -f "$watch_file" "$reason_file"
    return 0
  fi
  reason="$(tr -d '\n' < "$reason_file" 2>/dev/null || true)"
  log "training watch did not request supervisor restart pid=$pid reason=${reason:-unknown}"
  rm -f "$watch_file" "$reason_file"
  return 1
}

watch_requests_forward_evidence_wait() {
  local pid="${1:-}"
  local watch_file
  local reason_file
  local reason
  local -a guard_args=()
  watch_file="$(mktemp "$LOG_DIR/training-watch-forward-wait.XXXXXX.json")"
  reason_file="$(mktemp "$LOG_DIR/training-watch-forward-wait-guard.XXXXXX.txt")"
  if ! .venv/bin/python scripts/watch_training_progress.py --limit 5 > "$watch_file"; then
    log "training forward-wait check failed; continuing normal supervisor handling"
    rm -f "$watch_file" "$reason_file"
    return 1
  fi
  if [[ -n "$pid" ]]; then
    guard_args+=(--expected-pid "$pid")
  fi
  if .venv/bin/python scripts/training_watch_forward_wait_guard.py \
    "${guard_args[@]}" \
    < "$watch_file" \
    > "$reason_file"; then
    reason="$(tr -d '\n' < "$reason_file")"
    log "training watch requested forward-evidence wait pid=${pid:-none} reason=${reason:-unknown}"
    rm -f "$watch_file" "$reason_file"
    return 0
  fi
  reason="$(tr -d '\n' < "$reason_file" 2>/dev/null || true)"
  log "training watch did not request forward-evidence wait pid=${pid:-none} reason=${reason:-unknown}"
  rm -f "$watch_file" "$reason_file"
  return 1
}

watch_forward_evidence_wait_requested() {
  local pid="$1"
  local watch_file
  local reason_file
  local reason
  watch_file="$(mktemp "$LOG_DIR/training-watch-forward-wait-request.XXXXXX.json")"
  reason_file="$(mktemp "$LOG_DIR/training-watch-forward-wait-request-guard.XXXXXX.txt")"
  if ! .venv/bin/python scripts/watch_training_progress.py --limit 5 > "$watch_file"; then
    log "training forward-wait request check failed"
    rm -f "$watch_file" "$reason_file"
    return 1
  fi
  if .venv/bin/python scripts/training_watch_forward_wait_guard.py \
    --expected-pid "$pid" \
    --request-only \
    < "$watch_file" \
    > "$reason_file"; then
    reason="$(tr -d '\n' < "$reason_file")"
    log "training watch confirmed forward-evidence wait request pid=$pid reason=${reason:-unknown}"
    rm -f "$watch_file" "$reason_file"
    return 0
  fi
  reason="$(tr -d '\n' < "$reason_file" 2>/dev/null || true)"
  log "training watch did not confirm forward-evidence wait request pid=$pid reason=${reason:-unknown}"
  rm -f "$watch_file" "$reason_file"
  return 1
}

isolated_research_lane_active() {
  pgrep -f "scripts/run_isolated_research_lane.py" >/dev/null 2>&1
}

isolated_research_lane_completed() {
  local as_of_issue="$1"
  local seed_args=()
  if [[ -n "$RESEARCH_RANDOM_SEEDS" ]]; then
    seed_args=(--random-seeds "$RESEARCH_RANDOM_SEEDS")
  fi
  .venv/bin/python scripts/run_isolated_research_lane.py \
    --mode research \
    --as-of-issue "$as_of_issue" \
    --workers "$RESEARCH_LANE_WORKERS" \
    --profile-key "$RESEARCH_PROFILE" \
    --train-mode "$RESEARCH_TRAIN_MODE" \
    --train-window "$RESEARCH_TRAIN_WINDOW" \
    --eval-window "$RESEARCH_EVAL_WINDOW" \
    --top-n "$RESEARCH_TOP_N" \
    --history-scope "$RESEARCH_HISTORY_SCOPE" \
    --regime-years "$RESEARCH_REGIME_YEARS" \
    "${seed_args[@]}" \
    --tasks "$RESEARCH_TASKS" \
    --check-completed \
    >/dev/null
}

start_isolated_research_lane() {
  local as_of_issue="$1"
  local stamp
  local research_log
  local seed_args=()
  if isolated_research_lane_active; then
    log "isolated research lane already running as_of_issue=${as_of_issue:-none}"
    return 0
  fi
  if isolated_research_lane_completed "$as_of_issue"; then
    log "isolated research lane already completed for identical training fingerprint as_of_issue=${as_of_issue:-none} profile=$RESEARCH_PROFILE"
    return 0
  fi
  stamp="$(date +%Y%m%d-%H%M%S)"
  research_log="$LOG_DIR/isolated-research-lane-$stamp.log"
  if [[ -n "$RESEARCH_RANDOM_SEEDS" ]]; then
    seed_args=(--random-seeds "$RESEARCH_RANDOM_SEEDS")
  fi
  log "starting isolated research lane state=RESEARCH_ONLY as_of_issue=${as_of_issue:-none} profile=$RESEARCH_PROFILE tasks=$RESEARCH_TASKS train_mode=$RESEARCH_TRAIN_MODE train_window=$RESEARCH_TRAIN_WINDOW eval_window=$RESEARCH_EVAL_WINDOW top_n=$RESEARCH_TOP_N seed_policy=${RESEARCH_RANDOM_SEEDS:-none} workers=$RESEARCH_LANE_WORKERS log=$research_log"
  nohup .venv/bin/python scripts/run_isolated_research_lane.py \
    --mode research \
    --as-of-issue "$as_of_issue" \
    --workers "$RESEARCH_LANE_WORKERS" \
    --profile-key "$RESEARCH_PROFILE" \
    --train-mode "$RESEARCH_TRAIN_MODE" \
    --train-window "$RESEARCH_TRAIN_WINDOW" \
    --eval-window "$RESEARCH_EVAL_WINDOW" \
    --top-n "$RESEARCH_TOP_N" \
    --history-scope "$RESEARCH_HISTORY_SCOPE" \
    --regime-years "$RESEARCH_REGIME_YEARS" \
    "${seed_args[@]}" \
    --tasks "$RESEARCH_TASKS" > "$research_log" 2>&1 < /dev/null &
}

write_training_stall_diagnosis() {
  local diagnosis_output
  if diagnosis_output="$(.venv/bin/python scripts/diagnose_training_stall.py)"; then
    log "training stall diagnosis payload=$diagnosis_output"
    return 0
  fi
  log "training stall diagnosis failed payload=${diagnosis_output:-none}"
  return 1
}

source_worktree_status="$(git -C "$REPO_ROOT" status --porcelain=v1 --untracked-files=all)" || {
  log "source worktree status unavailable; refusing automated training"
  exit 1
}
if [[ -n "$source_worktree_status" ]]; then
  source_change_count="$(printf '%s\n' "$source_worktree_status" | wc -l)"
  log "source worktree is dirty; refusing automated production or research training change_count=$source_change_count"
  exit 1
fi

storage_capacity_output="$(.venv/bin/python scripts/check_runtime_storage_capacity.py)" || {
  log "runtime storage capacity blocked advisor refresh and supervisor start payload=$storage_capacity_output"
  exit 1
}
log "runtime storage capacity accepted payload=$storage_capacity_output"

latest_issue="$(latest_db_issue)"
unresolved_conflict_count="$(unresolved_data_conflict_count)"
if [[ ! "$unresolved_conflict_count" =~ ^[0-9]+$ ]]; then
  log "draw conflict audit invalid unresolved_conflict_count=$unresolved_conflict_count; watchdog stopping fail closed"
  exit 1
fi
if (( unresolved_conflict_count > 0 )); then
  log "draw conflict audit blocked release unresolved_conflict_count=$unresolved_conflict_count; refusing advisor refresh or supervisor start"
  exit 1
fi
log "draw synchronization is decoupled from training watchdog; latest_db_issue=${latest_issue:-none}"
signal_issue="$(latest_weight_kdj_signal_issue)"
signal_refresh_needed=false
if [[ -n "$latest_issue" && "$signal_issue" != "$latest_issue" ]]; then
  signal_refresh_needed=true
  log "weight KDJ signals stale signal_issue=${signal_issue:-none} latest_issue=$latest_issue"
fi

pid="$(discover_training_pid || true)"
if [[ -n "$pid" ]]; then
  if [[ "$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)" != "$pid" ]]; then
    printf '%s\n' "$pid" > "$PID_FILE"
    log "recovered training supervisor pid=$pid from heavy-job metadata"
  fi
  if is_training_pid_active "$pid"; then
    if ! training_pid_shadow_contract_valid "$pid"; then
      observed_capture="$(training_pid_environment_value "$pid" DEHPS_FORWARD_SHADOW_CAPTURE || true)"
      observed_workers="$(training_pid_environment_value "$pid" DEHPS_FORWARD_SHADOW_WORKERS || true)"
      log "training supervisor shadow contract mismatch pid=$pid capture=${observed_capture:-missing} workers=${observed_workers:-missing}; stopping fail closed"
      stop_training_pid "$pid"
    else
      running_as_of="$(training_pid_as_of_issue "$pid")"
      if [[ "$running_as_of" == "$latest_issue" && "$signal_refresh_needed" == false ]]; then
        if watch_forward_evidence_wait_requested "$pid"; then
          log "waiting for the next durable round boundary before parking supervisor pid=$pid"
          for _ in $(seq 1 90); do
            if watch_requests_forward_evidence_wait "$pid"; then
              stop_training_pid "$pid"
              mark_training_supervisor_waiting "$pid" "$latest_issue"
              log "training supervisor parked until a new forward issue is synced latest_issue=${latest_issue:-none}"
              exit 0
            fi
            if ! is_training_pid_active "$pid"; then
              log "training supervisor stopped before forward-wait boundary pid=$pid"
              break
            fi
            sleep 5
          done
          log "forward-evidence wait boundary was not reached in time; keeping supervisor pid=$pid"
        fi
        if watch_recommends_supervisor_restart "$pid"; then
          stop_training_pid "$pid"
        else
          log "training supervisor already running pid=$pid as_of_issue=${running_as_of:-auto} shadow_capture=$FORWARD_SHADOW_CAPTURE shadow_workers=$FORWARD_SHADOW_WORKERS"
          exit 0
        fi
      else
        log "training supervisor stale pid=$pid running_as_of=${running_as_of:-auto} latest_issue=${latest_issue:-none} signal_issue=${signal_issue:-none}"
        stop_training_pid "$pid"
      fi
    fi
  fi
fi

if [[ "$signal_refresh_needed" == true ]]; then
  refresh_weight_kdj_signals "$latest_issue"
fi

if watch_requests_forward_evidence_wait ""; then
  write_training_stall_diagnosis || true
  log "orchestration state=WAITING_FOR_DRAW production_prediction_allowed=false research_state=RESEARCH_ONLY research_training_allowed=true evaluation_allowed=false"
  start_isolated_research_lane "$latest_issue"
  log "production training supervisor remains parked; fingerprinted research may continue until a new forward issue is synced latest_issue=${latest_issue:-none}"
  exit 0
fi

stamp="$(date +%Y%m%d-%H%M%S)"
run_log="$LOG_DIR/training-supervisor-kdj-ridge-neural-target-inversion-$stamp.log"

setsid bash -lc '
  set -euo pipefail
  pid_file="$0"
  as_of_issue="$1"
  weight_kdj_budget_share="$2"
  neural_kdj_budget_share="$3"
  training_workers="$4"
  watchdog_lock="$5"
  max_configs_per_round="$6"
  memory_budget_gb="$7"
  neural_kdj_hidden_units="$8"
  neural_kdj_epochs="$9"
  target_inversion_max_candidates="${10}"
  target_inversion_max_deltas="${11}"
  progress_interval="${12}"
  shadow_capture="${13}"
  shadow_workers="${14}"
  export DEHPS_FORWARD_SHADOW_CAPTURE="$shadow_capture"
  export DEHPS_FORWARD_SHADOW_WORKERS="$shadow_workers"
  for fd_path in /proc/$$/fd/*; do
    fd="${fd_path##*/}"
    if [[ "$fd" =~ ^[0-9]+$ ]] && (( fd > 2 )) \
      && [[ "$(readlink "$fd_path" 2>/dev/null || true)" == "$watchdog_lock" ]]; then
      eval "exec ${fd}>&-"
    fi
  done
  printf "%s\n" "$$" > "$pid_file"
  args=(
    scripts/run_training_supervisor.py
    --duration-hours 0
    --train-window 900
    --eval-window 100
    --top-n 10000
    --workers "$training_workers"
    --train-mode expanding
    --history-scope current_regime_default
    --regime-years 10
    --progress-interval "$progress_interval"
    --max-configs-per-round "$max_configs_per_round"
    --memory-budget-gb "$memory_budget_gb"
    --write-status-json
    --enable-weight-kdj-advisor
    --weight-kdj-budget-share "$weight_kdj_budget_share"
    --enable-ridge-kdj-advisor
    --enable-neural-kdj-advisor
    --neural-kdj-budget-share "$neural_kdj_budget_share"
    --neural-kdj-hidden-units "$neural_kdj_hidden_units"
    --neural-kdj-epochs "$neural_kdj_epochs"
    --target-weight-inversion-max-candidates "$target_inversion_max_candidates"
    --target-weight-inversion-max-targets 100
    --target-weight-inversion-max-deltas-per-target "$target_inversion_max_deltas"
    --cpu-threads 1
  )
  if [[ -n "$as_of_issue" ]]; then
    args+=(--as-of-issue "$as_of_issue")
  fi
  exec .venv/bin/python "${args[@]}"
' "$PID_FILE" "$latest_issue" "$WEIGHT_KDJ_BUDGET_SHARE" "$NEURAL_KDJ_BUDGET_SHARE" "$TRAINING_WORKERS" \
  "$LOG_DIR/training-supervisor-watchdog.lock" "$MAX_CONFIGS_PER_ROUND" "$MEMORY_BUDGET_GB" \
  "$NEURAL_KDJ_HIDDEN_UNITS" "$NEURAL_KDJ_EPOCHS" "$TARGET_INVERSION_MAX_CANDIDATES" \
  "$TARGET_INVERSION_MAX_DELTAS" "$PROGRESS_INTERVAL" "$FORWARD_SHADOW_CAPTURE" \
  "$FORWARD_SHADOW_WORKERS" > "$run_log" 2>&1 < /dev/null &

launcher_pid="$!"
sleep 1
started_pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
if is_training_pid_active "$started_pid"; then
  if ! training_pid_shadow_contract_valid "$started_pid"; then
    observed_capture="$(training_pid_environment_value "$started_pid" DEHPS_FORWARD_SHADOW_CAPTURE || true)"
    observed_workers="$(training_pid_environment_value "$started_pid" DEHPS_FORWARD_SHADOW_WORKERS || true)"
    log "started training supervisor with invalid shadow contract pid=$started_pid capture=${observed_capture:-missing} workers=${observed_workers:-missing}; stopping fail closed"
    stop_training_pid "$started_pid"
    exit 1
  fi
  log "started training supervisor pid=$started_pid launcher_pid=$launcher_pid as_of_issue=${latest_issue:-auto} shadow_capture=$FORWARD_SHADOW_CAPTURE shadow_workers=$FORWARD_SHADOW_WORKERS log=$run_log"
  exit 0
fi

log "failed to start training supervisor launcher_pid=$launcher_pid log=$run_log"
tail -n 40 "$run_log" >&2 || true
exit 1
