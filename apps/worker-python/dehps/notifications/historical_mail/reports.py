"""Human-readable notifications from sealed candidates, never fresh post-draw ranks."""
import html
from collections import Counter
from .contract import require

NOTICE = '实验性推测 · 证据不足。历史评分未优于均匀基线，不代表已证实预测能力。蓝球采用固定分配规则，未训练。'


def report(seal, label=None):
    issue = seal['issue']; pre = label is None
    subject = f'[DEHPS 遗漏学习·实验] 第 {issue} 期 ' + ('Top100 推测' if pre else '开奖结果与命中复盘')
    lines = [subject, '', NOTICE, '', f"模型：shrink900；状态：{seal['status']}。"]
    if seal['status'] == 'SEALED_BEFORE_DRAW':
        lines += [f"训练截止：{seal['training_end_issue']}；累计标签：{seal['count']} 期。",
                  f"封存时间：{seal['sealed_at']}；开奖时间：{seal['draw_at']}。",
                  f"检查点摘要：{seal['checkpoint_sha256']}。"]
    else:
        lines += ['本期缺少开奖前封存推测，保留缺口；不补造候选、不计算假想命中。']
    hits = []
    if label is not None:
        require(label['issue'] == issue, 'result must match sealed issue')
        lines += ['', '真实开奖结果：红球 '+ ' '.join(f'{n:02d}' for n in label['red'])+f" / 蓝球 {label['blue']:02d}",
                  f"来源审计摘要：{label['audit_sha256']}。"]
    if seal['status'] == 'SEALED_BEFORE_DRAW':
        if label:
            for ticket in seal['tickets']:
                hits.append({'rank': ticket['rank'], 'red_hits': len(set(ticket['red']) & set(label['red'])),
                             'blue_hit': ticket['blue'] == label['blue']})
            hist = Counter(row['red_hits'] for row in hits)
            lines += ['红球命中分布：'+ '；'.join(f'{n} 中：{hist[n]} 注' for n in range(7)),
                      f"蓝球命中：{sum(row['blue_hit'] for row in hits)} 注。只核对命中，不计算收益。"]
        lines += ['', '| 排名 | 红球 | 蓝球 |'+(' 红球命中 | 蓝球命中 |' if label else ''),
                  '| ---: | --- | ---: |'+(' ---: | --- |' if label else '')]
        for index, ticket in enumerate(seal['tickets']):
            line = f"| {ticket['rank']} | "+' '.join(f'{n:02d}' for n in ticket['red'])+f" | {ticket['blue']:02d} |"
            if label:
                line += f" {hits[index]['red_hits']} | "+('是' if hits[index]['blue_hit'] else '否')+' |'
            lines.append(line)
    text = '\n'.join(lines)+'\n'
    return {'subject': subject, 'text': text, 'html': '<pre>'+html.escape(text)+'</pre>', 'hits': hits}
