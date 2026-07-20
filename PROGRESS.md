# PROGRESS.md - 断点续跑

更新时间: 2026-07-20

## 当前断点

M1/M2 三路线治理轮正在执行，授权为 Agent Request
`engineering-m1-roadmap-governance-e5ebffd`、execution `64`。本轮只改治理文档，不改代码、
Runtime、训练或生产状态。

## 已知当前状态

- 项目定位已校正: DEHPS 长期要训练成可审计的预测系统；当前阶段按假设检验、训练、回测和未来窗口验证来推进，不能提前宣称成熟预测能力。
- M1 Contract Runtime v1 capability 已接受；live freshness、三期 shadow cohort 和 backend
  promotion 仍按各自 gate 独立判断。
- commit `e5ebffd` 的最新完整 Worker 证据为 `1285 passed, 4 warnings`；本治理轮没有把它冒充
  新测试执行。
- 截至 2026-07-20 14:58 CST，observability-only run `20260720-124722` 已完成 14 轮，
  Recent-100 仍为 `3 / 3 / 4`，最近状态 `no_learning_lift`，production selection 未变化。
- `docs/roadmap.md` 保留历史 Round ledger；Runtime、Research、Knowledge 已使用独立 Roadmap。

## 下一位 agent 接手步骤

1. 运行 `git status --short`，以实时输出为准；若工作区不干净，按 `AGENTS.md` 停止并报告。
2. 阅读 `AGENTS.md` 和本文件，再决定是否需要更新 `TASK_PLAN.md`、`ACCEPTANCE.md`、`DECISIONS.md`、`RISKS.md`。
3. 对任何策略/训练/回测任务，先写出 hypothesis、baseline/null model、measurement、failure mode。
4. 完成后更新本文件的“最近进度”和“下一步”。

## 最近进度

- 2026-06-22: 根据爱因斯坦式假设检验框架和项目现状，创建根级 agent 协作规则文件。
- 2026-06-22: 校正项目定位措辞: 长期目标是预测系统，当前阶段是训练和验证，不是永久否定预测目标。
- 2026-06-22: 用户明确要求每次修改完代码都需要提交并推送；规则文件已同步该要求。
- 2026-06-22: 用户进一步校正定位: 允许投注建议，也允许将实验结果作为预测能力方向呈现；当前边界是未达训练目标时必须标注证据等级和风险。
- 2026-06-27: 自我迭代确认 Python worker、API、Web 测试和构建基线均通过；刷新过期 dirty-worktree 断点，避免后续 agent 误判当前状态。
- 2026-07-20: 接受 Contract Runtime v1 capability milestone；正式把 Runtime maturity 与
  Prediction Quality 分成独立目标函数。
- 2026-07-20: 开启 M2 Prediction Quality Improvement，基线 Recent-100 为 `3 / 3 / 4`。
- 2026-07-20: 建立 Runtime、Research、Knowledge Roadmap 和双 Dashboard 信息架构；实现仍需
  后续单独 Engineering Request。

## 下一步候选

- 以单独 Engineering Request 实现 Runtime/Research 双 Dashboard，不在本治理轮夹带代码。
- 以 Research Request 预注册 Recent-300 稳定性与 frozen walk-forward 证据合同，再决定是否
  实现新 Feature。
- 若后续训练出现停滞或候选族塌缩，按 `$gauss` / `$riemann` / `$gauss-riemann-dialogue` 规则先做诊断，再改策略逻辑。
- 若用户继续要求优化训练，优先诊断搜索空间是否在产生新候选族。
- 若用户要求提交，先区分本轮新增文档和既有训练/回测改动，避免夹带。
