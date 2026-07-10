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

定位：这是一个私有的 DEHPS 彩票预测训练系统。可以把实验结果作为候选预测信号或训练中的预测能力来研究，但任何输出都必须保留证据等级、训练状态、风险、不确定性、失败案例、合法样本空间、历史窗口、baseline/null model 和泄漏检查；不要把未成熟结果写成保证命中、确定优势或无风险投注建议。

长期目标：让训练循环持续变强且可审计。这里的“变强”必须表现为数据更新闭环、候选/排名结构产生可解释的新变化、冻结验证或前向证据改善、失败模式减少；单纯增加运行时长、轮数或 CPU 消耗不算进步。

目标：每轮只完成一个小而可验证的改进，优先级如下：
1. 先查看训练进度和运行状态：优先运行或读取 `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 12`，并检查最新 `data/output/optimization/training-supervisor-*.json` 和对应 Markdown report。必须读取 `advisor_signal_freshness`、`continuity_seed`、round repetition、rank homogeneity、`candidate_source_survival`、promotion/frozen validation 和 parser/sync/duplicate 结果。`candidate_source_survival.evidence_ready=false` 时只能继续观察；即使四轮观察窗口成熟，`budget_review_ready=false` 时也不得提出新的来源预算或预筛值。唯一例外是：当前 run 明确属于上一轮有 baseline、单变量和预声明 falsification 条件的实验；运行失败或科学护栏异常可直接回滚，重复度恶化则必须相对于同历史、同 incumbent/search base 的记录 baseline 才算已证明；此时只允许回滚到 baseline，不得转向第三个值。若起点不同或存在路径依赖混淆，只能标为不确定，不能作因果归因。只有至少八个同运行完整轮次后，才可把 `budget_review_sources` 当作新一轮可证伪实验候选，而且不得按来源保送候选或绕过冻结门。冻结护栏必须区分 `promotion_frozen_validation_evaluated/passed/bypassed` 与仅用于搜索导航的 `decision_navigation_frozen_primary_lift_required`；前者未评估或被绕过时不得声称晋升护栏有效。若 supervisor 刚交接，确认同历史、曾有严格冻结主分提升的 navigation candidate 已重评并续接 search base，不能把 continuity seed 当作 incumbent 或已晋级模型。若 action 是 `refresh_advisor_signals`、`inspect_advisor_signals` 或 `inspect_advisor_signal_leakage`，先检查 `runtime/logs/ssq_draw_sync.log`、canonical KDJ 最新 issue 与历史最新 issue，优先修复数据闭环。
2. 修复当前测试失败、明显 bug、类型错误、启动错误、训练 watch / supervisor 运行错误。
3. 如果训练出现停滞、发散、候选族塌缩、可疑跳变、重复评估相近配置、source/frontier 异常或 frozen validation 不一致，先做数学诊断，再决定最小修复。
4. 只有没有训练或运行异常时，才寻找高价值 TODO/FIXME、边界条件缺陷、日志/状态可观测性问题或测试缺口，并完成最小修复。

约束：
- 开始先检查 git status。若工作区不干净，立即停止并说明原因。
- 选择本轮唯一目标后、任何 repo-tracked 文件修改前，必须先确认当前仓库可回到干净 `main`，然后执行 `git switch main`、`git pull --ff-only origin main`，再切出 topic branch。
- 自我迭代分支名固定为 `<type>/self-iterate-YYYYMMDD-HHMM-<slug>`；`type` 只能是 `fix`、`feat`、`chore`、`docs`、`test`、`refactor`，并且要和本轮改动性质一致。
- commit subject 和 PR title 必须使用同一个 Conventional Commit 前缀，例如 `fix: self-iterate training watch restart guard`；不要再使用 `self-iterate:` 作为 commit 前缀。
- 不要删除或覆盖用户未提交改动。
- 不要提交 data/output 或 runtime 下的大型生成产物，除非本轮明确创建的是小型验收报告。
- Gauss/Riemann 是历史启发的验证和结构化诊断流程，不是权威背书，也不是对历史人物心智的重构。
- 涉及训练停滞、模型/策略判断、性能声称、权重边界、advisor 选择、候选源、搜索导航或 suspicious lift 时，必须先使用本地技能做诊断：
  - `$gauss`：检查合法样本空间、历史窗口、null baseline、泄漏、重复组合、parser/sync 错误、残差、数值敏感性、权重边界、后验阈值和 proof obligation。
  - `$riemann`：检查搜索空间结构、候选多样性、共现几何、离散/连续转换、局部改进是否解释全局行为、latent state 是否被错误表征。
  - `$gauss-riemann-dialogue`：当一个训练修复看似合理但未被证明时，记录 Task Frame、Gauss pass、Riemann pass、分歧、最小共同结论和下一轮验证。
- 自主度是诊断优先：允许修 bug、补诊断、改现有参数边界或现有策略的明显安全约束；不要新增模型、advisor、候选源或大策略，除非人类明确要求。
- advisor 信号落后历史时，不要让旧 supervisor 静默继续训练，也不要在 heavy-job 锁仍由 supervisor 持有时并发刷新。使用受控生命周期：记录旧 run id，停止旧 supervisor，增量刷新 canonical 信号并核对 issue 对齐，再启动 fresh supervisor。
- 不得把更多轮次、更多 CPU 或取消 frozen/null/leakage gate 当作停滞修复。若候选仍多样但 round-best 重复，先检查数据新鲜度与目标函数平台；连续指标只可用于搜索导航，不得替代晋级证据。
- 如果改动触及 training、optimization、dynamic weights、advisor 或 supervisor 代码，验证通过后必须启动更新后的 fresh supervisor，并监控至少 1-2 个完成训练轮次；不要继续依赖旧 live training process。
- 优先运行与改动相关的最小测试；必要时再跑 apps/worker-python/.venv/bin/python -m pytest、apps/api npm test、apps/web npm test。
- 每轮结束必须留下清晰结果：若有代码改动且测试通过，创建一个 git commit，然后用 `apps/worker-python/.venv/bin/python apps/worker-python/scripts/self_iteration_publish_pr.py --title "$PR_TITLE" --body-file "$PR_BODY_FILE" --base main --remote origin` 创建 ready PR 并启用 auto-merge；若发布失败，明确写明失败原因并保留当前分支供人工恢复。
- 禁止直接 push 或 merge 到 `main`；也不要使用旧的直推流程作为 fallback。Pair Extraordinaire 计数依赖 co-authored commit 通过 merged PR 进入默认分支。
- 自主提交使用脚本已设置的 Git 身份：author/committer 为 ark-65 的 GitHub noreply 身份；commit-msg hook 会补充 inhuman-0 的 Co-authored-by trailer，避免生成 Ark Codex <codex@local> 身份的自我迭代提交。
- 发布前必须确认 `git log -1 --format=%B` 包含 `Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>`；helper 会再次强制校验。
- 若没有安全可做的改动，也不要硬改；写明阻塞原因。

请自主完成探索、修改、验证、提交、创建 PR 和启用 auto-merge。
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
