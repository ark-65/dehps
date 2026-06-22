# TASK_PLAN.md - 任务拆解

本文件用于后续 agent 断点接手。任务必须按小闭环推进，每轮有明确非目标、验证命令和产物。

## 当前总目标

把 DEHPS 持续推进为一个可审计的预测训练平台: 以透明特征、冻结规则、历史回测、null model 对照、训练/仪表盘可读、风险可追踪为基础，逐步验证是否具备未来预测价值。

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

- 检查并保留已有未提交改动。
- 当前已观察到 `apps/worker-python/dehps/optimization/dynamic_kdj_backtest.py`、`apps/worker-python/scripts/run_dynamic_kdj_backtest.py`、`apps/worker-python/tests/test_dynamic_kdj_backtest.py` 存在未提交修改。
- 后续 agent 不得重置、覆盖或顺手格式化这些文件，除非任务明确要求处理该主题。

### P1 - 训练停滞诊断闭环

- 问题: 长轮数训练是否真的在探索新候选族，而不是重复评估相近配置？
- 基线: 当前训练 supervisor、target weight inversion 家族、已有 archive 表。
- 产物: 诊断报告或 round report，包含候选族分布、score 变化、失败样例。
- 验收: 相关 worker 测试通过，并能说明是否需要继续扩大搜索空间。

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

- 不做投注推荐。
- 不把历史 lift 直接写成未来优势；只有冻结规则在后续窗口继续成立，才能提高预测置信度。
- 不把蓝球或外部物理特征直接并入主 leaderboard，除非先通过冻结 baseline 与 null control。
- 不在一个回合同时改训练、同步、API、前端和调度。
