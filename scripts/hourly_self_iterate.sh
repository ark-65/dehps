#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/ark/workspace/dehps"
CODEX_BIN="/home/ark/.nodenv/versions/24.16.0/bin/codex"
LOG_DIR="$REPO_ROOT/runtime/logs"
LOCK_FILE="$LOG_DIR/hourly_self_iterate.lock"
LAST_MESSAGE="$LOG_DIR/hourly_self_iterate.last.md"

mkdir -p "$LOG_DIR"

cd "$REPO_ROOT"

if [[ ! -x "$CODEX_BIN" ]]; then
  echo "$(date -Is) codex executable not found: $CODEX_BIN" >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) hourly self-iteration already running; skip."
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "$(date -Is) working tree is dirty; skip to avoid overwriting human or previous-agent work."
  git status --short
  exit 0
fi

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
- 每轮结束必须留下清晰结果：若有代码改动且测试通过，创建一个本地 git commit，提交信息以 "self-iterate:" 开头；不要 push。
- 若没有安全可做的改动，也不要硬改；写明阻塞原因。

请自主完成探索、修改、验证和本地提交。
PROMPT
