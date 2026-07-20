# ACCEPTANCE.md - 验收标准

每次变更都必须让项目更可验证，而不只是更复杂。验收以事实、命令、产物和可回滚边界为准。

## 通用验收

- 目标清楚: 本轮只解决一个明确问题。
- 非目标清楚: 明确哪些相关诱惑本轮不碰。
- 不破坏等概率前提: 报告语言区分当前训练证据、历史过滤表现和未来预测主张，不提前写成预测承诺。
- 可复现: 记录数据源、历史窗口、配置、随机种子或配置哈希。
- 可反证: 写出失败条件，例如 coverage 低于 baseline、lift 不超过 null、missed issues 呈系统性偏差、结果对窗口极不稳定。
- 可回滚: 变更范围小，提交只包含本轮相关文件，并推送到远端形成可恢复 checkpoint。

## 模型/策略/训练验收

- 必须有 baseline 或 same keep-rate null model。
- 必须报告 keep_rate, coverage_rate, lift, missed issues, config snapshot。
- 必须检查泄漏: 目标期结果、开奖后字段、导入排序、报告筛选、重复组合。
- 必须说明样本空间: 双色球红球合法组合为 `C(33,6)=1,107,568`。
- 任何“提升”都必须附带对照，不允许只展示最佳窗口。

## Roadmap 归属验收

- 每轮只声明一个 owner lane: Runtime、Research 或 Knowledge；跨线依赖可以记录，但不能合并
  目标函数。
- Runtime 验收只使用 determinism、ABI、backend equality、throughput、latency、memory、
  scalability、reproducibility、auditability 等平台指标。
- Research 验收区分 search selection、window stability、historical walk-forward 和 genuinely
  unseen forward generalization；同一观察不得重复充当选择和独立验证证据。
- Knowledge 验收检查定义、版本、权威来源、链接、假设、非目标和 supersession，不替代代码、
  实验或 Promotion Gate。
- Runtime 绿色不能抵消 Research 失败；Research lift 不能掩盖 Runtime stale/missing/failed。

## Dashboard 证据验收

- Runtime Dashboard 与 Research Dashboard 使用独立 payload、状态和 KPI，不生成综合健康分。
- M1 milestone 不得硬编码成永久绿色；状态必须绑定 commit、命令、时间、范围和 freshness。
- Shadow 数值相等/attestation validity 归 Runtime Health；evaluation completion 归 Research
  Process。
- Promotion Rate 只做描述性流程指标，不能作为模型选择目标。
- Expected Value 在经济合同缺失时必须显示 `not_defined`，不得从 hit rate 推算。

## 数据同步验收

- 数据来源显式，优先真实历史源。
- CSV 只能通过明确参数或环境变量启用。
- 冲突、缺失、重复、解析异常必须记录。
- 不允许静默使用样例数据填充真实历史缺口。

## API/Web 验收

- API 返回类型应在服务层归一化，避免前端依赖原始 JSONB 或数据库行形状。
- 状态页优先显示 live process evidence；历史快照只能作为补充。
- 长历史图表必须可读，不能让 700+ 轮数据挤成不可解释的噪声。
- UI 文案可以表达“预测训练/候选假设/预测信号”，也可以承载投注建议方向；未达训练目标时必须显示证据等级、风险说明和失败样本。

## 自动化/调度验收

- cron 或 systemd 任务必须有锁、日志和失败路径。
- 自我迭代任务必须先检查工作区是否干净，避免覆盖人类正在做的事。
- 调度结果必须可追踪到命令、时间、退出码和日志。

## 推荐验证命令

```bash
git status --short
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests
cd apps/api && npm test
cd apps/web && npm test
cd apps/web && npm run build
```

按变更范围选择最小充分命令；未运行的命令必须说明原因。

## 提交验收

- 每次代码修改完成后必须 `git commit` 并 `git push`。
- 提交前只暂存本轮相关文件。
- 若存在无关未提交改动，必须保留并说明，不得夹带。
- 若验证无法运行，提交信息或最终说明中必须写清剩余风险。
