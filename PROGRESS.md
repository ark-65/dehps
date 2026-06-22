# PROGRESS.md - 断点续跑

更新时间: 2026-06-22

## 当前断点

本轮新增根级协作文件:

- `AGENTS.md`: 总规则。
- `TASK_PLAN.md`: 任务拆解。
- `ACCEPTANCE.md`: 验收标准。
- `PROGRESS.md`: 断点续跑。
- `DECISIONS.md`: 技术决策。
- `RISKS.md`: 风险记录。

## 已知当前状态

- 项目定位已校正: DEHPS 长期要训练成可审计的预测系统；当前阶段按假设检验、训练、回测和未来窗口验证来推进，不能提前宣称成熟预测能力。
- 长期路线已存在于 `docs/roadmap.md`，已完成至少 Round 1 到 Round 9 的阶段记录。
- 根目录此前没有 `AGENTS.md`、`TASK_PLAN.md`、`ACCEPTANCE.md`、`PROGRESS.md`、`DECISIONS.md`、`RISKS.md`。
- 当前工作区已有未提交改动:
  - `apps/worker-python/dehps/optimization/dynamic_kdj_backtest.py`
  - `apps/worker-python/dehps/optimization/target_inversion.py`
  - `apps/worker-python/scripts/run_dynamic_kdj_backtest.py`
  - `apps/worker-python/scripts/run_training_supervisor.py`
  - `apps/worker-python/tests/test_dynamic_kdj_backtest.py`

## 下一位 agent 接手步骤

1. 运行 `git status --short`，确认上述未提交改动是否仍存在。
2. 若任务不是 dynamic KDJ、target inversion 或 training supervisor，不要修改或格式化上述文件。
3. 阅读 `AGENTS.md` 和本文件，再决定是否需要更新 `TASK_PLAN.md`、`ACCEPTANCE.md`、`DECISIONS.md`、`RISKS.md`。
4. 对任何策略/训练/回测任务，先写出 hypothesis、baseline/null model、measurement、failure mode。
5. 完成后更新本文件的“最近进度”和“下一步”。

## 最近进度

- 2026-06-22: 根据爱因斯坦式假设检验框架和项目现状，创建根级 agent 协作规则文件。
- 2026-06-22: 校正项目定位措辞: 长期目标是预测系统，当前阶段是训练和验证，不是永久否定预测目标。
- 2026-06-22: 用户明确要求每次修改完代码都需要提交并推送；规则文件已同步该要求。

## 下一步候选

- 检查 dynamic KDJ 未提交改动是否需要收束为一个可验收实验。
- 若用户继续要求优化训练，优先诊断搜索空间是否在产生新候选族。
- 若用户要求提交，先区分本轮新增文档和既有训练/回测改动，避免夹带。
