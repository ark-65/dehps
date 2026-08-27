from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from . import isolated_challenger_v11_contract as contract

CNY = Decimal("0.01")
COST_CNY = Decimal("200.00")
TAX_FREE_BOUNDARY_CNY = Decimal("10000.00")
ABOVE_BOUNDARY_TAX_RATE = Decimal("0.20")
FIXED_PRIZES = {
    "third": Decimal("3000.00"),
    "fourth": Decimal("200.00"),
    "fifth": Decimal("10.00"),
    "sixth": Decimal("5.00"),
}


class IsolatedReportingError(contract.IsolatedChallengerContractError):
    pass


def _money(value: Decimal | str | float) -> Decimal:
    return Decimal(str(value)).quantize(CNY, rounding=ROUND_HALF_UP)


def ticket_tier(
    ticket: tuple[tuple[int, ...], int],
    *,
    winning_reds: tuple[int, ...],
    winning_blue: int,
) -> str | None:
    reds, blue = ticket
    red_hits = len(set(reds).intersection(winning_reds))
    blue_hit = blue == winning_blue
    if red_hits == 6 and blue_hit:
        return "first"
    if red_hits == 6:
        return "second"
    if red_hits == 5 and blue_hit:
        return "third"
    if red_hits == 5 or (red_hits == 4 and blue_hit):
        return "fourth"
    if red_hits == 4 or (red_hits == 3 and blue_hit):
        return "fifth"
    if blue_hit:
        return "sixth"
    return None


def settle_portfolio(
    tickets: Sequence[tuple[tuple[int, ...], int]],
    *,
    winning_reds: Sequence[int],
    winning_blue: int,
    first_prize_cny: Decimal | str | int,
    second_prize_cny: Decimal | str | int,
) -> dict[str, Any]:
    winning_red_tuple = tuple(int(item) for item in winning_reds)
    if (
        len(tickets) != contract.PORTFOLIO_SIZE
        or len(winning_red_tuple) != 6
        or winning_red_tuple != tuple(sorted(winning_red_tuple))
        or len(set(winning_red_tuple)) != 6
        or any(not 1 <= item <= 33 for item in winning_red_tuple)
        or not 1 <= int(winning_blue) <= 16
    ):
        raise IsolatedReportingError("settlement_input_invalid")
    prize_by_tier = {
        "first": _money(first_prize_cny),
        "second": _money(second_prize_cny),
        **FIXED_PRIZES,
    }
    tiers: Counter[str] = Counter()
    red_hit_distribution: Counter[int] = Counter()
    blue_hits = 0
    for ticket in tickets:
        reds, blue = ticket
        if (
            len(reds) != 6
            or tuple(sorted(reds)) != tuple(reds)
            or len(set(reds)) != 6
            or any(not 1 <= item <= 33 for item in reds)
            or not 1 <= blue <= 16
        ):
            raise IsolatedReportingError("settlement_ticket_invalid")
        red_hits = len(set(reds).intersection(winning_red_tuple))
        red_hit_distribution[red_hits] += 1
        blue_hits += int(blue == winning_blue)
        tier = ticket_tier(
            ticket, winning_reds=winning_red_tuple, winning_blue=winning_blue
        )
        if tier is not None:
            tiers[tier] += 1
    gross = _money(
        sum((prize_by_tier[tier] * count for tier, count in tiers.items()), Decimal(0))
    )
    tax = _money(
        Decimal(0)
        if gross <= TAX_FREE_BOUNDARY_CNY
        else gross * ABOVE_BOUNDARY_TAX_RATE
    )
    after_tax = _money(gross - tax)
    net = _money(after_tax - COST_CNY)
    roi = (net / COST_CNY).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return {
        "ticket_count": len(tickets),
        "cost_cny": str(COST_CNY),
        "tier_hit_counts": {tier: tiers.get(tier, 0) for tier in prize_by_tier},
        "gross_prize_cny": str(gross),
        "tax_rule": (
            "gross<=CNY10000: estimated tax CNY0; "
            "gross>CNY10000: estimated tax 20% of full gross"
        ),
        "estimated_tax_cny": str(tax),
        "estimated_after_tax_cny": str(after_tax),
        "net_cny": str(net),
        "roi": str(roi),
        "red_hit_distribution": {
            str(hits): red_hit_distribution.get(hits, 0) for hits in range(7)
        },
        "blue_hits": blue_hits,
        "actual_withholding_authoritative": True,
        "tax_authority": "PRC MOF/STA/MCA/GASC Announcement 2024 No.12",
    }


def percentile_position(
    challenger: Decimal | float, baseline: Sequence[Decimal | float]
) -> str:
    if len(baseline) != contract.BASELINE_REPLICATES:
        raise IsolatedReportingError("baseline_replicate_count_changed")
    observed = Decimal(str(challenger))
    count = sum(Decimal(str(item)) <= observed for item in baseline)
    return str(
        (
            (Decimal(1) + Decimal(count)) / Decimal(contract.BASELINE_REPLICATES + 1)
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    )


def predraw_subject(target_issue: str) -> str:
    return f"【隔离研发线 / 非正式预测】双色球 {contract.require_issue(target_issue)} Top-100"


def predraw_body(
    *,
    target_issue: str,
    configuration_id: str,
    cohort_id: str,
    model_summary: str,
    feature_summary: Sequence[str],
    maximum_training_issue: str,
    tickets: Sequence[tuple[tuple[int, ...], int]],
    checkpoint_digest: str,
    prediction_digest: str,
    source_digest: str,
) -> str:
    if len(tickets) != contract.PORTFOLIO_SIZE:
        raise IsolatedReportingError("predraw_top100_count_changed")
    lines = [
        "隔离研发线预测（RESEARCH_ONLY / SHADOW）",
        "这不是 Formal P3，也不会触发 Promotion；不保证中奖。",
        f"目标期号：{contract.require_issue(target_issue)}",
        f"候选配置：{configuration_id}",
        f"候选 cohort：{cohort_id}",
        f"模型摘要：{model_summary}",
        "特征摘要：" + ", ".join(str(item) for item in feature_summary),
        "固定候选 seed ordinal：0",
        f"训练数据截至：{contract.require_issue(maximum_training_issue)}（严格早于目标期）",
        f"假设投入：人民币 {COST_CNY} 元（100 注 × 2 元）",
        "证据状态：早期研究证据，不足以得出统计结论。",
        f"checkpoint：{checkpoint_digest}",
        f"prediction：{prediction_digest}",
        f"source：{source_digest}",
        "typed replay：VERIFIED；generic replay：VERIFIED",
        "",
        "Top-100（红球 + 蓝球）：",
    ]
    lines.extend(
        f"{index:03d}. {' '.join(f'{red:02d}' for red in reds)} + {blue:02d}"
        for index, (reds, blue) in enumerate(tickets, start=1)
    )
    return "\n".join(lines)


def postdraw_subject(target_issue: str) -> str:
    return f"【隔离研发线 / 开奖复盘】双色球 {contract.require_issue(target_issue)}"


def postdraw_body(
    *,
    target_issue: str,
    settlement: Mapping[str, Any],
    baseline_percentile: str,
    formal_p3_comparison: str,
    prediction_digest: str,
    settlement_digest: str,
    report_digest: str,
) -> str:
    required = {
        "cost_cny",
        "tier_hit_counts",
        "gross_prize_cny",
        "tax_rule",
        "estimated_tax_cny",
        "estimated_after_tax_cny",
        "net_cny",
        "roi",
        "red_hit_distribution",
        "blue_hits",
    }
    if not required.issubset(settlement):
        raise IsolatedReportingError("postdraw_settlement_incomplete")
    tiers = settlement["tier_hit_counts"]
    return "\n".join(
        [
            "隔离研发线开奖复盘（RESEARCH_ONLY / SHADOW）",
            f"期号：{contract.require_issue(target_issue)}",
            f"固定假设投入：人民币 {settlement['cost_cny']} 元",
            "中奖注数："
            + ", ".join(f"{tier}={count}" for tier, count in tiers.items()),
            f"中奖毛收益：人民币 {settlement['gross_prize_cny']} 元",
            f"税务规则：{settlement['tax_rule']}",
            f"预计税额：人民币 {settlement['estimated_tax_cny']} 元",
            f"预计税后到账：人民币 {settlement['estimated_after_tax_cny']} 元",
            "税费为合同估算，实际代扣与到账金额以彩票机构和税务机关为准。",
            f"净收益（税后到账-200）：人民币 {settlement['net_cny']} 元",
            f"ROI：{settlement['roi']}",
            f"红球命中分布：{settlement['red_hit_distribution']}",
            f"蓝球命中注数：{settlement['blue_hits']}",
            f"相对 1000 组合法随机组合的经验百分位：{baseline_percentile}",
            f"Formal P3 同期比较：{formal_p3_comparison}",
            "证据标签：INSUFFICIENT_FOR_STATISTICAL_CONCLUSION",
            f"prediction：{prediction_digest}",
            f"settlement：{settlement_digest}",
            f"report：{report_digest}",
            "typed replay：VERIFIED；generic replay：VERIFIED",
        ]
    )


def daily_subject(epoch_date: str) -> str:
    if len(epoch_date) != 8 or not epoch_date.isdigit():
        raise IsolatedReportingError("daily_epoch_date_invalid")
    return f"【隔离研发线 / 24小时研发报告】{epoch_date}"


def daily_body(summary: Mapping[str, Any]) -> str:
    fields = (
        "attempted",
        "succeeded",
        "failed",
        "timed_out",
        "retried",
        "family_distribution",
        "multiplicity_lifetime_total",
        "multiplicity_increment",
        "eligible_count",
        "leading_candidate",
        "cpu",
        "memory",
        "runtime",
        "checkpoint",
        "worker_health",
        "replay",
        "incidents",
        "recovery",
        "time_to_next_freeze",
    )
    missing = [field for field in fields if field not in summary]
    if missing:
        raise IsolatedReportingError("daily_summary_incomplete:" + ",".join(missing))
    lines = [
        "隔离研发线 24 小时研发报告（RESEARCH_ONLY / SHADOW）",
        "不会修改 Formal P3、P4、P5、P6 或 Promotion。",
    ]
    lines.extend(f"{field}: {summary[field]}" for field in fields)
    return "\n".join(lines)
