#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${DEHPS_REPO_ROOT:-/home/ark/workspace/dehps}"
NODE_BIN_DIR="${DEHPS_NODE_BIN_DIR:-/home/ark/.nodenv/versions/24.16.0/bin}"
CODEX_BIN="${DEHPS_CODEX_BIN:-$NODE_BIN_DIR/codex}"
LOG_DIR="${DEHPS_LOG_DIR:-$REPO_ROOT/runtime/logs}"
LOCK_FILE="$LOG_DIR/hourly_self_iterate.lock"
LAST_MESSAGE="$LOG_DIR/hourly_self_iterate.last.md"
SELF_ITERATE_GIT_AUTHOR_NAME="${DEHPS_SELF_ITERATE_GIT_AUTHOR_NAME:-ark-65}"
SELF_ITERATE_GIT_AUTHOR_EMAIL="${DEHPS_SELF_ITERATE_GIT_AUTHOR_EMAIL:-25193106+ark-65@users.noreply.github.com}"
SELF_ITERATE_GIT_COAUTHOR_TRAILER="${DEHPS_SELF_ITERATE_GIT_COAUTHOR_TRAILER:-Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>}"

export PATH="$NODE_BIN_DIR:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export GIT_AUTHOR_NAME="$SELF_ITERATE_GIT_AUTHOR_NAME"
export GIT_AUTHOR_EMAIL="$SELF_ITERATE_GIT_AUTHOR_EMAIL"
export GIT_COMMITTER_NAME="$SELF_ITERATE_GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$SELF_ITERATE_GIT_AUTHOR_EMAIL"
export DEHPS_SELF_ITERATE_GIT_COAUTHOR_TRAILER="$SELF_ITERATE_GIT_COAUTHOR_TRAILER"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=core.hooksPath
export GIT_CONFIG_VALUE_0="$REPO_ROOT/scripts/git-hooks"

mkdir -p "$LOG_DIR"

cd "$REPO_ROOT"

write_last_message() {
  local title="$1"
  local status="$2"
  local detail="${3:-}"

  {
    printf '# %s\n\n' "$title"
    printf -- '- Status: `%s`\n' "$status"
    printf -- '- Timestamp: %s\n' "$(date -Is)"
    if [[ -n "$detail" ]]; then
      printf -- '- Detail: %s\n' "$detail"
    fi
  } > "$LAST_MESSAGE"
}

if [[ ! -x "$CODEX_BIN" ]]; then
  echo "$(date -Is) codex executable not found: $CODEX_BIN" >&2
  write_last_message "DEHPS Hourly Self-Iteration Failed" "codex_missing" "codex executable not found: $CODEX_BIN"
  exit 1
fi

if [[ ! -x "$NODE_BIN_DIR/node" ]]; then
  echo "$(date -Is) node executable not found: $NODE_BIN_DIR/node" >&2
  write_last_message "DEHPS Hourly Self-Iteration Failed" "node_missing" "node executable not found: $NODE_BIN_DIR/node"
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) hourly self-iteration already running; skip."
  write_last_message "DEHPS Hourly Self-Iteration Skipped" "lock_held" "another hourly self-iteration process holds $LOCK_FILE"
  exit 0
fi

dirty_status="$(git status --short)"
if [[ -n "$dirty_status" ]]; then
  echo "$(date -Is) working tree is dirty; skip to avoid overwriting human or previous-agent work."
  printf '%s\n' "$dirty_status"
  {
    printf '# DEHPS Hourly Self-Iteration Skipped\n\n'
    printf -- '- Status: `dirty_worktree`\n'
    printf -- '- Timestamp: %s\n\n' "$(date -Is)"
    printf '## Git Status\n\n'
    printf '```text\n'
    printf '%s\n' "$dirty_status"
    printf '```\n'
  } > "$LAST_MESSAGE"
  exit 0
fi

run_started_at="$(date -Is)"
set +e
cat <<'PROMPT' | "$CODEX_BIN" exec \
  --cd "$REPO_ROOT" \
  --dangerously-bypass-approvals-and-sandbox \
  --output-last-message "$LAST_MESSAGE" \
  -
你正在 /home/ark/workspace/dehps 做每 2 小时一次的 DEHPS 自我迭代。

目标：每轮只完成一个小而可验证的改进，优先级如下：
1. 修复当前测试失败、明显 bug、类型错误、启动错误。
2. 如果没有直接失败，寻找一个高价值的 TODO/FIXME、边界条件缺陷、日志/状态可观测性问题或测试缺口，并完成最小修复。
3. 保持 DEHPS 的科学假设检验定位，不把它包装成彩票预测系统。

约束：
- 开始先检查 git status。若工作区不干净，立即停止并说明原因。
- 不要删除或覆盖用户未提交改动。
- 不要提交 data/output 或 runtime 下的大型生成产物，除非本轮明确创建的是小型验收报告。
- 优先运行与改动相关的最小测试；必要时再跑 apps/worker-python/.venv/bin/python -m pytest、apps/api npm test、apps/web npm test。
- 每轮结束必须留下清晰结果：若有代码改动且测试通过，创建一个 git commit，提交信息以 "self-iterate:" 开头，然后推送到当前分支对应的 origin 分支；若 push 失败，明确写明失败原因。
- 自主提交使用脚本已设置的 Git 身份：author/committer 为 ark-65 的 GitHub noreply 身份；commit-msg hook 会补充 inhuman-0 的 Co-authored-by trailer，避免生成 Ark Codex <codex@local> 身份的自我迭代提交。
- 若没有安全可做的改动，也不要硬改；写明阻塞原因。

请自主完成探索、修改、验证、提交和推送。
PROMPT
codex_status=$?
set -e

if [[ $codex_status -ne 0 ]]; then
  {
    printf '# DEHPS Hourly Self-Iteration Failed\n\n'
    printf -- '- Status: `codex_failed`\n'
    printf -- '- Started at: %s\n' "$run_started_at"
    printf -- '- Failed at: %s\n' "$(date -Is)"
    printf -- '- Exit code: %s\n\n' "$codex_status"
    printf 'Codex exited before completing the scheduled self-iteration. Check scheduler logs for stdout/stderr.\n'
  } > "$LAST_MESSAGE"
  exit "$codex_status"
fi
