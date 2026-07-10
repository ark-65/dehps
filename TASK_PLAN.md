# TASK_PLAN.md - 任务拆解

本文件用于后续 agent 断点接手。任务必须按小闭环推进，每轮有明确非目标、验证命令和产物。

## 当前总目标

把 DEHPS 持续推进为一个可审计的预测训练平台: 以透明特征、冻结规则、历史回测、null model 对照、训练/仪表盘可读、风险可追踪为基础，逐步验证是否具备未来预测价值。

长期训练增强目标：保持历史、canonical advisor 信号和 live supervisor `as_of_issue` 对齐；每 2 小时自我迭代检查训练进度、跨 supervisor continuity seed、停滞恢复、候选/排名多样性、source survival、冻结验证、null baseline、泄漏和 parser/sync/duplicate 状态。同历史、曾严格提高冻结主指标的 navigation candidate 必须在交接后重评，仍通过才续接 search base，且不得冒充 incumbent。只有可复现的新结构、冻结/前向证据改善或失败模式减少才算“变强”，持续计算本身不算。

## 工作流模板

每轮按以下顺序执行:

1. 定义问题: 写清 Core question、Hypothesis、Non-goals。
2. 固定边界: 确认样本空间、历史窗口、数据源、baseline/null model。
3. 最小实现: 只改完成该闭环所需的模块。
4. 验证: 运行相关测试、生成报告或 UI 证据。
5. 记录: 更新实验报告、进度、决策和风险。
6. 收束: 提交并推送本轮相关改动；若用户明确要求暂不提交或暂不推送，记录原因和断点。

## 优先任务池

### P0 - 保护当前工作区

- 每轮开始检查 `git status --short`，并以实时输出为准。
- 2026-06-27 自我迭代检查时工作区为干净状态；不要沿用过期的 dirty-file 列表作为当前事实。
- 若后续出现未提交改动，后续 agent 不得重置、覆盖或顺手格式化相关文件，除非任务明确要求处理该主题。

### P1 - 训练停滞诊断闭环

- 问题: 长轮数训练是否真的在探索新候选族，而不是重复评估相近配置？
- 基线: 当前训练 supervisor、target weight inversion 家族、已有 archive 表。
- 产物: 诊断报告或 round report，包含候选族分布、score 变化、失败样例。
- 验收: 相关 worker 测试通过，并能说明是否需要继续扩大搜索空间。

### P1 - Advisor 数据新鲜度闭环

- 问题: canonical KDJ/Ridge/Neural 信号是否与最新历史 issue 对齐，watchdog 是否会在信号落后时安全交接 supervisor？
- 基线: `weight-kdj-recent-1000-v1`、最新 `ssq_history` issue、当前 supervisor `--as-of-issue`。
- 非目标: 不新增 advisor，不放宽 frozen validation、null model 或 leakage gate。
- 产物: watcher 新鲜度状态、增量刷新日志、新 supervisor run id 和至少 1-2 个完整轮次。
- 验收: advisor 信号不超前且最多落后 1 个实际历史 issue；新 run 无运行错误，证据报告保留失败模式与不确定性。

### P1 - 动态 KDJ 回测闭环

- 问题: dynamic KDJ 相关改动是否形成可复现实验，而不是后验调参？
- 基线: frozen baseline + same keep-rate null control。
- 产物: Markdown/JSON 实验结果，记录配置快照和 missed issues。
- 验收: `test_dynamic_kdj_backtest.py` 相关测试通过，报告语言区分“训练中的预测假设”和“已验证的预测能力”。

### P2 - 仪表盘可读性与真实状态

- 问题: 前端显示的训练状态是否对应当前 live run，而不是陈旧 DB 行或启动噪声？
- 基线: 当前 API `ResearchService` 归一化边界和 training status hub。
- 产物: UI 截图或测试结果。
- 验收: API/Web 测试通过，长历史图表保持可扫读。

### P2 - 数据源与同步卫生

- 问题: 是否仍存在隐藏样例数据、隐式 fallback 或 raw API shape 泄漏？
- 基线: `zhcw --history` 和显式 CSV 回填。
- 产物: 清理报告和测试。
- 验收: 无真实数据时明确失败或要求显式输入，不悄悄换样例数据。

## 不做事项

- 允许投注建议作为未来产品方向或明确标注的实验输出，但必须绑定证据等级、风险说明和训练状态。
- 允许把实验结果表述为预测信号或候选预测能力；历史 lift 需要经过冻结规则和后续窗口验证后，才能提高预测置信度。
- 不把蓝球或外部物理特征直接并入主 leaderboard，除非先通过冻结 baseline 与 null control。
- 不在一个回合同时改训练、同步、API、前端和调度。
