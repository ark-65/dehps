"""A readable independent report, never a production mail dependency."""


def render(issue, score, next_seal, window_analysis=None):
    lines = [f'# 第 {issue} 期独立学习复盘', '', 'RESEARCH_ONLY；正式 P3 不变。', '',
             f"本期状态：{score['status']}", '可学习原因：证据不足。遗漏位置描述选票过程，不解释开奖机制。',
             ('全部 33 个红球正负标签均参与评分。' if score['status'] == 'SCORED'
              else '本期缺少合格封存预测，保留缺口；全部标签仅用于下一期更新。'),
             '蓝球仅记录，不训练。',
             f"开奖号码：红 {score['label']['red']}；蓝 {score['label']['blue']}。",
             f"标签可用时间：{score['label']['available_at']}；审计摘要：{score['label']['audit_sha256']}。", '',
             '| 模型 | 平均 log-loss | Brier |', '| --- | ---: | ---: |']
    for name, metrics in score['probability'].items():
        lines.append(f"| {name} | {metrics['log_loss']:.10f} | {metrics['brier']:.10f} |")
    for name, metrics in score['probability'].items():
        lines += ['', f'## {name} 的全部号码误差',
                  '| 号码 | 预测概率 | 标签 | 标签减概率 | log-loss |', '| --- | ---: | ---: | ---: | ---: |']
        lines += [f"| {n['number']} | {n['probability']:.8f} | {n['label']} | {n['residual']:+.8f} | {n['log_loss']:.8f} |"
                  for n in metrics['numbers']]
    for name, diagnostic in score['diagnostics'].items():
        lines += ['', f'## {name} 的完整遗漏过程',
                  f"首次遗漏阶段：{diagnostic['first_loss_stage']}；额外筛选：无。",
                  f"真实候选池排名：{diagnostic['actual_pool_rank']}；假想插入排名：{diagnostic['hypothetical_insertion_rank']}。",
                  f"各号码暴露次数：{diagnostic['number_exposures']}",
                  f"0–6 红球命中分布：{diagnostic['hit_histogram']}",
                  '以下为全部 100 注；完整假想替换分数差保存在机器结果，不用于下一期调参。']
        for ticket in diagnostic['all_100_tickets']:
            lines.append(f"- #{ticket['rank']:03d} 红 {ticket['red']}；漏选 {ticket['missing']}；"
                         f"多选 {ticket['extra']}；红中 {ticket['red_hits']}；蓝中 {ticket['blue_hit']}")
    lines += ['', '## 实际训练动作',
              '本期先评价此前封存概率，再将经审计标签计入下一期；固定 shrink900，无新特征或调参。',
              f"下一期 checkpoint：{next_seal or '固定窗口结束，不自动延长'}", '',
              '本期数值仅作描述；固定 60 个目标期次结束后才统一分析。',
              '漏封存期不补造，不因成绩换期；概率改进不等于收益改进。',
              '奖金信息不作为概率学习的前提；本报告没有发送邮件。']
    if window_analysis is not None:
        import json
        lines += ['', '## 固定窗口最终分析', window_analysis['conclusion'],
                  '主指标及冻结配对检验如下；辅助指标不改变结论，无正式推广资格。',
                  '```json', json.dumps(window_analysis, ensure_ascii=False, sort_keys=True, indent=2), '```']
    return '\n'.join(lines) + '\n'
