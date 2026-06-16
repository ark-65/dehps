# DEHPS 可视化监控入口

## 页面入口

- 局域网仪表盘：http://192.168.99.248:4200/
- 本机仪表盘：http://localhost:4200/
- 训练状态 API：http://192.168.99.248:3000/training-status
- 聚合数据 API：http://192.168.99.248:3000/dashboard

## 当前展示内容

- 24 小时训练监督器运行状态、PID、进程存活状态。
- 当前轮 target 进度、最近训练轮次、最佳 Top10000/Top1000/Top100 命中。
- 当前最佳权重配置、配置哈希、运行键。
- 训练日志尾部、状态文件、报告文件、日志文件路径。
- 历史实验、实验报告、实验对比、组合空间分布、红球全组合特征分布。
- 开奖同步计划：北京时间每周二、周四、周日 23:59 自动同步。

## 本机服务

```bash
systemctl --user status dehps-api-dashboard.service
systemctl --user status dehps-web-dashboard.service
systemctl --user status dehps-training-supervisor-20260616-145808.service
```

## 日志路径

- API 日志：`runtime/logs/api-dashboard.log`
- Web 日志：`runtime/logs/web-dashboard.log`
- 训练日志：`runtime/logs/training-supervisor-20260616-145808.log`
- 同步日志：`runtime/logs/ssq_draw_sync.log`
