#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ark/workspace/dehps"
WORKER_DIR="$REPO_ROOT/apps/worker-python"
LOG_DIR="$REPO_ROOT/runtime/logs"
PID_FILE="$LOG_DIR/draw-sync-watch.pid"
LOG_FILE="$LOG_DIR/draw-sync-watch.log"

mkdir -p "$LOG_DIR"
cd "$WORKER_DIR"

pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
if [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_draw_sync_watch.py"; then
  printf '%s draw sync watch already running pid=%s\n' "$(date -Is)" "$pid"
  exit 0
fi

nohup .venv/bin/python "$REPO_ROOT/scripts/run_draw_sync_watch.py" \
  --interval-seconds "${DEHPS_DRAW_SYNC_INTERVAL_SECONDS:-900}" \
  --hot-interval-seconds "${DEHPS_DRAW_SYNC_HOT_INTERVAL_SECONDS:-300}" \
  --timezone "${DEHPS_DRAW_SYNC_TIMEZONE:-Asia/Shanghai}" \
  >> "$LOG_FILE" 2>&1 < /dev/null &

sleep 1
pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
if [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_draw_sync_watch.py"; then
  printf '%s started draw sync watch pid=%s log=%s\n' "$(date -Is)" "$pid" "$LOG_FILE"
  exit 0
fi

printf '%s failed to start draw sync watch log=%s\n' "$(date -Is)" "$LOG_FILE" >&2
tail -n 40 "$LOG_FILE" >&2 || true
exit 1
