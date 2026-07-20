# DEHPS 可视化监控入口

## 治理边界

当前页面仍是历史形成的混合视图。目标信息架构已经在
[Runtime And Research Dashboard Governance](architecture/dashboard-governance.md) 冻结，后续将以
单独 Engineering Request 拆为：

- Runtime Dashboard：Contracts、ABI、backend equality、Golden、测试证据、性能、Telemetry、
  operational freshness。
- Research Dashboard：Recent-30/100/300、walk-forward、rank、calibration、stability、ablation、
  future generalization。
- Cross-lane Process strip：evaluation completion、shadow coverage、experiment/promotion decisions。

三个命名空间不计算综合分。M1 capability 不代表现场永远绿色；缺失或陈旧证据必须显示
`missing`/`stale`。当前 Expected Value 在经济合同建立前显示 `not_defined`。

## 页面入口

- 局域网仪表盘：http://192.168.99.248:4200/
- 本机仪表盘：http://localhost:4200/
- 训练状态 API：http://192.168.99.248:3000/training-status
- 训练实时 WebSocket：ws://192.168.99.248:3000/training-status/ws
- 聚合数据 API：http://192.168.99.248:3000/dashboard

## 当前展示内容

- 24 小时训练监督器运行状态、PID、进程存活状态。
- 训练状态 WebSocket 实时推送；页面保留 30 秒 HTTP 刷新作为兜底。
- 当前轮 target 进度、最近训练轮次、最佳 Top10000/Top1000/Top100 命中。
- ECharts 图表：命中趋势、排名分布、奖惩机制、权重演化、候选分布。
- 当前最佳权重配置、配置哈希、运行键。
- 训练日志尾部、状态文件、报告文件、日志文件路径。
- 并行实验 tab：历史实验、实验报告、实验对比、组合空间分布、红球全组合特征分布。
- 开奖同步计划：官方 21:15 开奖后预留 30 分钟，固定在北京时间每周二、周四、周日 21:45 自动同步；以数据源实际更新为准，未更新时由轮询与恢复链路继续补偿。
- 少于 100 期历史样本的早期烟测实验会被隐藏，避免和当前 100 期 walk-forward 训练结果混淆。

## 本机服务

```bash
systemctl --user status dehps-api-dashboard.service
systemctl --user status dehps-web-dashboard.service
systemctl --user status dehps-training-supervisor-20260616-145808.service
```

API 服务使用 `npm run start:dev`，源码变化会由 `tsx watch` 热重启；Web 服务使用 `ng serve`，模板和样式变化会热更新到浏览器。

## 奖惩机制

当前训练监控采用透明奖惩分：

```text
命中奖励 = Top100 命中数 * 1000 + Top1000 命中数 * 100 + Top10000 命中数 * 10
排名惩罚 = 中位排名 / 全组合数 + 最差排名 / 全组合数 / 4
综合分 = 命中奖励 - 排名惩罚
```

训练器硬优先比较 Top100、Top1000、Top10000 命中数；额外 Top10000 命中不能抵消 Top1000 命中的损失。当命中层级相同时，综合分用于选择排名分布更稳的权重。

训练器每轮会保留历史优秀配置组成精英池，并围绕精英配置做微扰、混合和外推；目标是让 Top10000 命中从 3/100 开始逐步寻找 4/100、5/100，而不是只在单个基准权重附近反复试探。

训练器重启时会加载同一 `as_of_issue`、历史指纹、训练协议下的旧监督报告，把历史最佳配置带入新 run，避免新 run 局部最佳覆盖全局更优结果。

## 日志路径

- API 日志：`runtime/logs/api-dashboard.log`
- Web 日志：`runtime/logs/web-dashboard.log`
- 训练日志：`runtime/logs/training-supervisor-20260616-145808.log`
- 同步日志：`runtime/logs/ssq_draw_sync.log`
