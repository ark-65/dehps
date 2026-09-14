"""Readable reconstruction and original evidence are explicitly separated."""
import json


def render(value):
    score = value['score']
    lines = [f"# 第 {value['issue']} 期历史报告学习", '',
        'HISTORICAL_RECONSTRUCTION · RESEARCH_ONLY · 证据不足',
        '这是历史回顾重建。没有声称本次概率或选票在开奖前封存。',
        '原始报告文字只供审计，未作为训练标签或调参指令。', '',
        f"训练截止期：{value['training_cutoff']}；训练样本 {value['before']['count']} → {value['after']['count']}。",
        f"输入摘要：{value['input_sha256']}",
        f"更新前 checkpoint：{value['before_sha256']}", f"更新后 checkpoint：{value['after_sha256']}",
        f"开奖：红 {score['label']['red']}；蓝 {score['label']['blue']}。",
        f"来源审计：{score['label']['audit_sha256']}；标签可用时间：{score['label']['available_at']}。", '',
        '## 原始报告证据', f"原始预测状态：{value['original_prediction_status']}。",
        '原始候选和排名保存在下列内容寻址机器产物中；不会用本次重建选票替换。']
    for ref in value['original_references']:
        lines.append(f"- {ref['kind']}；模型 {ref['model']}；来源 {ref['source']}；摘要 {ref['sha256']}")
    if value['original_prediction_status'] == 'REPORT_GAP':
        lines.append('没有核实到本期原始开奖前预测。该缺口继续保留；合法开奖标签仍可用于历史更新。')
    lines += ['', '## 本次历史重建结果', '| 模型 | log-loss | Brier |', '| --- | ---: | ---: |']
    for model, metrics in score['probability'].items():
        lines.append(f"| {model} | {metrics['log_loss']:.10f} | {metrics['brier']:.10f} |")
        lines += ['', f'### {model} 全部 33 个红球标签与误差',
            '| 号码 | 概率 | 标签 | 残差 | log-loss |', '| --- | ---: | ---: | ---: | ---: |']
        lines += [f"| {n['number']} | {n['probability']:.8f} | {n['label']} | {n['residual']:+.8f} | {n['log_loss']:.8f} |"
                  for n in metrics['numbers']]
    for model, diagnostic in score['diagnostics'].items():
        lines += ['', f'### {model} 完整遗漏诊断', f"首次遗漏阶段：{diagnostic['first_loss_stage']}。",
            f"真实候选池排名：{diagnostic['actual_pool_rank']}；假想插入排名：{diagnostic['hypothetical_insertion_rank']}。",
            f"号码暴露：{diagnostic['number_exposures']}；命中分布：{diagnostic['hit_histogram']}。",
            '同一期各模型共享固定 10000 注候选池，按各自原规则排序；无额外筛选。',
            '遗漏描述选票过程，不解释开奖机制；全部假想替换分数差保存在注册机器产物中。']
        lines += [f"- #{t['rank']:03d} 红 {t['red']}；蓝 {t['blue']}；遗漏 {t['missing']}；多选 {t['extra']}；"
                  f"红中 {t['red_hits']}；蓝中 {t['blue_hit']}。" for t in diagnostic['all_100_tickets']]
    lines += ['', '## 实际学习动作', '先用此前数据生成概率，再评分，最后吸收全部标签。固定 shrink900；蓝球只记录，不训练。',
        f"红球标签（33）：{score['red_labels']}", f"蓝球标签（16）：{score['blue_labels']}",
        '工程运行成功不能证明预测改善；旧模型与均匀概率基线保留。没有发送邮件。',
        '独立观察消费与新进程回放以各自登记记录为准。']
    return '\n'.join(lines)+'\n'


def report(value, learn_sha256):
    return {'issue': value['issue'], 'input_sha256': value['input_sha256'], 'learn_sha256': learn_sha256,
        'checkpoint_sha256': value['after_sha256'], 'original_prediction_status': value['original_prediction_status'],
        'metrics': {m: {k: v[k] for k in ('log_loss', 'brier')} for m, v in value['score']['probability'].items()},
        'text': render(value), 'external_delivery': False}


def summary_text(value):
    return '# 历史学习批次汇总\n\nHISTORICAL_RECONSTRUCTION · 证据不足\n\n'+json.dumps(value, ensure_ascii=False, indent=2)+'\n'
