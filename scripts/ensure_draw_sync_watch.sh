#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ark/workspace/dehps"
WORKER_DIR="$REPO_ROOT/apps/worker-python"
LOG_DIR="$REPO_ROOT/runtime/logs"
PID_FILE="$LOG_DIR/draw-sync-watch.pid"
VERSION_FILE="$LOG_DIR/draw-sync-watch.version"
LOG_FILE="$LOG_DIR/draw-sync-watch.log"

mkdir -p "$LOG_DIR"
cd "$WORKER_DIR"

desired_commit="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
if [[ ! "$desired_commit" =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s invalid draw sync desired commit=%s\n' "$(date -Is)" "$desired_commit" >&2
  exit 1
fi
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain=v1 --untracked-files=all)" ]]; then
  printf '%s source worktree is dirty; refusing draw sync watcher restart\n' "$(date -Is)" >&2
  exit 1
fi

pid=""
if [[ -f "$PID_FILE" ]]; then
  pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
fi
if [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_draw_sync_watch.py"; then
  running_commit="$(tr -d '[:space:]' < "$VERSION_FILE" 2>/dev/null || true)"
  if [[ "$running_commit" == "$desired_commit" ]]; then
    printf '%s draw sync watch already running pid=%s commit=%s\n' "$(date -Is)" "$pid" "$running_commit"
    exit 0
  fi
  printf '%s stopping stale draw sync watch pid=%s running_commit=%s desired_commit=%s\n' \
    "$(date -Is)" "$pid" "${running_commit:-not_recorded}" "$desired_commit"
  kill -TERM "$pid"
  for _attempt in {1..50}; do
    if ! ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_draw_sync_watch.py"; then
      break
    fi
    sleep 0.2
  done
  if ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_draw_sync_watch.py"; then
    printf '%s stale draw sync watch did not stop pid=%s; refusing overlapping restart\n' \
      "$(date -Is)" "$pid" >&2
    exit 1
  fi
fi

rm -f "$PID_FILE" "$VERSION_FILE"

setsid .venv/bin/python "$REPO_ROOT/scripts/run_draw_sync_watch.py" \
  --interval-seconds "${DEHPS_DRAW_SYNC_INTERVAL_SECONDS:-900}" \
  --hot-interval-seconds "${DEHPS_DRAW_SYNC_HOT_INTERVAL_SECONDS:-300}" \
  --timezone "${DEHPS_DRAW_SYNC_TIMEZONE:-Asia/Shanghai}" \
  >> "$LOG_FILE" 2>&1 < /dev/null &

sleep 1
pid=""
if [[ -f "$PID_FILE" ]]; then
  pid="$(tr -d '[:space:]' < "$PID_FILE" 2>/dev/null || true)"
fi
if [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" -o args= 2>/dev/null | grep -Fq "scripts/run_draw_sync_watch.py"; then
  running_commit="$(tr -d '[:space:]' < "$VERSION_FILE" 2>/dev/null || true)"
  if [[ "$running_commit" != "$desired_commit" ]]; then
    printf '%s draw sync watch started with wrong commit pid=%s running_commit=%s desired_commit=%s\n' \
      "$(date -Is)" "$pid" "${running_commit:-not_recorded}" "$desired_commit" >&2
    kill -TERM "$pid" 2>/dev/null || true
    exit 1
  fi
  printf '%s started draw sync watch pid=%s commit=%s log=%s\n' \
    "$(date -Is)" "$pid" "$running_commit" "$LOG_FILE"
  exit 0
fi

printf '%s failed to start draw sync watch log=%s\n' "$(date -Is)" "$LOG_FILE" >&2
tail -n 40 "$LOG_FILE" >&2 || true
exit 1
