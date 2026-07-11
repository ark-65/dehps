# 自溶蚀任务优化 Memory

这个项目级 memory 用于记录 DEHPS 自溶蚀 / 自我迭代任务的历史、操作规则和后续优化约束。

这里的“自溶蚀”指一个由调度器驱动的私有预测训练维护循环：持续、缓慢地蚀除 bug、陈旧假设、噪音产物、训练盲点和可观测性缺口。它可以围绕彩票预测信号做内部训练优化，但必须受合法样本空间、历史窗口、baseline/null model、泄漏检查、证据等级、风险、不确定性和失败案例约束。

## 当前约定

- 范围：`/home/ark/workspace/dehps`
- 执行脚本：`scripts/hourly_self_iterate.sh`
- 调度入口：用户 crontab 中的 `DEHPS two-hour self-iteration` 区块
- 频率：北京时间每 2 小时的第 `0` 分钟，`CRON_TZ=Asia/Shanghai`
- 日志：`runtime/logs/hourly_self_iterate.log`
- 最近一次回复：`runtime/logs/hourly_self_iterate.last.md`
- 锁：cron 层 `hourly_self_iterate.cron.lock`，脚本层 `hourly_self_iterate.lock`

## 安全不变量

- 开始先检查 `git status`。
- 如果工作区不干净，停止并说明原因；不要覆盖用户或上一轮 agent 的改动。
- 每轮只做一个小而可验证的改进。
- 每轮优先查看训练进度：运行或读取 `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 12`，并检查最新 training supervisor status/report。
- 每轮必须检查 `advisor_signal_freshness`。canonical advisor 信号落后历史时，优先检查同步流水线和 supervisor/heavy-job 锁交接；不得把旧信号下新增的轮数当作学习进步。
- supervisor 交接后必须检查 `continuity_seed`、`holdout_isolation` 和 `guard_continuity`。只允许重放同一历史指纹下、带相同隔离 protocol 且明确 `search_uses_frozen_validation=false` 的 search base，并在新进程启动时重新完整评估；旧的冻结主分 navigation candidate 不得续接。continuity seed 只能续接搜索，不能替换 incumbent 或绕过 promotion quarantine。同历史且没有正式晋级时，effective stagnation、rank homogeneity 和 overfit gate 必须跨 run 延续，不能因进程重启从 0 计数。有限 navigation 查询窗口只能提供最近的 rank-signature 几何，不能充当全局停滞计数；窗口饱和时必须沿用持久化的 effective stagnation 单调位置，使 restart batch/catalog offset 不回退。轮次完成以 watcher 的 `target_complete_round_recorded` 和数据库记录为准，不能只凭 `strategy_memory` 日志；未提交的部分轮次不得推进连续计数。
- restart batch/catalog offset 增长本身不是新覆盖证据；目录会循环，必须检查 `rank_homogeneity.restart_candidate_novelty`。同历史指纹下的精确候选哈希不得占用新的 restart 评估槽位；过滤生效时 `generated_reused_count` 必须为 0，替换候选仍须经过相同预筛、search-slice 导航约束和 promotion quarantine。
- 100 期回看必须拆成互不重叠的 search/frozen 窗口。搜索排序、advisor 锚点、continuity 和 search base 不得读取 frozen 结果；固定冻结集被多轮自适应查看后只能作为污染诊断，必须保持 `historical_holdout_quarantined=true`，直到取得真正前向未见证据。
- 每轮检查 `candidate_source_survival` 的生成、预筛、Top5、round-best 与冻结前沿。少于 4 个已落库轮次时只观察，少于 8 个同 run 轮次时不得新开来源预算实验；冻结前沿可以保留为诊断，但不得直接影响预算、候选选择、search base 或正式晋级。
- 来源预算复核必须同时读取 source-conversion、history-surface 和 final-performance 签名数及 `evidence_geometry`。八个原始轮次不自动等于八份独立性能证据；`automatic_budget_change_allowed` 必须保持 false，后续每次最多预声明一个来源预算变量。
- 每轮必须读取 `sequential_null_audit` 的覆盖率、legacy gap、candidate×band 算术不变量、最强 band 三层 p 值和 completeness blocker。账本无效时先修算术；账本只是 observed lower bound 时保持 noise risk，不能解释为预测能力或自动晋级。
- 优先修训练 watch / supervisor 运行错误、失败测试、明显 bug、类型错误和启动错误。
- 当训练停滞、发散、候选族塌缩或出现可疑跳变时，先做 `$gauss` / `$riemann` / `$gauss-riemann-dialogue` 诊断，再改策略逻辑。
- 诊断必须覆盖合法样本空间、历史窗口、baseline/null model、泄漏、重复组合、parser/sync 错误、后验阈值、候选多样性、共现结构和局部-全局一致性。
- 自主改动限制在 bug、诊断、现有参数边界或现有策略的明显安全约束；没有人工明确要求时，不新增模型、advisor、候选源或大策略。
- 不提交 `data/output` 或 `runtime` 下的生成产物，除非本轮明确要提升一个小型验收报告为正式产物。
- 先跑最小相关测试；只有改动面要求时再扩大测试范围。
- 若代码改动通过验证，从干净 `main` 切出 `<type>/self-iterate-YYYYMMDD-HHMM-<slug>` 分支，提交信息和 PR 标题使用同一个 Conventional Commit 前缀，然后创建 ready PR 并启用 squash auto-merge；不要直推 `main`。
- 自主提交由调度脚本设置 Git 身份：author/committer 使用 `ark-65 <25193106+ark-65@users.noreply.github.com>`，并通过 commit-msg hook 自动追加 `Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>`。
- 若没有安全可做的改动，记录阻塞原因，不强行为了变化而变化。

## 历史记忆

| 日期 | 记忆 |
| --- | --- |
| 2026-06-18 | 安装了调度器驱动的自我迭代：crontab 标记区块、`flock`、Codex CLI 执行和 clean-tree guard。 |
| 2026-06-18 | 修复 Codex exec 调用参数，使自动任务可以非交互运行。提交：`7081210`。 |
| 2026-06-22 | 修复 cron 环境，让自我迭代任务能通过 nodenv 路径找到 Node/Codex。提交：`667f01b`。 |
| 2026-06-22 | 自我迭代运行修复了仓库根目录 worker pytest 配置。提交：`e100e8c`。 |
| 2026-06-22 | 自我迭代运行把 backtest misses 从聚合级记录改成记录级。提交：`41da058`。 |
| 2026-06-22 | 更新自我迭代 prompt，使成功创建的自主提交会继续推送。提交：`ef895bc`。 |
| 2026-06-22 | 自我迭代运行显式记录同步校验失败。提交：`8b7c4b5`。 |
| 2026-06-30 | 调整调度器自我迭代提交归属：脚本导出 ark-65 GitHub noreply author/committer，并启用 commit-msg hook 自动追加 inhuman-0 co-author trailer，避免后续自主提交继续显示为 `Ark Codex <codex@local>`。验证：`bash -n scripts/hourly_self_iterate.sh`、临时仓库 hook 提交冒烟。 |
| 2026-06-30 | 调整自我迭代目标：从普通维护优先改为训练进度优先、Gauss/Riemann 数学诊断优先的私有预测训练维护循环；自主改动限制在小修、诊断和现有策略安全边界。验证：`bash -n scripts/hourly_self_iterate.sh`、`apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`、`git diff --check`。 |
| 2026-07-01 | 调整自我迭代发布流程：成功改动不再直推当前分支，而是从 `main` 切 `<type>/self-iterate-*` 分支、提交带 co-author trailer 的 Conventional Commit、创建 ready PR 并启用 squash auto-merge，以便 Pair Extraordinaire 统计 co-authored merged PR。验证：`bash -n scripts/hourly_self_iterate.sh`、`apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_self_iteration_publish_pr.py`。 |
| 2026-07-10 | 把训练持续增强设为长期目标：自我迭代必须审计 advisor 信号新鲜度、round repetition、rank homogeneity、source survival、冻结验证和泄漏；信号落后时通过受控 supervisor 交接增量刷新，而不是继续用旧信号空转。 |
| 2026-07-11 | 区分 restart batch 编号与真实候选新颖度：30 项目录会循环，必须以同历史候选哈希去重和 `restart_candidate_novelty` 证明新增覆盖，不能把重复确定性评估当作探索。 |
| 2026-07-11 | 审计发现同一组 20 个冻结期次在同历史下被 17 个 run、202 个轮次反复查看，已不再是未见 holdout；后续强制 search/frozen 隔离，冻结结果仅用于被隔离的晋级诊断，并在真正前向证据到来前保持 quarantine。 |
| 2026-07-11 | 自我迭代配置开始强制消费来源预算证据几何与 sequential-null 覆盖审计：区分转化路径变化和重复性能面，显式检查 legacy/adaptive/sequential 缺口，并禁止自动预算变更或自动晋级。 |
| 2026-07-10 | 增加跨 supervisor 搜索连续性：持久化轮内 decision candidate，恢复同历史且冻结主指标严格提升的 navigation candidate；新进程必须重评后才能用作 search base，incumbent 与 promotion gate 不变。 |
| 2026-07-10 | 增加当前 run 的候选来源转化窗口：累计 generated → prefilter → Top5 → round-best，至少 4 轮后才判断 narrow/diverse；避免用单轮或混入旧信号的跨 run 统计贸然改预算。 |
| 2026-06-22 | 修复训练 supervisor 的 target inversion 锚点：若本轮 best 只是历史 best 重放，改用本轮 challenger 做反推锚点。验证：`apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests -q` 通过 `164 passed`；live run `20260622-103001` round 1 写入 `anchor.source=challenger_best`，round 2 status 显示 `candidate_budget.target_weight_inversion=4`。 |
| 2026-06-22 | 调整训练节奏：初期 24 轮使用 large/medium 大步长，后期逐步退火到 small/micro；同时把 retained best 和 moving search base 分离，没刷新 best 时也用 rank-vector 不同的 challenger 推进下一轮 search base。验证：`apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests -q` 通过 `167 passed`。 |
| 2026-06-22 | 修复 moving search base 的 A/B 回跳：选择下一轮 search base 时排除当前和最近 search base，优先选 rank-vector 不同的新 challenger。验证：`apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests -q` 通过 `169 passed`；live run `20260622-112552` R1 `37713bad -> fdacf9ec`，R2 `fdacf9ec -> f88482b2`。 |

## 如何更新这个 Memory

当自溶蚀任务修改了维护循环、改变了保护规则，或产出了值得追踪的自主修复时，在“历史记忆”表格追加一行。

每条记录应包含：

- 日期。
- 改了什么。
- 证据：commit hash、测试命令、日志路径或 DB/status 检查。
- 是否影响后续自我迭代行为。

记录要具体。优先写精确路径、命令和提交哈希，少写“优化了自动化”这种不可复核描述。

## 注意点

- clean-tree guard 是刻意设计，不要为了强行推进而删除它。
- 自溶蚀任务允许跳过；安全跳过好过自主覆盖。
- 如果反复跳过，先查 `git status --short`，把无关改动提交或清理掉。
- `data/output` 下生成物通常是本地证据，不是提交目标。
- 长训练状态要优先看 live process 和 status file，再参考 DB 快照。

## 常用命令

```bash
crontab -l
tail -n 120 runtime/logs/hourly_self_iterate.log
cat runtime/logs/hourly_self_iterate.last.md
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
git status --short
git log --oneline --grep='self-iterate' -n 20
```
