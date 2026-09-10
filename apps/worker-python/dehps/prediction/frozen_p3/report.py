"""Frozen definitions preserved from dehps/notifications/p3_top100.py.

Original files remain the legacy compatibility implementation. This release-local
copy has explicit calculation-only imports; scientific bodies are checked against
the originals. No historical digest or source contract is rewritten.
"""
from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from dehps.research_os.models import m4_v2_domain_digest
from . import calculation as p3


class P3Top100NotificationError(RuntimeError):
    """Fail-closed notification contract violation."""


PRE_ENVELOPE_ARTIFACT_TYPE = "P3Top100PreMailEnvelopeV1"


PRE_REPLAY_ARTIFACT_TYPE = "P3Top100PreMailReplayV1"


PAYOUT_SOURCE_ARTIFACT_TYPE = "P3Top100IssuePayoutSourceV1"


POST_REPORT_ARTIFACT_TYPE = "P3Top100PostReturnReportV1"


POST_REPLAY_ARTIFACT_TYPE = "P3Top100PostReturnReplayV1"


ARTIFACT_DOMAINS = {
    PRE_ENVELOPE_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.pre-envelope.v1",
    PRE_REPLAY_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.pre-replay.v1",
    PAYOUT_SOURCE_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.payout-source.v1",
    POST_REPORT_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.post-report.v1",
    POST_REPLAY_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.post-replay.v1",
}


PORTFOLIO_COST = Decimal("200.00")


TAX_FREE_BOUNDARY = Decimal("10000.00")


TAX_RATE = Decimal("0.20")


MONEY_QUANTUM = Decimal("0.01")


def _issue(value: Any) -> str:
    issue = str(value or "").strip()
    if not issue or not issue.isdigit():
        raise P3Top100NotificationError("notification_issue_changed")
    return issue


def _artifact(
    *, artifact_type: str, body: Mapping[str, Any], parent_digests: Sequence[str]
) -> dict[str, Any]:
    if artifact_type not in ARTIFACT_DOMAINS:
        raise P3Top100NotificationError("notification_artifact_type_changed")
    payload: dict[str, Any] = {
        "schema_version": f"dehps-{artifact_type}.v1",
        "artifact_type": artifact_type,
        "body": deepcopy(dict(body)),
        "parent_digests": [str(item) for item in parent_digests],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(
        payload, domain=ARTIFACT_DOMAINS[artifact_type]
    )
    return payload


def validate_notification_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    artifact_type = str(payload.get("artifact_type") or "")
    if artifact_type not in ARTIFACT_DOMAINS or set(payload) != {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "body",
        "parent_digests",
    }:
        raise P3Top100NotificationError("notification_artifact_shape_changed")
    if payload["schema_version"] != f"dehps-{artifact_type}.v1":
        raise P3Top100NotificationError("notification_artifact_schema_changed")
    digest = str(payload.pop("artifact_digest") or "")
    if m4_v2_domain_digest(payload, domain=ARTIFACT_DOMAINS[artifact_type]) != digest:
        raise P3Top100NotificationError("notification_artifact_digest_changed")
    payload["artifact_digest"] = digest
    return payload


@dataclass(frozen=True)
class PredrawBundle:
    issue: str
    model_candidates: dict[str, Any]
    random_baseline: dict[str, Any]
    checkpoint: dict[str, Any]
    report: dict[str, Any]
    replay: dict[str, Any]

    @property
    def input_digests(self) -> tuple[str, ...]:
        return (
            self.model_candidates["artifact_digest"],
            self.checkpoint["artifact_digest"],
            self.replay["artifact_digest"],
        )


@dataclass(frozen=True)
class PostdrawBundle:
    predraw: PredrawBundle
    settlement: dict[str, Any]
    settlement_replay: dict[str, Any]

    @property
    def input_digests(self) -> tuple[str, ...]:
        return (
            *self.predraw.input_digests,
            self.settlement["artifact_digest"],
            self.settlement_replay["artifact_digest"],
        )


def _validated_tickets(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    body = candidate["body"]
    tickets = body.get("tickets")
    if (
        body.get("mode") != "SHADOW_ONLY"
        or body.get("candidate_count") != 100
        or not isinstance(tickets, list)
        or len(tickets) != 100
    ):
        raise P3Top100NotificationError("notification_candidate_set_changed")
    seen: set[tuple[int, ...]] = set()
    output: list[dict[str, Any]] = []
    for expected_rank, item in enumerate(tickets, start=1):
        if not isinstance(item, Mapping) or int(item.get("rank", 0)) != expected_rank:
            raise P3Top100NotificationError("notification_candidate_rank_changed")
        red = tuple(int(value) for value in item.get("red_numbers", ()))
        blue = int(item.get("blue_number", 0))
        score = float(item.get("model_log2_score", float("nan")))
        if (
            len(red) != 6
            or red != tuple(sorted(red))
            or len(set(red)) != 6
            or red[0] < 1
            or red[-1] > 33
            or not 1 <= blue <= 16
            or not math.isfinite(score)
            or red in seen
        ):
            raise P3Top100NotificationError("notification_candidate_ticket_changed")
        seen.add(red)
        output.append(
            {"rank": expected_rank, "red_numbers": list(red), "blue_number": blue}
        )
    return output


def _decimal_money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value).replace(",", "")).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
    except Exception as exc:
        raise P3Top100NotificationError("notification_prize_amount_changed") from exc
    if amount < 0:
        raise P3Top100NotificationError("notification_prize_amount_changed")
    return amount


def prize_tier(*, red_hits: int, blue_hit: bool) -> int:
    if red_hits == 6 and blue_hit:
        return 1
    if red_hits == 6:
        return 2
    if red_hits == 5 and blue_hit:
        return 3
    if red_hits == 5 or (red_hits == 4 and blue_hit):
        return 4
    if red_hits == 4 or (red_hits == 3 and blue_hit):
        return 5
    if red_hits <= 2 and blue_hit:
        return 6
    return 0


def calculate_return(gross: Decimal) -> dict[str, str]:
    gross = gross.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    tax = (
        Decimal("0.00")
        if gross <= TAX_FREE_BOUNDARY
        else (gross * TAX_RATE).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    )
    after_tax = (gross - tax).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    net = (after_tax - PORTFOLIO_COST).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    roi = ((net / PORTFOLIO_COST) * Decimal(100)).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
    return {
        "hypothetical_cost_cny": "200.00",
        "gross_prize_cny": f"{gross:.2f}",
        "estimated_tax_cny": f"{tax:.2f}",
        "after_tax_receipt_cny": f"{after_tax:.2f}",
        "net_profit_cny": f"{net:.2f}",
        "roi_percent": f"{roi:.2f}",
    }


def build_post_report(
    *, bundle: PostdrawBundle, payout: Mapping[str, Any], recipient_digest: str
) -> dict[str, Any]:
    payout = validate_notification_artifact(payout)
    if payout["artifact_type"] != PAYOUT_SOURCE_ARTIFACT_TYPE:
        raise P3Top100NotificationError("notification_payout_artifact_changed")
    if payout["parent_digests"] != [
        bundle.settlement["artifact_digest"],
        bundle.settlement_replay["artifact_digest"],
    ]:
        raise P3Top100NotificationError("notification_payout_parent_changed")
    amounts = {
        int(item["tier"]): _decimal_money(item["single_ticket_gross_cny"])
        for item in payout["body"]["tiers"]
    }
    actual_red = {int(item) for item in bundle.settlement["body"]["actual_red_numbers"]}
    actual_blue = int(bundle.settlement["body"]["actual_blue_number"])
    winners: list[dict[str, Any]] = []
    tier_counts = {index: 0 for index in range(1, 7)}
    gross = Decimal("0.00")
    for ticket in _validated_tickets(bundle.predraw.model_candidates):
        red_hits = len(actual_red.intersection(ticket["red_numbers"]))
        blue_hit = int(ticket["blue_number"]) == actual_blue
        tier = prize_tier(red_hits=red_hits, blue_hit=blue_hit)
        if tier:
            amount = amounts[tier]
            gross += amount
            tier_counts[tier] += 1
            winners.append(
                {
                    **ticket,
                    "red_hits": red_hits,
                    "blue_hit": blue_hit,
                    "tier": tier,
                    "gross_prize_cny": f"{amount:.2f}",
                }
            )
    accounting = calculate_return(gross)
    losing_count = 100 - len(winners)
    subject = f"[DEHPS][开奖复盘·模拟收益] 双色球 {bundle.predraw.issue} 新P3 Top-100"
    lines = [
        f"双色球 {bundle.predraw.issue} 新P3 Top-100 开奖复盘",
        "开奖号码：红球 "
        + " ".join(f"{item:02d}" for item in sorted(actual_red))
        + f"  蓝球 {actual_blue:02d}",
        f"开奖结算回放：{bundle.settlement_replay['artifact_digest']}",
        f"奖金来源：中彩网当期 winnerDetails / {payout['body']['raw_record_sha256']}",
        "",
        "模拟投入：¥200.00（100 注 × ¥2.00）",
        f"税前中奖总额：¥{accounting['gross_prize_cny']}",
        f"预计应纳税额：¥{accounting['estimated_tax_cny']}",
        f"预计税后到账：¥{accounting['after_tax_receipt_cny']}",
        f"扣除200元后的净收益：¥{accounting['net_profit_cny']}",
        f"回报率：{accounting['roi_percent']}%",
        "",
        "中奖分布："
        + "，".join(f"{tier}等奖 {tier_counts[tier]} 注" for tier in range(1, 7))
        + f"，未中奖 {losing_count} 注",
        "中奖明细：",
    ]
    if winners:
        lines.extend(
            f"#{item['rank']:03d} 红球 "
            + " ".join(f"{value:02d}" for value in item["red_numbers"])
            + f" 蓝球 {item['blue_number']:02d}；红中{item['red_hits']} "
            + ("蓝中" if item["blue_hit"] else "蓝未中")
            + f"；{item['tier']}等奖 ¥{item['gross_prize_cny']}"
            for item in winners
        )
    else:
        lines.append("无中奖票据。")
    lines.extend(
        [
            "",
            (
                "税务口径：同一自然人、同一电脑彩票游戏、同一期全部中奖金额合并；"
                "合计不超过 ¥10,000.00 免征个人所得税，超过时按税前合计金额的 20% 估算。"
                "实际代扣及兑奖记录以彩票机构为准。"
            ),
            (
                "说明：这是固定模拟投入 200 元的账面复盘。DEHPS 不购买彩票、不确认实际购买、"
                "不保证中奖，也未证明概率优势；票据支持与奖金对 P3 科学决策均为零信用。"
            ),
        ]
    )
    text = "\n".join(lines)
    return _artifact(
        artifact_type=POST_REPORT_ARTIFACT_TYPE,
        body={
            "status": "COMPILED_NOT_DELIVERED",
            "issue": bundle.predraw.issue,
            "lineage_id": p3.LINEAGE_ID,
            "recipient_digest": recipient_digest,
            "subject": subject,
            "text": text,
            "html": f"<!doctype html><html><body><pre>{html.escape(text)}</pre></body></html>",
            "candidate_count": 100,
            "winner_count": len(winners),
            "losing_count": losing_count,
            "tier_counts": {str(key): value for key, value in tier_counts.items()},
            "winners": winners,
            "accounting": accounting,
            "tax_free_boundary_cny": "10000.00",
            "tax_rate_over_boundary": "0.20",
            "p3_decision_credit": False,
            "configuration_drift": False,
        },
        parent_digests=(
            *bundle.input_digests,
            payout["artifact_digest"],
        ),
    )
