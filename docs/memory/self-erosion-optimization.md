# 自溶蚀任务优化 Memory

这个项目级 memory 用于记录 DEHPS 自溶蚀 / 自我迭代任务的历史、操作规则和后续优化约束。

这里的“自溶蚀”指一个由调度器驱动的维护循环：持续、缓慢地蚀除 bug、陈旧假设、噪音产物和可观测性缺口。它不是彩票预测机制。

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
- 优先修 bug、失败测试、启动错误、陈旧假设、噪音产物和可观测性缺口。
- 不提交 `data/output` 或 `runtime` 下的生成产物，除非本轮明确要提升一个小型验收报告为正式产物。
- 先跑最小相关测试；只有改动面要求时再扩大测试范围。
- 若代码改动通过验证，提交信息使用 `self-iterate:` 前缀，并推送到当前 upstream 分支。
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
git status --short
git log --oneline --grep='self-iterate' -n 20
```
