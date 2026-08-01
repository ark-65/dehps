from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from dehps.input_contracts.candidate_abi import validate_candidate_numbers
from dehps.prediction.v2.contracts import require_issue, seal_artifact, verify_artifact
from dehps.prediction.v2.generator import UNIVERSE


def build_pre_draw_report(
    *,
    contract: Mapping[str, Any],
    state: Mapping[str, Any],
    pool: Mapping[str, Any],
    top100: Mapping[str, Any],
) -> dict[str, Any]:
    verified_contract = verify_artifact(contract, domain="dehps.prediction-v2.shadow-contract.v1")
    verified_state = verify_artifact(state, domain="dehps.prediction-v2.state-artifact.v1")
    verified_pool = verify_artifact(pool, domain="dehps.prediction-v2.shadow-pool-artifact.v1")
    verified_top100 = verify_artifact(
        top100,
        domain="dehps.prediction-v2.shadow-top100-artifact.v1",
    )
    as_of = require_issue(verified_top100.get("as_of_issue"), field="as_of_issue")
    target = require_issue(verified_top100.get("target_issue"), field="target_issue")
    if verified_top100.get("contract_digest") != verified_contract.get("artifact_digest"):
        raise ValueError("Top100 is not bound to the supplied contract")
    if verified_top100.get("state_artifact_digest") != verified_state.get("artifact_digest"):
        raise ValueError("Top100 is not bound to the supplied state")
    if verified_top100.get("pool_artifact_digest") != verified_pool.get("artifact_digest"):
        raise ValueError("Top100 is not bound to the supplied pool")
    candidates = list(verified_top100.get("candidates") or [])
    if len(candidates) != 100:
        raise ValueError("pre-draw shadow report requires exactly 100 candidates")
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-pre-draw-report.v1",
            "artifact_type": "PredictionV2PreDrawReport.v1",
            "shadow_only": True,
            "as_of_issue": as_of,
            "target_issue": target,
            "contract_digest": verified_contract["artifact_digest"],
            "state_artifact_digest": verified_state["artifact_digest"],
            "pool_artifact_digest": verified_pool["artifact_digest"],
            "top100_artifact_digest": verified_top100["artifact_digest"],
            "route": "BASELINE_ONLY",
            "ranking_semantics": "DETERMINISTIC_LEGAL_NULL_ORDER",
            "top100": candidates,
            "diversity_diagnostics": verified_top100["diversity_diagnostics"],
            "labels": {
                "prediction_status": "SHADOW_BASELINE",
                "measurement_health": "NOT_APPLICABLE",
                "historical_evidence": "NOT_RUN",
                "betting_recommendation": "NOT_AUTHORIZED",
            },
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "parent_digests": [
                verified_contract["artifact_digest"],
                verified_state["artifact_digest"],
                verified_pool["artifact_digest"],
                verified_top100["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.pre-draw-report.v1",
    )


def build_post_draw_report(
    *,
    pre_draw_report: Mapping[str, Any],
    actual_issue: str,
    actual_red_numbers: Sequence[object],
) -> dict[str, Any]:
    pre = verify_artifact(
        pre_draw_report,
        domain="dehps.prediction-v2.pre-draw-report.v1",
    )
    issue = require_issue(actual_issue, field="actual_issue")
    if issue != pre.get("target_issue"):
        raise ValueError("actual draw issue does not match the frozen pre-draw target")
    actual = validate_candidate_numbers(actual_red_numbers, universe=UNIVERSE)
    actual_set = set(actual)
    candidates = list(pre.get("top100") or [])
    overlaps: Counter[int] = Counter()
    exact_rank: int | None = None
    best_overlap = 0
    for item in candidates:
        numbers = validate_candidate_numbers(item.get("red_numbers") or (), universe=UNIVERSE)
        overlap = len(actual_set.intersection(numbers))
        overlaps[overlap] += 1
        best_overlap = max(best_overlap, overlap)
        if numbers == actual:
            exact_rank = int(item["rank"])
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-post-draw-report.v1",
            "artifact_type": "PredictionV2PostDrawReport.v1",
            "shadow_only": True,
            "issue": issue,
            "as_of_issue": pre["as_of_issue"],
            "actual_red_numbers": list(actual),
            "pre_draw_report_digest": pre["artifact_digest"],
            "top100_artifact_digest": pre["top100_artifact_digest"],
            "evaluation": {
                "exact_hit": exact_rank is not None,
                "exact_rank": exact_rank,
                "best_red_overlap": best_overlap,
                "overlap_histogram": {
                    str(overlap): overlaps.get(overlap, 0) for overlap in range(7)
                },
                "candidate_count": len(candidates),
            },
            "labels": {
                "prediction_status": "SHADOW_BASELINE_EVALUATED",
                "historical_evidence": "NOT_RUN",
                "predictive_claim": "NONE",
            },
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "parent_digests": [pre["artifact_digest"]],
        },
        domain="dehps.prediction-v2.post-draw-report.v1",
    )


def render_pre_draw_markdown(report: Mapping[str, Any]) -> str:
    value = verify_artifact(report, domain="dehps.prediction-v2.pre-draw-report.v1")
    rows = [
        f"# Prediction v2 Shadow Top100 — {value['target_issue']}",
        "",
        f"依据期：{value['as_of_issue']}",
        "路由：BASELINE_ONLY（可复现合法零模型顺序）",
        "状态：shadow only；HistoricalEvidence=NOT_RUN；Promotion Gate=CLOSED。",
        "说明：当前输出用于管线与回放验收，不构成预测优势或投注结论。",
        "",
        "| Rank | 红球 |",
        "| ---: | --- |",
    ]
    rows.extend(
        f"| {item['rank']} | {' '.join(f'{int(number):02d}' for number in item['red_numbers'])} |"
        for item in value["top100"]
    )
    rows.extend(("", f"Artifact digest: `{value['artifact_digest']}`", ""))
    return "\n".join(rows)


def render_post_draw_markdown(report: Mapping[str, Any]) -> str:
    value = verify_artifact(report, domain="dehps.prediction-v2.post-draw-report.v1")
    evaluation = value["evaluation"]
    return "\n".join(
        (
            f"# Prediction v2 Shadow 开奖后报告 — {value['issue']}",
            "",
            "开奖号码（红球）：" + " ".join(f"{int(number):02d}" for number in value["actual_red_numbers"]),
            f"Top100 精确命中：{'是' if evaluation['exact_hit'] else '否'}",
            f"最高红球重合数：{evaluation['best_red_overlap']}",
            f"重合分布：{evaluation['overlap_histogram']}",
            "",
            "状态：shadow only；HistoricalEvidence=NOT_RUN；不产生预测能力结论。",
            f"Pre-draw digest: `{value['pre_draw_report_digest']}`",
            f"Artifact digest: `{value['artifact_digest']}`",
            "",
        )
    )
