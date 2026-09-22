"""Exact base-prize accounting; no new candidates, training or tax assumptions."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import html
from dehps.notifications.p3_top100 import prize_tier, validate_notification_artifact
from dehps.notifications.historical_mail.reports import NOTICE
from dehps.notifications.historical_mail.contract import require

RULES_URL = 'https://www.lottost.cn/c/2026-01-29/486279.shtml'
NAMES = {0:'未中奖',1:'一等奖',2:'二等奖',3:'三等奖',4:'四等奖',5:'五等奖',6:'六等奖'}
SCOPE = '常规六奖级；不含未登记的派奖或福运奖，不估算税费。'


def money(value):
    try:
        result = Decimal(str(value))
        require(result.is_finite() and result >= 0 and result == result.quantize(Decimal('.01')), 'invalid prize amount')
        return result
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid prize amount') from exc


def settle(seal, label, payout):
    require(seal['issue'] == label['issue'], 'settlement issue differs')
    red = label['red']; blue = label['blue']
    require(len(red)==6 and red==sorted(set(red)) and all(type(n) is int and 1<=n<=33 for n in red)
            and type(blue) is int and 1<=blue<=16, 'invalid winning numbers')
    artifact = validate_notification_artifact(payout); p = artifact['body']
    require(artifact['artifact_type']=='P3Top100IssuePayoutSourceV1' and p['status']=='EXACT_ISSUE_PAYOUT_VALIDATED'
            and p['issue']==label['issue'] and p['actual_red_numbers']==red and p['actual_blue_number']==blue,
            'payout does not match audited draw')
    require(len(p['tiers'])==6 and {r['tier'] for r in p['tiers']}==set(range(1,7)), 'unsupported or incomplete prize schedule')
    amounts={r['tier']:money(r['single_ticket_gross_cny']) for r in p['tiers']}
    require(all(amounts[k]==Decimal(v) for k,v in {3:3000,4:200,5:10,6:5}.items()), 'fixed prize differs')
    if seal['status']=='MISSING_PREDRAW_SEAL':
        require(not seal['tickets'], 'gap cannot contain retrospective tickets')
        return {'status':'NO_SIMULATION_PREDRAW_GAP','tickets':[], 'cost_cny':None,'gross_cny':None,'net_cny':None,'roi_percent':None}
    require(seal['status']=='SEALED_BEFORE_DRAW' and len(seal['tickets'])==100, '100 genuinely sealed tickets required')
    rows=[];seen=set()
    for index,t in enumerate(seal['tickets'],1):
        numbers=t['red'];b=t['blue']
        require(t['rank']==index and numbers==sorted(set(numbers)) and len(numbers)==6
                and all(type(n) is int and 1<=n<=33 for n in numbers) and type(b) is int and 1<=b<=16,
                'invalid sealed ticket')
        identity=(tuple(numbers),b);require(identity not in seen,'duplicate ticket');seen.add(identity)
        hit=sorted(set(numbers)&set(red));blue_hit=b==blue;tier=prize_tier(red_hits=len(hit),blue_hit=blue_hit)
        amount=amounts[tier] if tier else Decimal(0)
        require(not tier or amount>0, 'winning tier official payout missing')
        rows.append({**t,'hit_numbers':hit,'red_hits':len(hit),'blue_hit':blue_hit,'tier':tier,'gross_cny':f'{amount:.2f}'})
    cost=Decimal(len(rows))*2;gross=sum((Decimal(r['gross_cny']) for r in rows),Decimal(0));net=gross-cost
    counts=Counter(r['tier'] for r in rows)
    return {'status':'SIMULATED_PRETAX_BASE_PRIZES','tickets':rows,'winning_tickets':sum(r['tier']>0 for r in rows),
            'tier_counts':{str(k):counts[k] for k in range(7)},'unit_cost_cny':'2.00','multiplier':1,
            'cost_cny':f'{cost:.2f}','gross_cny':f'{gross:.2f}','net_cny':f'{net:.2f}',
            'roi_percent':f'{net/cost*100:.2f}','payout_digest':artifact['artifact_digest'],'scope':SCOPE}


def report(source):
    value=source['original']['artifact']['value'];seal=value['seal'];label=value['label'];payout=source['payout']['artifact']
    result=settle(seal,label,payout);issue=label['issue']
    subject=f'[DEHPS 遗漏学习·实验] 第 {issue} 期 开奖复盘与模拟收益'
    balls=' '.join(f'{n:02d}' for n in label['red']);blue=f"{label['blue']:02d}"
    lines=[subject,'',f'开奖号码：红球 {balls} ｜ 蓝球 {blue}','']
    if result['cost_cny'] is None:
        summary='本期缺少开奖前封存推测，不计算模拟投入、奖金或收益。';lines.append(summary)
    else:
        summary=f"模拟投入 ¥{result['cost_cny']} ｜ 税前奖金 ¥{result['gross_cny']} ｜ 净收益 ¥{result['net_cny']} ｜ 收益率 {result['roi_percent']}%"
        lines += [summary, f"口径：100注 × 每注¥2.00 × 1倍；中奖{result['winning_tickets']}注，未中奖{result['tier_counts']['0']}注。",
                  '净收益＝税前奖金－模拟投入；收益率＝净收益÷模拟投入。',SCOPE,
                  '仅为封存候选的模拟核算，没有实际购买或实际收入。','',
                  '奖级分布：'+'；'.join(f"{NAMES[k]} {result['tier_counts'][str(k)]}注" for k in range(1,7))]
    lines += ['',NOTICE,'',f"模型：shrink900；封存状态：{seal['status']}；封存时间：{seal['sealed_at']}。",
              f"训练截止：{seal.get('training_end_issue','无')}；开奖时间：{seal['draw_at']}。",
              f"原始复盘摘要：{source['original']['artifact_sha256']}",f"当期奖金登记摘要：{payout['artifact_digest']}",
              f"奖金来源：{payout['body']['source_url']}；规则：{RULES_URL}"]
    winners=[r for r in result['tickets'] if r['tier']]
    def line(r):
        return f"| {r['rank']} | "+' '.join(f'{n:02d}' for n in r['red'])+f" | {r['blue']:02d} | "+(' '.join(f'{n:02d}' for n in r['hit_numbers']) or '—')+f" | {'是' if r['blue_hit'] else '否'} | {NAMES[r['tier']]} | {r['gross_cny']} |"
    for title,rows in [('中奖明细',winners),('全部100注明细',result['tickets'])]:
        if not result['tickets']:continue
        lines += ['',title,'| 排名 | 预测红球 | 预测蓝球 | 命中红球 | 蓝球命中 | 奖级 | 税前奖金（元） |','| ---: | --- | ---: | --- | --- | --- | ---: |']
        lines += [line(r) for r in rows] or ['本期无中奖注。']
    esc=html.escape
    red_html=' '.join(f'<span style="display:inline-block;background:#c62828;color:white;border-radius:50%;padding:9px;font-weight:bold">{n:02d}</span>' for n in label['red'])
    blue_html=f'<span style="display:inline-block;background:#1565c0;color:white;border-radius:50%;padding:9px;font-weight:bold">{blue}</span>'
    def table(rows):
        head='<tr>'+''.join(f'<th style="padding:8px;border-bottom:2px solid #ccc">{t}</th>' for t in ['排名','预测红球','蓝球','命中红球','蓝球命中','奖级','税前奖金'])+'</tr>'
        body=''
        for r in rows:
            numbers=' '.join(f'<b style="color:#c62828">{n:02d}</b>' if n in r['hit_numbers'] else f'{n:02d}' for n in r['red'])
            cells=[str(r['rank']),numbers,f"{r['blue']:02d}",' '.join(f'{n:02d}' for n in r['hit_numbers']) or '—','是' if r['blue_hit'] else '否',NAMES[r['tier']],'¥'+r['gross_cny']]
            body+='<tr>'+''.join(f'<td style="padding:7px;border-bottom:1px solid #ddd">{c}</td>' for c in cells)+'</tr>'
        return '<table style="border-collapse:collapse;width:100%;font-size:14px">'+head+body+'</table>'
    rich=f'<div style="font-family:Arial,sans-serif;max-width:1000px;margin:auto;color:#202124"><h2>第 {issue} 期 · 遗漏学习开奖复盘</h2><h3>开奖号码</h3><p>{red_html}　{blue_html}</p>'
    rich+=f'<div style="background:#f3f6fa;border-left:5px solid #245a85;padding:16px;font-size:18px;font-weight:bold">{esc(summary)}</div>'
    rich+=f'<p>100注 × 2元 × 1倍；净收益＝税前奖金－投入；收益率＝净收益÷投入。<br>{esc(SCOPE)}<br>仅为模拟核算，不代表实际购买或收入。</p>' if result['tickets'] else ''
    if result['tickets']:
        rich+='<p>'+esc('；'.join(f"{NAMES[k]} {result['tier_counts'][str(k)]}注" for k in range(1,7)))+'</p><h3>中奖明细</h3>'+(table(winners) if winners else '<p>本期无中奖注。</p>')+'<h3>全部100注明细（红色为命中号码）</h3>'+table(result['tickets'])
    rich+='<p>'+esc(NOTICE)+'</p><details><summary>封存和来源</summary><pre style="white-space:pre-wrap">'+esc('\n'.join(lines[lines.index(NOTICE)+1:lines.index('中奖明细')] if '中奖明细' in lines else lines[lines.index(NOTICE)+1:]))+'</pre></details></div>'
    return {'subject':subject,'text':'\n'.join(lines)+'\n','html':rich,'settlement':result}
