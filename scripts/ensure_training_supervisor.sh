#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ark/workspace/dehps"
WORKER_DIR="$REPO_ROOT/apps/worker-python"
LOG_DIR="$REPO_ROOT/runtime/logs"
PID_FILE="$LOG_DIR/training-supervisor-kdj-ridge-neural.pid"
WEIGHT_KDJ_BUDGET_SHARE="${DEHPS_WEIGHT_KDJ_BUDGET_SHARE:-0.22}"
NEURAL_KDJ_BUDGET_SHARE="${DEHPS_NEURAL_KDJ_BUDGET_SHARE:-0.10}"
TRAINING_WORKERS="${DEHPS_TRAINING_WORKERS:-16}"

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

capture_current_prediction_snapshots() {
  local output_path="$1"
  .venv/bin/python - "$output_path" <<'PY'
import json
import sys
from dehps.db import get_connection

output_path = sys.argv[1]
rows = []
try:
    with get_connection() as conn:
        table = conn.execute("SELECT to_regclass('public.training_next_candidates_current')").fetchone()
        if table and table[0]:
            with conn.cursor() as cur:
                rows = cur.execute(
                    """
                    SELECT line_key, next_issue, snapshot_key, as_of_issue
                    FROM training_next_candidates_current
                    WHERE line_key IN ('static_100', 'dynamic_kdj', 'dynamic_kdj_near')
                    GROUP BY line_key, next_issue, snapshot_key, as_of_issue
                    ORDER BY line_key
                    """
                ).fetchall()
except Exception:
    rows = []
payload = [
    {
        "line_key": str(row[0]),
        "next_issue": str(row[1]),
        "snapshot_key": str(row[2]),
        "as_of_issue": str(row[3]),
    }
    for row in rows
]
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False)
PY
}

sync_latest_draw_issue() {
  local path="$1"
  .venv/bin/python - "$path" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    print("")
    raise SystemExit(0)
latest = payload.get("latest_draw") if isinstance(payload, dict) else None
print(str((latest or {}).get("issue") or ""))
PY
}

sync_changed_draw_count() {
  local path="$1"
  .venv/bin/python - "$path" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    print("0")
    raise SystemExit(0)
print(int(payload.get("inserted_count") or 0) + int(payload.get("updated_count") or 0))
PY
}

evaluate_synced_predictions_if_needed() {
  local sync_output_file="$1"
  local previous_issue="$2"
  local current_issue="$3"
  local prediction_snapshot_file="$4"
  local changed_count
  local sync_latest_issue
  changed_count="$(sync_changed_draw_count "$sync_output_file")"
  sync_latest_issue="$(sync_latest_draw_issue "$sync_output_file")"
  if [[ "$changed_count" == "0" && "${previous_issue:-}" == "${current_issue:-}" ]]; then
    log "prediction evaluation skipped changed_count=$changed_count sync_latest_issue=${sync_latest_issue:-none}"
    return 0
  fi
  while IFS=$'\t' read -r line_key next_issue snapshot_key; do
    [[ -n "${line_key:-}" && -n "${next_issue:-}" && -n "${snapshot_key:-}" ]] || continue
    if [[ "$next_issue" =~ ^[0-9]+$ && "$current_issue" =~ ^[0-9]+$ && "$next_issue" -gt "$current_issue" ]]; then
      continue
    fi
    log "evaluating prediction line=$line_key issue=$next_issue snapshot=$snapshot_key changed_count=$changed_count previous_issue=${previous_issue:-none} current_issue=${current_issue:-none}"
    if .venv/bin/python scripts/evaluate_training_prediction.py --line-key "$line_key" --issue "$next_issue" --snapshot-key "$snapshot_key"; then
      log "prediction evaluation completed line=$line_key issue=$next_issue"
    else
      log "prediction evaluation failed line=$line_key issue=$next_issue"
    fi
  done < <(
    .venv/bin/python - "$prediction_snapshot_file" <<'PY'
import json
import sys
from dehps.db import get_connection

try:
    snapshots = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    snapshots = []
with get_connection() as conn:
    for snapshot in snapshots:
        line_key = str(snapshot.get("line_key") or "")
        next_issue = str(snapshot.get("next_issue") or "")
        snapshot_key = str(snapshot.get("snapshot_key") or "")
        if line_key not in {"static_100", "dynamic_kdj", "dynamic_kdj_near"} or not next_issue or not snapshot_key:
            continue
        row = conn.execute("SELECT 1 FROM ssq_history WHERE issue = %s LIMIT 1", (next_issue,)).fetchone()
        if row:
            print("\t".join((line_key, next_issue, snapshot_key)))
PY
  )
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

sync_from_issue="$(latest_db_issue)"
prediction_snapshot_file="$(mktemp "$LOG_DIR/training-prediction-snapshots.XXXXXX.json")"
capture_current_prediction_snapshots "$prediction_snapshot_file"
sync_output_file="$(mktemp "$LOG_DIR/ssq-sync.XXXXXX.json")"
if [[ -n "$sync_from_issue" ]]; then
  log "syncing ssq history from issue=$sync_from_issue"
  .venv/bin/python scripts/sync_latest_ssq.py --source zhcw --history --from-issue "$sync_from_issue" | tee "$sync_output_file"
else
  log "syncing ssq history with no local issue"
  .venv/bin/python scripts/sync_latest_ssq.py --source zhcw --history | tee "$sync_output_file"
fi

latest_issue="$(latest_db_issue)"
evaluate_synced_predictions_if_needed "$sync_output_file" "$sync_from_issue" "$latest_issue" "$prediction_snapshot_file"
rm -f "$sync_output_file"
rm -f "$prediction_snapshot_file"
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
    running_as_of="$(training_pid_as_of_issue "$pid")"
    if [[ "$running_as_of" == "$latest_issue" && "$signal_refresh_needed" == false ]]; then
      if watch_recommends_supervisor_restart "$pid"; then
        stop_training_pid "$pid"
      else
        log "training supervisor already running pid=$pid as_of_issue=${running_as_of:-auto}"
        exit 0
      fi
    else
      log "training supervisor stale pid=$pid running_as_of=${running_as_of:-auto} latest_issue=${latest_issue:-none} signal_issue=${signal_issue:-none}"
      stop_training_pid "$pid"
    fi
  fi
fi

if [[ "$signal_refresh_needed" == true ]]; then
  refresh_weight_kdj_signals "$latest_issue"
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
    --progress-interval 10
    --max-configs-per-round 28
    --memory-budget-gb 20
    --write-status-json
    --enable-weight-kdj-advisor
    --weight-kdj-budget-share "$weight_kdj_budget_share"
    --enable-ridge-kdj-advisor
    --enable-neural-kdj-advisor
    --neural-kdj-budget-share "$neural_kdj_budget_share"
    --target-weight-inversion-max-candidates 4
    --target-weight-inversion-max-targets 100
    --target-weight-inversion-max-deltas-per-target 8
    --cpu-threads 1
  )
  if [[ -n "$as_of_issue" ]]; then
    args+=(--as-of-issue "$as_of_issue")
  fi
  exec .venv/bin/python "${args[@]}"
' "$PID_FILE" "$latest_issue" "$WEIGHT_KDJ_BUDGET_SHARE" "$NEURAL_KDJ_BUDGET_SHARE" "$TRAINING_WORKERS" > "$run_log" 2>&1 < /dev/null &

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
