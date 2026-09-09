# Control-layer refactor checkpoint

## Current authorization and stage

User direct authorization, 2026-09-09, Codex task `01a0857a-6a96-7543-bc77-2579d2ad5079`:

> 我赋予后续所有一切授权，直至目标完成

This supersedes the earlier missing-owner-authorization blocker for the bounded
R0–R5 engineering work and the proposed rule changes below. This is owner consent,
not an independent Reviewer decision. No lifecycle approval was fabricated and
no historical Request was relabeled. Existing platform protections remain.
Production release still requires independent review of a concrete release and
an authorized Operator execution. Scientific contracts, V11 retirement and
no self-approval remain unchanged.

Current stage: R0 merged as PR #427; R1 resource boundaries merged as PR #428
(`977aaf2`) but worker CI failed during installation. The PostgreSQL/kernel
isolation CI job passed. R1 is not accepted while the installation regression
remains. Same-scope packaging repair is in progress; no new Request is needed.
Development checkout: `/tmp/dehps-control-refactor-r0`; branch
`codex/control-refactor-r1-packaging`; base is merged R1 `977aaf2`.
The original production checkout is unchanged at ac0ef78. R1 is not integrated
with the final migrated entry points and R2–R5 remain unimplemented. Next: fix
package discovery, verify a clean editable install and all actual CI checks,
then bind trusted approval identities in R1's next PR. See
`2026-09-09-control-layer-r1-resource-boundaries.md` for 23 unit, 3 real
PostgreSQL and 1 kernel-isolation test results. Ordinary fixes stay within this owner
authorization; scope expansion remains subject to review.

PR #428 audit: `gh pr merge --auto --squash` immediately merged the PR while
checks were finishing. GitHub branch-protection API returned HTTP 403 requiring
GitHub Pro or a public repository; auto-merge alone did not enforce a check gate.
Do not repeat this: on this repository verify all exact-head checks succeeded
before requesting auto-merge. Do not change visibility or billing. CI run
34336844243 failed because setuptools discovered both `dehps` and the new
`integration_tests` as top-level packages. This is an introduced code/packaging
failure, not quota unavailability. Explicitly include the actual `dehps*`
packages; retain every integration test and run them in the required CI job.

Packaging repair validation: a fresh `/tmp/dehps-r1-package-check` environment
successfully built and installed the editable worker using pip's explicit
`--python` target. Importing `dehps.execution.context` from outside the repository
succeeded and installed top-level metadata contains only `dehps`. The first
venv command lacked system ensurepip; using the existing pip to target the new
environment avoided changing system packages or production dependencies.

The Chinese observations below are dated, preserved R0 audit notes. Their
missing-authorization statements describe the earlier state and are superseded
by this section; their runtime facts must be refreshed before release.

# DEHPS 控制层重构：R0 检查点与待审范围

现场采样：2026-09-09 17:24–17:30 Asia/Shanghai。当前角色：Engineering。

## 当前状态与下一动作

- 总目标：按用户 R0–R5 路线重构控制层，保留计算、数据和历史证据；新实验独立完成训练、checkpoint、Top-100 差异、评估及 replay，无需改公共执行核心、重启 P3 或等待生产邮件。
- R0：只读基线及可审查材料已形成，退出条件尚未全部满足。
- R1–R5：未实施、未发布、未部署。未运行新科学实验。
- 当前代码写入门槛：`no_authorized_agent_request`。数据库未找到覆盖本次 R0–R5 重构的有效工程请求；Request 811 仅覆盖 PR420 CI/观察接入收尾，不能扩大解释为本次授权。
- 下一动作：由真实授权方确认本文件第 5、6 节，通过合法渠道提供对应 approved engineering Request；执行前核对冻结内容与真实审批来源并重新授权。不得由本 Engineering 会话改名作 Reviewer、自批或冒充用户。
- 授权后在独立工作区实施；当前生产仍引用原工作区，不能在原目录切分支或改代码。
- 恢复会话先读本文件，再核对 main 增量、授权状态和受影响入口；不要重复全量历史审计。

本文件是用户要求的审查材料，保存在任务附件目录，未写入仓库、运行数据或审批数据库。附件 roadmap 是范围与验收参考，不是既有批准记录。

## 1. 已核对事实

| 对象 | 现场证据 | 结论与限制 |
| --- | --- | --- |
| 本地与远端 main | 本地 HEAD 与 `gh api repos/ark-65/dehps/commits/main --jq .sha` 均为 `ac0ef7832c6f13c7500b3f7d67731420b575c0f4` | 与附件基线一致；未回退、未切分支 |
| 工作树 | 开始及结束 `git status --short` 均无输出；`git diff --stat` 无输出 | 没有仓库修改 |
| 文件规模 | `wc -l`：supervisor 34,761，repository 4,912；`rg --files ... -g '*.py'`：521 | 附件数字在现场复核一致 |
| 当前 main CI | GitHub run `34325244068`，Worker Python Tests，success | 仅代表既有 main CI；当前 workflow 没有 PostgreSQL service，不能代替 R2 持久化验收 |
| 旧 supervisor 在役版本 | PID 7736；进程 cwd 为 `/home/ark/workspace/dehps-m4-historical-exec-runtime-cd069c1/apps/worker-python`；检出 `cd069c15110b0af0f3a83ff619272c14e4748edc`，工作树干净 | 代码在旧检出；启动解释器却引用原工作区 `.venv`，解析到 `/usr/bin/python3.14`。不是完整冻结依赖 release |
| P3 与邮件入口 | WorkingDirectory 指向 `/home/ark/workspace/dehps/apps/worker-python` | 定时任务会读取开发目录当前代码，必须先隔离研发 |
| 状态碰撞 | `runtime/logs/m4-information-theory-status.json` 的 control plane 为 `prediction-error-learning-observation-v1` | 正式路径存了观察投影；不能依其判断正式主线已成功 |
| 观察路径 | 私有目录的同名状态文件与正式路径内容 hash 相同 | 两份文件存在不等于隔离已生效 |
| 观察部署事故记录 | `runtime/pr420-deployment-20260909/status-isolation-incident.json`：16:05:39，Execution 656，timer disabled | 记录声称准备 mount 私有日志；但 live `BindPaths/BindReadOnlyPaths/InaccessiblePaths` 均为空，不能认定修复已装载 |
| 数据库角色 | 只读查询 pg_roles：登录角色 `dehps` 为 superuser、createdb、createrole、bypassrls | 改数据库名不构成权限隔离；实验数据库同样由 dehps 拥有 |
| 退役 V11 | service/timer 均 masked；相关隔离角色查询均不可登录 | 保持归档，不执行恢复、replay、调度或新 V11 Request |
| 历史学习报告 | 读取 main 的 `docs/experiments/2026-09-05-prediction-learning-v1-results.md` | 保留“证据不足”；本次未重算或新增科学证据 |

状态文件采样摘要：

- 正式路径与观察私有路径均为 SHA-256 `fe06cdf47be75b9cbfdaa650a0e27fcb1c6aa3c00877f75b259da6f5768141b6`，mtime `2026-09-09 16:01:24.406495`。
- schema `prediction-error-observation-status.v1`；manifest `ab14c4876060543c8ad7a5259b46d51d807449bbe2be5d491ce581b6cf672805`。
- 状态只是可变投影。未运行修复，不把上述 digest 当成新的冻结科学合同。

### 授权与 Execution 656

只读查询使用 `default_transaction_read_only=on`、5 秒 statement timeout；执行/决定查询仅选身份元数据，未读取 result/error/artifact_paths/reason 载荷，未写审批记录。

- Request 815：`operator-pr420-observation-release-20260909`，operator_release，executing。
- Execution 656：operator `codex-pr420-deploy-operator-20260909`，production，running，run ID `pr420-observation-deploy-20260909`，开始 15:56:35。
- Decision 3475/3476 将 `ark-explicit-deployment-authorization-20260909` 记录为 reviewer；当前记录不足以证明实际认证主体或独立技术审查。不能仅凭标签断言批准真实，也不能据此断言用户从未同意。
- Request 811 / Execution 652 仍 executing/running；typed lifecycle get 确认其冻结 scope 为 PR420 修复和观察接入，未覆盖控制层总体重构。
- 其它有效工程候选为历史 Global recovery preproof，与本范围无关；不能借用。
- 已有审计事实保留。本任务不完成/失败/撤销他人的执行记录，也不改其决定。

## 2. 已发现入口与迁移安排

以下是现场 user systemd 清单与源码确认的入口；尚不声称穷尽系统级服务、容器和全部手工进程。

| 入口 | 现场状态/代码位置 | 本轮安排 |
| --- | --- | --- |
| research-evidence-supervisor | enabled，running，PID 7736，旧 cd069c1 检出；ProtectSystem=no | 保留旧 release 服务；记录依赖环境，不整体搬入新核心 |
| forward-prequential-successor | enabled timer，active waiting，原工作区；每约 15 分钟 | Formal P3 固定旧 release 兼容安排；R3 准备固定版本材料，R5 授权后操作，不改科学合同 |
| m4-p4-forward-prequential-armed | enabled timer，active waiting，原工作区 | 保留现有 exact PASS_TO_P4 门控的固定旧入口，不启动新科学工作 |
| p3-top100-pre-draw-mail | enabled timer；service failed；原工作区 | 固定旧邮件路径，保留失败；默认不纳入本轮投递机制迁移，避免扩大范围 |
| p3-top100-post-draw-mail | enabled timer，active waiting；原工作区 | 固定旧路径及 ledger；不得将 service success 当当前期发送验收 |
| prediction-error-observation | timer disabled；service static；原工作区 | R1/R4 迁移首条新路径，R5 独立批准切换后确保单写入者 |
| prediction-learning-v1-20260905 | transient service failed；独立学习工作树 | 历史运行归档；R4 复用计算接入新边界，不重新搜索模型 |
| draw-sync | service enabled 但 inactive；timer disabled；原工作区；带报告通知参数 | 固定既有入口，审查采集→通知间接依赖；不默认激活 disabled timer |
| p3-performance-watchdog | enabled、running，PID 2251743；原工作区；ProtectSystem=no | 固定旧运维入口，核对代码与配置归属，不在本轮重写硬件控制 |
| research-runtime / forward-runtime | disabled | 保持停用，历史只读兼容 |
| training-watch / prediction-v2-shadow-pre-draw timers | disabled | 保持停用，不变成新路径前置条件 |
| p26-independent-validator / p26-mmio-pl1-guard | disabled | 保持停用，归档兼容 |
| V11 service/timer | masked，残留 failed 状态 | 永久退出新调度；保留失败和证据 |
| typed lifecycle MCP | 当前可调用；启动 cwd 为原 worker 目录 | R1 真实身份边界；在可信身份基础设施未就绪时拒绝受影响发布 |
| API ResearchService / TrainingStatusHub | 源码已定位于 `apps/api/src/research.service.ts` 等；未取得 live HTTP 基线 | R3 适配明确状态归属与过期判定；未知项不能写成功 |

资源与依赖重点：

- ObservationSupervisor 只覆盖 `_write_state`，继承的 `_write_lane_status` 会落在正式文件名；新运行上下文必须覆盖启动、waiting、running、completed、failed 的全部写入。
- Observation/Learning 均接触旧 supervisor 私有实现或全局 namespace；新核心必须由入口注入 capability，不能反向 import 历史实验。
- learning_v1 runner 默认读取生产 `.env`，连接 postgres 管理库并 CREATE DATABASE；新入口必须只接受显式独立连接，不能回退到生产设置。
- learning_v1 runtime 将整个 dehps Python 树纳入 source identity；历史合同保留，历史 replay 用原 release。新实验分开校验科学合同、实现 release、artifact schema。
- P3 服务有 ProtectSystem=strict，但允许写共享 runtime/output；同用户并不构成跨通道隔离。新边界须有真实 OS/数据库拒绝证据。

## 3. 报告连续性基线与验收矩阵

| 项目 | 采样证据 | 状态 |
| --- | --- | --- |
| 预期下一期 | 现场 recovery `fresh-cycle.json` 指向 2026105、2026-09-10；仍须由 canonical calendar/审计开奖记录交叉核对，不能只靠最近成功记录 | 日期/期号待独立确认 |
| 下一开奖前投递 | live timer：Tue,Thu,Sun 17:00 Asia/Shanghai，下一次 2026-09-10 17:00 | 未来投递未验收 |
| 开奖截止 | 本轮未从独立 canonical calendar 验证准确 official_draw_time | UNKNOWN，不自行补写 |
| 2026105 预测报告 | `data/output/m4-p3-forward-prequential-confirmatory/2026105/pre-draw-report.md` 存在，625 bytes，mtime 09-09 10:19:02 | 仅确认存在；未把 mtime 充当封存证明 |
| 已存恢复结果 | fresh-cycle 记录 2026105 SEALED_BEFORE_DRAW、3 个阶段 REPLAY_VERIFIED | 历史操作输出，本轮未执行 verifier，不能称本轮 replay 通过 |
| 2026103 投递 | ledger 含 pre/post sent；ledger SHA-256 `28e1909dc1ee2b0bb2ea5f9e7fed07a3bc5a00f0f002efe4ce6e7255879bd69f`，mtime 09-09 10:14:16 | 账本事实已读，未核验收件人收到；不能据旧期宣称下一期完成 |
| 2026104 缺口 | 当前 ledger 没有该期；尚未与 canonical calendar/原始封存事实核对 | UNVERIFIED_GAP，不能补造预测或收益 |
| 最近 pre-mail 失败 | journal：`P3Top100NotificationError: notification_predraw_window_closed`；unit Result=exit-code | 原有失败保留；未修复、未补发 |
| 下一任务消费者 | 存储恢复输出称推进 2026105；正式显示路径却为观察身份 | 状态可信度缺口，不能据显示结果判断主线完成 |
| 定时 | successor / P4 / pre / post timer enabled active；观察 disabled；V11 masked | 本轮未改动 |
| 原始证据 | 未写任何生产文件/数据库/服务或邮件；工作树无 diff | 保持原样 |

本次材料的报告影响判定：`NO_RUNTIME_IMPACT`，仅限本次只读审计和仓库外 Markdown 材料。具体依据：无仓库 diff、未进入 521 文件 source 闭包、未调用任何执行/投递/迁移入口、数据库只读事务、systemd 仅 list/show/journal。不得将这个判定用于未来 R1–R5 代码变更，或解释成现有报告链健康。

## 4. 约 10 个可审查 PR 的有限拆分

| PR / 阶段 | 唯一主要目标 | 退出证据 |
| --- | --- | --- |
| 1 / R0 | 基线、ADR、入口清单、集中授权与规则修订 | 范围已批准；每个已发现入口有归属；未知项明确 |
| 2 / R1 | 显式路径与资源权限 | A1：双通道所有状态分支与真实权限拒绝，正式 sentinel 内容/mtime 不变 |
| 3 / R1 | 可信主体与批准绑定 | A2：同主体换标签不能自批；执行时核对撤销、内容、release、身份分离 |
| 4 / R2 | 最小执行存储、claim、fencing、不可变发布 | A3/A5：真实 PostgreSQL + FK + 文件，提交前后崩溃、并发唯一成功 |
| 5 / R2 | 版本化 verifier、恢复与统一消费 | A4：commit/readback/replay/下游共用规则；新进程 resume 不重训、不重复发布 |
| 6 / R3 | 独立 release、环境与 source 身份 | A8/A11：研发改动不影响服务，历史版本验证，隔离发布/回退演练 |
| 7 / R3 | API/状态消费者归属 | A9：路径缺失、过期、身份不符明确失败或未知 |
| 8 / R4 | 观察完整路径迁移 | A6/A12：合法输入→决策记录→100 注诊断→样本/报告→replay，科学语义等价 |
| 9 / R4 | 既有学习路径及确定性扩展验收 | A6/A10：固定快照→训练/评估/checkpoint/差异/replay；新增测试能力不改核心 |
| 10 / R5 | 发布/回退包、授权切换和单写入者 | 真实审查+Operator+部署事实；明确 P3 仍固定旧 release |

这是拆分估计，不以 PR 数作为验收。可在 8–12 范围内按依赖合并或拆分，不扩大目标。

A7 仅在触及投递机制时执行：假传输接收后中断，持久化 uncertain，重启不盲目重发。默认保留旧正式邮件机制，R0 和 R3 必须以依赖检查证明未触及它，不能无条件省略。

本轮各项训练路径声明：

| 合同项 | 路径 A 观察 | 路径 B 既有有限学习 |
| --- | --- | --- |
| Goal | 独立完成合法已开放预测诊断 | 独立复用既有冻结学习计算 |
| Ready | 目标期预测/结算合法开放、输入完整、scope 有效 | 固定快照、合同、release 与独立资源已验证 |
| Runner | 新入口组装旧 resolver/ready queue 与最小执行核心 | 同一个执行核心，注册学习 capability |
| 上游 | 不可变预测、checkpoint、合法开奖标签 | 冻结数据快照、配置、seed、原计算版本 |
| 下游 artifact | 决策记录、100 注诊断、完整样本、报告 | checkpoint、模型/评估、差异/基线报告 |
| 状态 | 各自 namespace 的可重建投影 | 各自 namespace 的可重建投影 |
| Evidence rule | 原合法开放与 point-in-time 规则，历史不冒充当期预测 | 原探索性证据口径，原阈值/基线不变 |
| decision consumer | 版本化 verifier、报告读取端 | 版本化 verifier、比较报告读取端 |
| next consumer | 样本/报告→replay；无邮件强依赖 | 评估/报告→replay；无 Promotion |

主线集成矩阵：R0 没有新增可执行能力。R1–R4 未实现，Goal/Resolver/Ready/Supervisor/Artifacts/Status/Next Task 均未获得新路径执行证据。整体答案 **NO — INTEGRATION_PENDING**。该事实不撤销已完成只读审计，也不改变历史学习实验结论。

## 5. 集中规则修订草案（未应用）

建议由真实授权方一次确认以下规范差异，再在 PR1 修改 AGENTS.md 与 training-mainline-integration-governance.md。现阶段仍按已有约束执行。

1. **完成口径按控制域分开。** 保留 Goal→Resolver→Ready Queue→Supervisor→Capability→Artifacts→Status→Next Task 和 deterministic replay 要求；明确可在受批准的独立观察/实验 control plane 验收。分别记录 CODE/OFFLINE、RELEASE_READY、DEPLOYED、BUSINESS_CYCLE、SCIENTIFIC_RESULT。离线完成不冒充生产部署，也不被不相关生产投递阻塞。
2. **报告 gate 按真实依赖。** 新增文字：经 diff、资源权限与 source 依赖审计证明隔离的研发，可独立结束其工程阶段；旧报告缺口继续保留为受影响生产路径的门槛。涉及生产报告路径的变化仍须精确期号、封存、内容、来源、replay、下游、ledger、timer 证据；未来投递仍 PENDING_DELIVERY。
3. **刷新进程限于受影响服务。** 替换无条件“训练变更后重启 supervisor”为：独立实验启动其新 release 的新执行进程并记录 run ID；只有变更涉及正式在役服务且存在有效 Operator 授权时才重启正式服务。P3 保留旧 release 不因独立研发而重启。
4. **连续工程授权。** 在已批准冻结 scope 内，代码、必要测试、普通 bug 修复、文档和 PR 迭代使用同一持续有效授权；不为每个测试失败新增 Request。每次执行检查是否撤销/越界；范围扩展、真实身份不明、生产动作仍使用对应合法路径。
5. **用户同意与 Reviewer 分开。** 用户会话的范围确认可作为真实用户同意证据，不可重标为 Reviewer Decision。身份 label 仅用于展示；审批必须由独立可信主体绑定内容及发布对象。当前接口尚未提供证明，不得因填入不同字符串就称已满足。
6. **V11 与旧 P3 兼容。** V11 保留不可调度归档；不得创建恢复 Request。P3 本轮可以固定旧 release，不宣称本体迁移完成；新路径只读合法开放 artifact。未开放累计指标、旧 V11 日报和无关 P4–P6 不自动成为新实验依赖。

不修改科学冻结合同、历史 digest、Evidence、null/failure 条件、开奖前后输入边界或 Promotion Gate。

## 6. 待授权的工程合同草案

建议类型：`engineering_implementation`；建议键：`engineering-control-layer-refactor-r0-r5-20260909`。此键仅为提案，尚未创建或批准。风险：high；具体生产切换另行绑定 release 的 Operator Request。

**scope：** 依据本文件与用户 roadmap，在独立开发工作区完成 R0–R5 的代码/离线工程部分及发布准备。包括运行上下文、路径归属与权限模板、可信主体校验、版本化执行/存储/恢复接口、增量 schema、固定 release/依赖身份、观察与既有学习能力接入、受影响 API 状态读取、真实 PostgreSQL CI、文档/回退包与可审查 PR。允许修改这些依赖所需文件，不固定五文件限制；不对无关算法/前端做重写。第 5 节规则差异须由真实授权方确认后落实。

**acceptance：** 按第 4 节与附件 A1–A12 验收。测试库必须真实、完整外键、与迁移一致；提交确认丢失及新进程 resume 不重训/重复注册/覆盖 artifact；并发单业务成功；同版本 verifier 覆盖提交/读取/replay/消费；路径错选被真实权限拒绝；同认证主体无法换 label 自批；两条路径科学等价且无生产凭据/邮件/P3 重启依赖；确定性新能力无需修改核心；原证据能由原 release 验证。准备准确发布/回退材料，真实 Operator 切换后才记录 DEPLOYED。

**non_goals：** V11 恢复/重放/激活；原失败/审批记录改写；历史 digest 重签；新模型族、调参、无限搜索、R6 科学实验；读取未开放结果；生产数据库/账号/系统服务/邮件/Promotion 直接操作；执行者自批；把工程结论改写为预测有效。

**权限与环境：** 代码及普通相关测试为 development；真实持久化/权限验收需要专门提供的隔离环境与账号，不得拿生产超级用户降格命名后使用。必要的隔离基础设施操作须有对应合法操作授权；production 只允许只读核查和生成审查材料。执行者身份必须是本会话实际 Engineering 主体，不能采用用户姓名或 Reviewer 标签。

## 7. 剩余检查与恢复顺序

1. 提供有效范围授权与真实确认第 5 节；本会话不代批。
2. 只读补齐独立 calendar/2026104 缺口、正式输入来源与可验证 artifact 索引；未开放信息不读。对生产相关未知项只阻断相关切换。
3. 补齐 API 实际进程/端口/响应以及系统级、容器、手工入口清单；当前 systemd user 清单不是所有执行者的证明。
4. 独立工作区建立 PR1；核对主目录仍作为在役代码路径，不在其上开发。
5. 在授权隔离环境获取非超级用户实验/观察账号及真实可信 Reviewer/Operator 入口；缺失项保持不可用，不造安全完成。
6. 开始 PR2，仅修复 R1 对应边界；每个阶段在本检查点追加证据摘要与唯一下一动作。

## 8. 本次命令限制与失败记录

- 初次 sandbox `systemctl --user`：Operation not permitted；经只读工具权限审查后成功取得 live 状态，未操作服务。
- `git ls-remote origin`：`Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf`；未修改系统配置，改用已认证 GitHub 只读 API 得到 main SHA。
- 最初猜测 workflow/API 文件路径不存在；已定位实际 `.github/workflows/worker-python-tests.yml` 和 `apps/api/src/research.service.ts`。不是产品测试失败。
- 未运行会调用 ensure_schema、dispatch、replay 写入或发送邮件的所谓 status 命令。未跑测试，因为代码未改且当前没有本范围有效执行授权。
- 当前 GitHub main CI success 已确认，不假设历史 quota 仍阻断；将来每个 PR 以当时 runner/check 事实判断。

本轮结束时总 Goal 保持未完成。R0 材料交付不能标为 R0–R5 重构完成。

## 9. 第二次 Goal 续接：补充现场证据

上一轮分类为 progress：完成初始现场核查并保存审查材料。本轮重新检查工作树仍干净、HEAD 仍 ac0ef78；数据库 `id > 815` 无新 Request，建议重构 key 无记录。缺少本范围有效工程授权的条件连续出现第 2 次，尚未将 Goal 标为 blocked。

本轮补齐的 R0 事实：

- 系统级 `systemctl list-units 'dehps*' --all` 为 0；user systemd 之外，没有在该命名范围发现加载的系统级 DEHPS 服务。此检查不涵盖其它命名服务。
- 当前 Docker DEHPS 容器是 `ark-dehps-postgres`（postgres:17，54329→5432）和 `ark-dehps-redis`（redis:7，63799→6379）；本轮保留数据库/Redis，不迁移它们的数据。未修改容器，也不调查同时列出的其它项目容器。
- 主机监听清单无 3000；`curl --noproxy '*' --max-time 5 http://127.0.0.1:3000/health` 返回 exit 7 / Could not connect to server。源码默认 API_PORT=3000。因此默认本机 API 当前不可用，不能填写 live HTTP 成功基线；不据此断言所有远端或自定义端口 API 都不存在。
- /proc 只读检查确认 PID 7736 仍为旧 release supervisor，PID 2251743 仍为性能 watchdog。另见 4 个 lifecycle MCP Python 服务，都从原工作区启动；这进一步说明 R1 身份/数据库边界需要覆盖全部生命周期入口，不能仅靠单一客户端 label。
- 同目录下 Codex Node 工具进程不属于 DEHPS 业务 API，不计为正式业务入口。本轮未启动任何服务。

报告期号与日历补证：

- `ssq_history` 只选日期和来源元数据：2026102=2026-09-03，2026103=2026-09-06，2026104=2026-09-08，来源均 zhcw。2026104 创建时间为 09-08 21:57:52.328886+08:00。
- 2026104 同步事件 `draw-issue-2026104-d6115b435c0f941c536c` 存在，audit hash `00552552c0efa875762c52e444b93a0ce15c8734d5762427753f0ddc3cb83930`；事件状态 pending。pending 只代表该事件消费者状态，不能解释成开奖记录未入库或重训许可。
- canonical `forward_prequential_confirmatory.target_for_now` 委托 `bounded_operational_forward.target_for_now`；代码将最近开奖之后的下一开奖日作为目标，封存 deadline 固定 17:00，official_draw_time 固定 21:15，均为 Asia/Shanghai。现有 2026104 日期与这条规则、已存 2026105 记录及 Thu 09-10 17:00 timer 一致。这是项目内部调度合同确认，不是对外部官方日历的独立背书。
- 2026104 已开奖且当前邮件账本缺少该期，故不再仅视为未知期号；应明确记录“已到期的投递账本缺口”。尚未完成数据库注册预测/封存审计，不能断言有合法预测可供补发，更不得生成事后预测。
- 以上没有读取号码、未开放累计结果或 execution result 载荷，未运行 target_for_now 或任何恢复/同步入口。

更新后的直接下一动作仍是取得第 5、6 节对应的真实工程授权。当前没有可供本会话等待的重构 job/进程 handle；已有生产进程运行不代表本次重构在执行。报告影响仍为 NO_RUNTIME_IMPACT，仅适用于只读检查与本材料更新；R1–R5 仍未实施。

## 10. 第三次 Goal 核查：授权阻塞

上一轮为 progress（新增容器、API、日期及审计事件证据）；本轮为 no progress，仅重验阻塞。工作树干净，HEAD 仍 ac0ef78。只读查询新增 Request、拟定重构 key 和工程重构标题，返回 `rows: []`。

`no_authorized_agent_request` 已连续出现三轮。可审查范围、规则差异、入口迁移和验收材料已准备；不能靠进一步重复只读检查取得实施权限。当前无本重构的执行进程可等待，也不能代签、自批或将旧 Request 扩大解释为授权。Goal 标记 BLOCKED，完整 R0–R5 目标保留，未标为完成。

解除条件：真实授权方确认第 5、6 节并通过合法入口提供覆盖本范围的 approved engineering Request；执行前重新核验批准有效、scope 与身份。生产切换仍另需具体 release 的合法审查和 Operator 授权。解除后从本检查点继续，不重做全量历史盘点。
