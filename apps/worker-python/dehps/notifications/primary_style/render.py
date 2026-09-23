"""Render immutable primary facts with the omission report's visual language."""
from decimal import Decimal
from html import escape

NAMES = {0: '未中奖', 1: '一等奖', 2: '二等奖', 3: '三等奖', 4: '四等奖', 5: '五等奖', 6: '六等奖'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def render(source):
    email = source['email']; body = source['report']['body']
    tickets = source['tickets']; kind = email['kind']; issue = email['issue']
    require(kind in ('pre', 'post') and issue.isdigit() and body['issue'] == issue, 'presentation identity differs')
    require(len(tickets) == 100 and [t['rank'] for t in tickets] == list(range(1, 101)), '100 ranked tickets required')
    require(len({(tuple(t['red_numbers']), t['blue_number']) for t in tickets}) == 100, 'duplicate tickets')
    require(email['text'] == body['text'] and email['subject'] == body['subject'], 'original wording differs')
    checkpoint = source['checkpoint']['body']
    require(checkpoint['status'] == 'SEALED_BEFORE_DRAW' and checkpoint['target_issue'] == issue, 'sealed issue differs')
    post = kind == 'post'; actual = source.get('draw') if post else None
    winners = {t['rank']: t for t in body['winners']} if post else {}
    if post:
        require(len(winners) == body['winner_count'] and body['winner_count'] + body['losing_count'] == 100, 'winner count differs')
        require(sum(Decimal(t['gross_prize_cny']) for t in winners.values()) == Decimal(body['accounting']['gross_prize_cny']), 'registered prize sum differs')
        require(sum(body['tier_counts'].values()) == len(winners), 'prize distribution differs')
    for ticket in tickets:
        red = ticket['red_numbers']; blue = ticket['blue_number']
        require(len(red) == 6 and red == sorted(set(red)) and all(type(n) is int and 1 <= n <= 33 for n in red)
                and type(blue) is int and 1 <= blue <= 16, 'illegal ticket')
        if ticket['rank'] in winners:
            winner = winners[ticket['rank']]
            require(all(winner[k] == ticket[k] for k in ('rank', 'red_numbers', 'blue_number')), 'winner ticket differs')
            require(winner['red_hits'] == len(set(red) & set(actual['red'])) and winner['blue_hit'] == (blue == actual['blue']), 'winner hits differ')

    def balls(red, blue):
        return ' '.join(f'<span style="display:inline-block;background:#c62828;color:white;border-radius:50%;padding:9px;font-weight:bold">{n:02d}</span>' for n in red) + f'　<span style="display:inline-block;background:#1565c0;color:white;border-radius:50%;padding:9px;font-weight:bold">{blue:02d}</span>'

    def table(rows):
        titles = ['排名', '预测红球', '蓝球'] + (['命中红球', '蓝球命中', '奖级', '税前奖金'] if post else ['单注金额'])
        result = '<table style="border-collapse:collapse;width:100%;font-size:14px"><thead><tr>'
        result += ''.join(f'<th style="padding:8px;border-bottom:2px solid #ccc;text-align:left">{s}</th>' for s in titles) + '</tr></thead><tbody>'
        for row in rows:
            hit = set(row['red_numbers']) & set(actual['red']) if post else set()
            numbers = ' '.join(f'<b style="color:#c62828">{n:02d}</b>' if n in hit else f'{n:02d}' for n in row['red_numbers'])
            cells = [str(row['rank']), numbers, f"{row['blue_number']:02d}"]
            if post:
                winner = winners.get(row['rank'])
                cells += [' '.join(f'{n:02d}' for n in sorted(hit)) or '—', '是' if row['blue_number'] == actual['blue'] else '否',
                          NAMES[winner['tier']] if winner else NAMES[0], '¥' + escape(winner['gross_prize_cny']) if winner else '¥0.00']
            else:
                cells += ['¥' + escape(body['unit_cost_cny'])]
            result += '<tr>' + ''.join(f'<td style="padding:7px;border-bottom:1px solid #ddd">{c}</td>' for c in cells) + '</tr>'
        return result + '</tbody></table>'

    title = '主线 Top-100 开奖复盘' if post else '主线 Top-100 开奖前推测'
    out = f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(email["subject"])}</title></head><body><div style="font-family:Arial,sans-serif;max-width:1000px;margin:auto;color:#202124"><h2>第 {issue} 期 · {title}</h2>'
    if post:
        out += '<h3>开奖号码</h3><p>' + balls(actual['red'], actual['blue']) + '</p>'
        a = body['accounting']
        summary = f"模拟投入 ¥{a['hypothetical_cost_cny']} ｜ 税前奖金 ¥{a['gross_prize_cny']} ｜ 税后净收益 ¥{a['net_profit_cny']} ｜ 收益率 {a['roi_percent']}%"
        out += f'<div style="background:#f3f6fa;border-left:5px solid #245a85;padding:16px;font-size:18px;font-weight:bold">{escape(summary)}</div>'
        out += f'<p>预计应纳税额：¥{escape(a["estimated_tax_cny"])}　｜　预计税后到账：¥{escape(a["after_tax_receipt_cny"])}</p>'
        out += '<p>100注 × 2元；税后净收益＝预计税后到账－模拟投入；收益率＝税后净收益÷模拟投入。<br>金额沿用主线已登记的模拟核算，不代表实际购买或收入。</p>'
        out += '<p>' + '；'.join(f'{NAMES[n]} {body["tier_counts"][str(n)]}注' for n in range(1, 7)) + f'；未中奖 {body["losing_count"]}注</p>'
        out += '<h3>中奖明细</h3>' + (table([t for t in tickets if t['rank'] in winners]) if winners else '<p>本期无中奖注。</p>')
    else:
        out += f'<div style="background:#f3f6fa;border-left:5px solid #245a85;padding:16px;font-size:18px;font-weight:bold">模拟投入 ¥{escape(body["hypothetical_total_cost_cny"])} ｜ 100注 × ¥{escape(body["unit_cost_cny"])} ｜ 开奖与收益：待开奖</div>'
        out += '<p>排名沿用开奖前封存候选，不代表已证明的中奖概率优势。</p><h3>排名第 1 的封存候选</h3><p>' + balls(tickets[0]['red_numbers'], tickets[0]['blue_number']) + '</p>'
    out += '<h3>全部100注明细' + ('（红色为命中号码）' if post else '（原封存排名）') + '</h3>' + table(tickets)
    out += '<p>实验性影子输出；证据不足，未证明概率优势，不保证中奖。仅为模拟展示。</p>'
    # Keep the registered tax policy and evidence wording visible; the plain-text
    # MIME alternative remains byte-for-byte identical to the canonical report.
    policy = [s for s in email['text'].splitlines() if s.startswith(('税务口径：', '说明：'))]
    out += ''.join('<p>' + escape(s) + '</p>' for s in policy)
    provenance = f"封存时间：{checkpoint['sealed_at']}\n开奖时间：{checkpoint['official_draw_time']}\n原报告摘要：{email['artifact_digest']}\n原报告回放：{email['replay_digest']}\n候选摘要：{source['candidate_digest']}"
    out += '<h3>封存和来源</h3><p style="font-size:12px;overflow-wrap:anywhere;white-space:pre-wrap">' + escape(provenance) + '</p></div></body></html>'
    return out
