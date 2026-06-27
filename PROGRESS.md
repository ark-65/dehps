# PROGRESS.md - 断点续跑

更新时间: 2026-06-27

## 当前断点

本轮检查到工作区为干净状态；此前 2026-06-22 记录的 dynamic KDJ、target inversion、training supervisor 相关未提交改动已不再存在于 `git status --short` 输出中。

## 已知当前状态

- 项目定位已校正: DEHPS 长期要训练成可审计的预测系统；当前阶段按假设检验、训练、回测和未来窗口验证来推进，不能提前宣称成熟预测能力。
- 长期路线已存在于 `docs/roadmap.md`，已完成至少 Round 1 到 Round 9 的阶段记录。
- 根目录此前没有 `AGENTS.md`、`TASK_PLAN.md`、`ACCEPTANCE.md`、`PROGRESS.md`、`DECISIONS.md`、`RISKS.md`。
- 2026-06-27 自我迭代基线验证通过:
  - `apps/worker-python/.venv/bin/python -m pytest -q` -> 284 passed
  - `cd apps/api && npm test` -> 45 passed
  - `cd apps/web && npm test` -> 18 passed
  - `cd apps/api && npm run build` -> passed
  - `cd apps/web && npm run build` -> passed

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

## 下一步候选

- 若后续训练出现停滞或候选族塌缩，按 `$gauss` / `$riemann` / `$gauss-riemann-dialogue` 规则先做诊断，再改策略逻辑。
- 若用户继续要求优化训练，优先诊断搜索空间是否在产生新候选族。
- 若用户要求提交，先区分本轮新增文档和既有训练/回测改动，避免夹带。
