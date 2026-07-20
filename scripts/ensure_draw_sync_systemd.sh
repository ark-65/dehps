#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--apply" ]]; then
  printf 'usage: %s --apply\n' "$0" >&2
  exit 2
fi

REPO_ROOT="${DEHPS_REPO_ROOT:-/home/ark/workspace/dehps}"
WORKER_DIR="$REPO_ROOT/apps/worker-python"
SOURCE_UNIT="$REPO_ROOT/deploy/systemd/dehps-draw-sync.service"
SOURCE_TIMER="$REPO_ROOT/deploy/systemd/dehps-draw-sync.timer"
USER_UNIT_DIR="${DEHPS_SYSTEMD_USER_UNIT_DIR:-$HOME/.config/systemd/user}"
USER_CONFIG_DIR="${DEHPS_USER_CONFIG_DIR:-$HOME/.config/dehps}"
INSTALLED_UNIT="$USER_UNIT_DIR/dehps-draw-sync.service"
INSTALLED_TIMER="$USER_UNIT_DIR/dehps-draw-sync.timer"
ENV_FILE="$USER_CONFIG_DIR/draw-sync.env"
LOG_DIR="$REPO_ROOT/runtime/logs"
LAUNCH_FILE="$LOG_DIR/draw-sync-watch.launch.json"
STATE_FILE="$LOG_DIR/draw-sync-watch.json"
VERSION_FILE="$LOG_DIR/draw-sync-watch.version"
DEPLOYMENT_FILE="$LOG_DIR/draw-sync-systemd-deployment.json"
SYSTEMD_UNIT="dehps-draw-sync.service"
SYSTEMD_TIMER="dehps-draw-sync.timer"

INTERVAL_SECONDS=900
HOT_INTERVAL_SECONDS=300
COLD_INTERVAL_SECONDS=3600
TIMEZONE=Asia/Shanghai
SHADOW_ATTESTATION="${DEHPS_FORWARD_SHADOW_ATTESTATION:-false}"
SHADOW_CAPTURE="${DEHPS_FORWARD_SHADOW_CAPTURE:-true}"
SHADOW_WORKERS="${DEHPS_FORWARD_SHADOW_WORKERS:-8}"

cd "$WORKER_DIR"
desired_commit="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
if [[ ! "$desired_commit" =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s invalid draw-sync systemd desired commit=%s\n' "$(date -Is)" "$desired_commit" >&2
  exit 1
fi
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain=v1 --untracked-files=all)" ]]; then
  printf '%s source worktree is dirty; refusing draw-sync systemd deployment\n' "$(date -Is)" >&2
  exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
  printf '%s systemctl is unavailable; refusing draw-sync systemd deployment\n' "$(date -Is)" >&2
  exit 1
fi

desired_launch_digest="$(
  .venv/bin/python -m dehps.draw_sync.launch_contract \
    --code-commit "$desired_commit" \
    --interval-seconds "$INTERVAL_SECONDS" \
    --hot-interval-seconds "$HOT_INTERVAL_SECONDS" \
    --cold-interval-seconds "$COLD_INTERVAL_SECONDS" \
    --timezone "$TIMEZONE" \
    --resume-on-event false \
    --shadow-attestation-enabled "$SHADOW_ATTESTATION" \
    --digest-only
)"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
desired_env="$tmp_dir/draw-sync.env"
desired_deployment="$tmp_dir/draw-sync-systemd-deployment.json"
desired_deployment_digest="$(
  .venv/bin/python -m dehps.draw_sync.systemd_deployment \
    --code-commit "$desired_commit" \
    --unit-path "$SOURCE_UNIT" \
    --timer-path "$SOURCE_TIMER" \
    --launch-contract-digest "$desired_launch_digest" \
    --shadow-attestation-enabled "$SHADOW_ATTESTATION" \
    --shadow-capture-enabled "$SHADOW_CAPTURE" \
    --shadow-worker-count "$SHADOW_WORKERS" \
    --write-environment "$desired_env" \
    --write-contract "$desired_deployment" \
    --digest-only
)"

if cmp -s "$SOURCE_UNIT" "$INSTALLED_UNIT" \
  && cmp -s "$SOURCE_TIMER" "$INSTALLED_TIMER" \
  && cmp -s "$desired_env" "$ENV_FILE" \
  && cmp -s "$desired_deployment" "$DEPLOYMENT_FILE" \
  && [[ "$(systemctl --user is-active "$SYSTEMD_TIMER" 2>/dev/null || true)" == "active" ]] \
  && [[ "$(.venv/bin/python -m dehps.draw_sync.launch_contract --verify-file "$LAUNCH_FILE" --digest-only 2>/dev/null || true)" == "$desired_launch_digest" ]]; then
  printf '%s draw-sync systemd already converged commit=%s deployment_contract=%s launch_contract=%s\n' \
    "$(date -Is)" "$desired_commit" "$desired_deployment_digest" "$desired_launch_digest"
  exit 0
fi

mkdir -p "$USER_UNIT_DIR" "$USER_CONFIG_DIR" "$LOG_DIR"
backup_dir="$tmp_dir/backup"
mkdir -p "$backup_dir"
for item in unit timer env deployment; do
  case "$item" in
    unit) source_path="$INSTALLED_UNIT" ;;
    timer) source_path="$INSTALLED_TIMER" ;;
    env) source_path="$ENV_FILE" ;;
    deployment) source_path="$DEPLOYMENT_FILE" ;;
  esac
  if [[ -e "$source_path" ]]; then
    cp -a "$source_path" "$backup_dir/$item"
    : > "$backup_dir/$item.exists"
  fi
done
timer_was_enabled="$(systemctl --user is-enabled "$SYSTEMD_TIMER" 2>/dev/null || true)"
timer_was_active="$(systemctl --user is-active "$SYSTEMD_TIMER" 2>/dev/null || true)"
service_was_active="$(systemctl --user is-active "$SYSTEMD_UNIT" 2>/dev/null || true)"
deployment_committed=false

restore_path() {
  local name="$1"
  local destination="$2"
  if [[ -e "$backup_dir/$name.exists" ]]; then
    cp -a "$backup_dir/$name" "$destination"
  else
    rm -f "$destination"
  fi
}

rollback() {
  local exit_code=$?
  if [[ "$deployment_committed" == true ]]; then
    return "$exit_code"
  fi
  systemctl --user stop "$SYSTEMD_TIMER" "$SYSTEMD_UNIT" >/dev/null 2>&1 || true
  restore_path unit "$INSTALLED_UNIT"
  restore_path timer "$INSTALLED_TIMER"
  restore_path env "$ENV_FILE"
  restore_path deployment "$DEPLOYMENT_FILE"
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  if [[ "$timer_was_enabled" == "enabled" ]]; then
    systemctl --user enable "$SYSTEMD_TIMER" >/dev/null 2>&1 || true
  fi
  if [[ "$timer_was_active" == "active" ]]; then
    systemctl --user start "$SYSTEMD_TIMER" >/dev/null 2>&1 || true
  fi
  if [[ "$service_was_active" == "active" ]]; then
    systemctl --user start "$SYSTEMD_UNIT" >/dev/null 2>&1 || true
  fi
  printf '%s draw-sync systemd deployment rolled back exit=%s\n' "$(date -Is)" "$exit_code" >&2
  rm -rf "$tmp_dir"
  return "$exit_code"
}
trap rollback EXIT

systemctl --user stop "$SYSTEMD_TIMER" "$SYSTEMD_UNIT" >/dev/null 2>&1 || true
mapfile -t residual_pids < <(pgrep -u "$(id -u)" -f 'scripts/run_draw_sync_watch.py' || true)
if [[ "${#residual_pids[@]}" -ne 0 ]]; then
  printf '%s unmanaged draw-sync watcher remains pids=%s; refusing overlapping deployment\n' \
    "$(date -Is)" "${residual_pids[*]}" >&2
  exit 1
fi

install -m 0644 "$SOURCE_UNIT" "$INSTALLED_UNIT"
install -m 0644 "$SOURCE_TIMER" "$INSTALLED_TIMER"
install -m 0600 "$desired_env" "$ENV_FILE"
systemctl --user daemon-reload
systemctl --user start "$SYSTEMD_UNIT"

observed_launch_digest="$(
  .venv/bin/python -m dehps.draw_sync.launch_contract \
    --verify-file "$LAUNCH_FILE" \
    --digest-only
)"
if [[ "$observed_launch_digest" != "$desired_launch_digest" ]]; then
  printf '%s draw-sync oneshot launch digest mismatch observed=%s desired=%s\n' \
    "$(date -Is)" "$observed_launch_digest" "$desired_launch_digest" >&2
  exit 1
fi
if [[ "$(tr -d '[:space:]' < "$VERSION_FILE")" != "$desired_commit" ]]; then
  printf '%s draw-sync oneshot version mismatch\n' "$(date -Is)" >&2
  exit 1
fi
.venv/bin/python - "$STATE_FILE" "$desired_launch_digest" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if state.get("status") != "ok" or state.get("error") is not None:
    raise SystemExit("draw-sync oneshot state is not ok")
launch = state.get("launch_contract") or {}
if launch.get("contract_digest") != sys.argv[2]:
    raise SystemExit("draw-sync oneshot state launch digest mismatch")
evaluation = state.get("forward_evaluation") or {}
if evaluation.get("status") != "ok":
    raise SystemExit("draw-sync oneshot forward evaluation is not ok")
if (launch.get("automatic_promotion_allowed") is not False):
    raise SystemExit("draw-sync oneshot unexpectedly authorizes promotion")
PY

mapfile -t residual_pids < <(pgrep -u "$(id -u)" -f 'scripts/run_draw_sync_watch.py' || true)
if [[ "${#residual_pids[@]}" -ne 0 ]]; then
  printf '%s oneshot left resident draw-sync watchers pids=%s\n' \
    "$(date -Is)" "${residual_pids[*]}" >&2
  exit 1
fi

systemctl --user enable --now "$SYSTEMD_TIMER"
install -m 0600 "$desired_deployment" "$DEPLOYMENT_FILE"
.venv/bin/python -m dehps.draw_sync.systemd_deployment \
  --verify-file "$DEPLOYMENT_FILE" \
  --unit-path "$INSTALLED_UNIT" \
  --timer-path "$INSTALLED_TIMER" \
  --environment-path "$ENV_FILE" \
  --digest-only >/dev/null
if [[ "$(systemctl --user is-active "$SYSTEMD_TIMER")" != "active" ]]; then
  printf '%s draw-sync timer is not active after deployment\n' "$(date -Is)" >&2
  exit 1
fi

deployment_committed=true
trap 'rm -rf "$tmp_dir"' EXIT
printf '%s draw-sync systemd converged commit=%s deployment_contract=%s launch_contract=%s timer=active\n' \
  "$(date -Is)" "$desired_commit" "$desired_deployment_digest" "$desired_launch_digest"
