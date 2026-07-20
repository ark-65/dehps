# DECISIONS.md - 技术决策

本文件记录会影响后续 agent 行为的项目级决策。新决策应写明日期、背景、决定和后果。

## 2026-06-22 - 根级 agent 文档采用科学验收框架

背景: 项目已经进入多轮训练、回测、仪表盘和自动化阶段，需要让后续 agent 在断点续跑时保持同一套科学边界。

决定:

- 根目录使用 `AGENTS.md` 作为总规则入口。
- `TASK_PLAN.md`, `ACCEPTANCE.md`, `PROGRESS.md`, `DECISIONS.md`, `RISKS.md` 分别承载任务拆解、验收、断点、决策和风险。
- 所有策略和训练建议都必须先通过 hypothesis、baseline/null model、measurement、failure mode 的格式。

后果:

- 后续改动不应只写“优化效果更好”，必须说明相对于谁更好、在哪个窗口更好、失败在哪里。
- 文档更新本身也应遵守小闭环，不把计划文件写成无限膨胀的路线图。

## 2026-06-22 - DEHPS 预测目标与当前证据分层表述

背景: 用户明确指出项目未来需要做成预测系统，只是当前还不够成熟，正在训练。双色球红球 demo 的合法组合开奖前等概率，历史回测本身不能单独证明未来优势，但它是训练预测系统的必要证据层。

决定:

- 项目长期目标可以表述为“可审计的预测系统”“预测训练平台”或“预测型决策支持系统”。
- 当前阶段统一使用“预测假设”“预测信号”“训练中”“冻结规则验证”“历史过滤表现”“未来窗口检验”等分层表述。
- 允许投注建议作为未来产品方向或明确标注的实验输出；未达训练目标时必须带证据等级和风险说明。

后果:

- 报告里的 lift 先解释为历史窗口内的过滤表现和预测信号证据；若冻结规则在后续窗口继续成立，可记录为预测置信度提升证据。
- 候选号码是预测训练系统输出的候选假设，可作为实验性投注建议材料，但必须标注训练状态和风险。

## 2026-06-22 - Betting And Predictive Packaging Allowed With Evidence Labels

背景: 用户进一步校正定位，明确允许提供投注建议，也允许把实验结果包装成预测能力；当前只是还没有到达训练目标。

决定:

- 文档不再使用“禁止投注建议”或“禁止包装成预测能力”的绝对表述。
- 允许将实验结果作为预测信号、候选预测能力和实验性投注建议来呈现。
- 当前未达训练目标时，所有预测/投注表述必须保留证据等级、训练状态、不确定性和失败样本。

后果:

- 产品方向可以面向预测和投注建议演进。
- 工程验收仍以可复现训练、回测、未来窗口验证和泄漏检查为准。

## 2026-06-22 - 真实数据优先，隐藏 fallback 禁止

背景: 项目已有真实历史同步和数据库流程，样例数据会污染判断。

决定:

- 数据缺口应显式失败或要求显式输入。
- CSV 回填必须由参数或环境变量明确触发。
- API/前端通过服务层归一化数据形状。

后果:

- 后续 agent 不得为“跑通”而悄悄注入样例历史。
- 接口改动要优先保护前端不依赖 raw DB/JSONB 形状。

## 2026-06-22 - 探索性特征必须隔离

背景: 外部物理、玄学编码、神经模型或复杂权重容易造成过拟合和后验解释。

决定:

- 弱假设进入 parallel exploratory track。
- 进入主 leaderboard 前必须通过 frozen baseline 和 null control。

后果:

- 新特征先作为可关闭、可报告的实验分支。
- 不能因为单个历史窗口表现好就晋升为默认策略。

## 2026-06-22 - 代码改动必须提交并推送

背景: 用户明确要求每次修改完代码需要提交并推送代码。

决定:

- 每次代码修改完成后，agent 必须运行相关验证，提交本轮相关改动，并推送到远端。
- 文档/规则改动若影响后续工程协作，也应独立提交并推送。
- 若用户明确要求暂不提交或暂不推送，以用户最新指令为准，并记录断点。

后果:

- 默认交付不再停留在本地工作区。
- 提交前必须更严格地区分本轮文件、历史脏改动和生成产物。

## 2026-07-20 - Runtime、Research、Knowledge 使用独立目标与评价口径

背景: Contract Runtime v1 已经具备 Contract、Compiler、ABI、Unified Runtime Verifier、
VerifiedRuntimePackage、Kernel Planner、多后端和 Artifact Runtime 全链路。Recent-100 仍为
`3 / 3 / 4`，说明工程成熟度与预测能力是不同目标函数。

决定:

- 接受 [M1 Contract Runtime Complete](docs/milestones/m1-contract-runtime-complete.md) 为工程能力
  milestone，并开启 [M2 Prediction Quality Improvement](docs/roadmaps/research.md)。
- Runtime、Research、Knowledge 分别维护独立 Roadmap、KPI、证据和失败条件。
- Runtime 工作不承担 Recent-N、hit、rank 或 generalization KPI；Research 改善也不自动提高
  Runtime 成熟度。
- Dashboard 分为 Runtime Health 与 Research Quality；跨线流程指标单独展示，不计算综合分。
- Shadow 数值一致性归 Runtime Health；研究评估是否完成归 Research Process。
- Promotion Rate 只描述流程，不以越高越好为目标。
- 当前红球排名输出的 Expected Value 为 `not_defined`，直到独立经济合同被接受。

后果:

- 后续每轮必须声明唯一 owner lane，验收指标不得跨线偷换。
- M1 是 capability badge，不是永久绿色运行状态；缺失、陈旧或失败证据仍必须 fail closed。
- Recent-100 用于搜索选择，Recent-300 用于重叠窗口稳定性；真正未见 future issues 才支持
  generalization 置信度提升。
