"""Frozen definitions preserved from dehps/prediction/error_learning.py.

Original files remain the legacy compatibility implementation. This release-local
copy has explicit calculation-only imports; scientific bodies are checked against
the originals. No historical digest or source contract is rewritten.
"""
from __future__ import annotations

import bisect
import html
import json
import math
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Mapping
from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import candidate_rank, candidate_unrank
from .sampling import UNIVERSE, _sample_lex_ids
from . import calculation as p3
from . import report as notification


GOAL = "dehps-mainline-prediction-error-learning"


DOMAIN = "dehps.prediction-error-learning.sidecar.v1"


class DecisionIntegrityError(ValueError):
    """Prediction/label provenance failure: never downgrade to report failure."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise DecisionIntegrityError(reason)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    _require(parsed.tzinfo is not None, "timezone_required")
    return parsed


def _seal(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    result = {"schema_version": "dehps-prediction-error-learning.v1",
              "kind": kind, "goal": GOAL, "body": deepcopy(body)}
    result["digest"] = canonical_digest(result, domain=DOMAIN)
    return result


def verify_sidecar(value: Mapping[str, Any], kind: str) -> dict[str, Any]:
    result = deepcopy(dict(value))
    digest = result.pop("digest", None)
    _require(result.get("kind") == kind and result.get("goal") == GOAL
             and result.get("schema_version") == "dehps-prediction-error-learning.v1"
             and canonical_digest(result, domain=DOMAIN) == digest,
             "sidecar_identity_changed")
    return {**result, "digest": digest}


@dataclass(frozen=True)
class FrozenInputs:
    source: dict[str, Any]
    preregistration: dict[str, Any]
    dataset: dict[str, Any]
    model: dict[str, Any]
    predraw: notification.PredrawBundle
    registration_proof: list[dict[str, Any]] = field(default_factory=list)


def verify_frozen(inputs: FrozenInputs, *, code_root: Path) -> None:
    """Recompute only from frozen inputs, before accepting any outcome label."""
    try:
        source = p3.load_source_contract(root_dir=code_root)
        _require(source == inputs.source, "frozen_source_changed")
        for artifact in (inputs.preregistration, inputs.dataset, inputs.model,
                         *asdict(inputs.predraw).values()):
            if isinstance(artifact, dict):
                p3.validate_artifact(artifact)
        issue = inputs.predraw.issue
        body = inputs.dataset["body"]
        rows = body["rows"]
        _require(body["target_issue"] == issue and body["future_rows_read"] is False,
                 "dataset_boundary_changed")
        _require(len({row["issue"] for row in rows}) == len(rows)
                 and all(row["issue"] < issue for row in rows), "future_or_duplicate_history")
        dataset, model = p3.fit_model_artifacts(
            source_contract=source, preregistration=inputs.preregistration,
            history_rows=[(r["issue"], date.fromisoformat(r["draw_date"]), r["red_numbers"])
                          for r in rows], target_issue=issue)
        _require(dataset == inputs.dataset and model == inputs.model,
                 "frozen_refit_not_reproducible")
        checkpoint = inputs.predraw.checkpoint["body"]
        original_time = _time(checkpoint["sealed_at"])
        official = _time(checkpoint["official_draw_time"])
        _require(all(date.fromisoformat(r["draw_date"]) <= original_time.date() for r in rows),
                 "history_date_after_seal")
        regenerated = p3.generate_predraw_artifacts(
            preregistration=inputs.preregistration, model=model,
            target_draw_date=official.date(), sealed_at=original_time)
        actual = (inputs.predraw.model_candidates, inputs.predraw.random_baseline,
                  inputs.predraw.checkpoint, inputs.predraw.report)
        _require(regenerated == actual, "formal_prediction_parity_failed")
        replay = p3.build_predraw_replay_artifact(
            model_candidates=actual[0], random_baseline=actual[1],
            checkpoint=actual[2], report=actual[3])
        _require(replay == inputs.predraw.replay, "predraw_replay_changed")
        for proof in inputs.registration_proof:
            if proof.get("event_type") == "completed":
                _require(_time(proof["recorded_at"]) < official,
                         "registration_not_before_draw")
    except DecisionIntegrityError:
        raise
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise DecisionIntegrityError("invalid_frozen_decision") from exc


def capture_decision(inputs: FrozenInputs, *, code_root: Path) -> dict[str, Any]:
    """No clock override and no label parameter; past records cannot be backdated."""
    verify_frozen(inputs, code_root=code_root)
    now = datetime.now(timezone.utc)
    checkpoint = inputs.predraw.checkpoint["body"]
    _require(now >= _time(checkpoint["sealed_at"]), "original_seal_in_future")
    before = now < _time(checkpoint["official_draw_time"])
    return _seal("decision", {
        "issue": inputs.predraw.issue,
        "recorded_at": now.isoformat(),
        "record_mode": "PREDRAW_OBSERVATION" if before else "POST_HOC_DIAGNOSTIC_INDEX",
        "original_sealed_at": checkpoint["sealed_at"],
        "new_prediction": False,
        "registration_status": ("REGISTERED_PARENTS_VERIFIED" if inputs.registration_proof
                                else "REGISTRATION_NOT_ATTESTED_OFFLINE_INPUT_ONLY"),
        "data_boundary": {"training_end_issue": inputs.model["body"]["training_end_issue"],
                          "cutoff_timestamp": None,
                          "limitation": "Original data cutoff is issue-bounded; exact ingestion cutoff timestamp was not recorded."},
        "value_kind": "MARGINAL_RED_EVENT_PROBABILITIES_NOT_JOINT_COMBINATION_PROBABILITY",
        "model_version": inputs.model["artifact_digest"],
        "feature_version": inputs.model["body"]["feature_digest"],
        "training_rule": "q_i=(c_i+2/11)/(n+1); expanding audited history strictly through t-1",
        "mechanism": {"features": "33 historical event counts only", "interactions": False,
                      "proposal_count": 10000, "selection_count": 100,
                      "score": "sum of 33 Bernoulli log2 event scores",
                      "tie_break": "ascending lex_id", "extra_filter": None,
                      "diversification": None,
                      "blue_model": None,
                      "blue_assignment": "SHARED_DETERMINISTIC_UNIFORM_BLUE_BY_RANK_V1"},
        "frozen_inputs": asdict(inputs),
        "formal_output_parity": "EXACT_ALL_FOUR_ARTIFACTS_AND_REPLAY",
    })


def restore_decision(record: Mapping[str, Any], *, code_root: Path) -> FrozenInputs:
    record = verify_sidecar(record, "decision")
    raw = deepcopy(record["body"]["frozen_inputs"])
    raw["predraw"] = notification.PredrawBundle(**raw["predraw"])
    inputs = FrozenInputs(**raw)
    verify_frozen(inputs, code_root=code_root)
    body = record["body"]
    recorded = _time(body["recorded_at"])
    checkpoint = inputs.predraw.checkpoint["body"]
    expected_mode = ("PREDRAW_OBSERVATION" if recorded < _time(checkpoint["official_draw_time"])
                     else "POST_HOC_DIAGNOSTIC_INDEX")
    _require(body["issue"] == inputs.predraw.issue and body["record_mode"] == expected_mode
             and recorded >= _time(checkpoint["sealed_at"])
             and body["original_sealed_at"] == checkpoint["sealed_at"],
             "decision_time_or_issue_changed")
    return inputs


class DecisionIndex:
    """One 10,000-row deterministic recomputation; no enormous combination log."""

    def __init__(self, inputs: FrozenInputs):
        self.inputs = inputs
        self.probabilities = inputs.model["body"]["probabilities_q_1_to_33"]
        candidate = inputs.predraw.model_candidates["body"]
        ids = _sample_lex_ids(seed_material=bytes.fromhex(candidate["seed_digest"]),
                              count=candidate["proposal_pool_size"])
        self.rows = sorted(
            [(p3._ticket_score(candidate_unrank(i, universe=UNIVERSE), self.probabilities), i)
             for i in ids], key=lambda row: (-row[0], row[1]))
        self.keys = [(-score, lex_id) for score, lex_id in self.rows]
        self.ranks = {lex_id: rank for rank, (_, lex_id) in enumerate(self.rows, 1)}
        self.cache: dict[tuple[int, ...], dict[str, Any]] = {}
        # Fail closed even if a dependency changes after source verification.
        _require([(r["model_log2_score"], r["lex_id"]) for r in candidate["tickets"]]
                 == self.rows[:100], "rank_reconstruction_changed")

    def locate(self, numbers: list[int] | tuple[int, ...]) -> dict[str, Any]:
        red = tuple(numbers)
        if red in self.cache:
            return deepcopy(self.cache[red])
        lex_id = candidate_rank(red, universe=UNIVERSE)
        score = p3._ticket_score(red, self.probabilities)
        rank = self.ranks.get(lex_id)
        insertion = bisect.bisect_left(self.keys, (-score, lex_id)) + 1
        stage = "NOT_GENERATED" if rank is None else ("SCORE_BELOW_CUTOFF" if rank > 100 else "COVERED")
        result = {"red_numbers": list(red), "lex_id": lex_id, "score": score,
                  "first_loss_stage": stage, "actual_pool_rank": rank,
                  "hypothetical_insertion_rank": insertion,
                  "rank_scope": "frozen 10000-proposal pool; insertion does not make an ungenerated ticket eligible",
                  "score_minus_top100_cutoff": score - self.rows[99][0],
                  "generated": rank is not None, "selected": rank is not None and rank <= 100,
                  "passes_extra_filter": None, "extra_filter": "NOT_APPLIED_IN_FORMAL_P3",
                  "final_selection_exclusion": "NOT_APPLIED_AFTER_TOP100_CUTOFF"}
        self.cache[red] = result
        return deepcopy(result)

    def replace(self, numbers: list[int], *, remove: int, add: int) -> dict[str, Any]:
        _require(remove in numbers and add not in numbers and 1 <= add <= 33,
                 "invalid_number_replacement")
        before = self.locate(numbers)
        after = self.locate(sorted((set(numbers) - {remove}) | {add}))
        q = self.probabilities
        ranks = {number: rank for rank, number in enumerate(
            sorted(range(1, 34), key=lambda number: (-q[number - 1], number)), 1)}
        counts = self.inputs.model["body"]["number_event_counts_1_to_33"]
        def number_info(number: int) -> dict[str, Any]:
            return {"number": number, "marginal_probability": q[number - 1],
                    "display_rank_probability_then_number": ranks[number],
                    "probability_rank": 1 + sum(value > q[number - 1] for value in q),
                    "historical_event_count": counts[number - 1],
                    "selection_log2_odds": math.log2(q[number - 1] / (1 - q[number - 1]))}
        removed, added = number_info(remove), number_info(add)
        contributions = {
            "removed_event_delta": math.log2(1 - q[remove - 1]) - math.log2(q[remove - 1]),
            "added_event_delta": math.log2(q[add - 1]) - math.log2(1 - q[add - 1]),
            "other_31_events_delta": 0.0, "interaction_contribution": None}
        return {"remove": removed, "add": added, "before": before, "after": after,
                "score_delta": after["score"] - before["score"],
                "insertion_rank_delta": after["hypothetical_insertion_rank"] - before["hypothetical_insertion_rank"],
                "exact_additive_contributions": contributions,
                "interpretation": "Frozen model score mechanics, not a cause of the draw; no learned interaction."}


def verify_opened_outcome(inputs: FrozenInputs, bundle: notification.PostdrawBundle,
                          payout: dict[str, Any], *, available_at: str) -> dict[str, Any]:
    """Payout must come from the already-open per-issue registered report path."""
    try:
        _require(bundle.predraw == inputs.predraw, "postdraw_prediction_changed")
        settlement = p3.validate_artifact(bundle.settlement)
        p3.validate_artifact(bundle.settlement_replay)
        sb = settlement["body"]
        _require(sb["target_issue"] == inputs.predraw.issue and sb["status"] == "SETTLED"
                 and sb["lineage_id"] == p3.LINEAGE_ID and sb["configuration_drift"] is False,
                 "settlement_identity_changed")
        _require(settlement["parent_digests"] == [inputs.model["artifact_digest"],
                 inputs.predraw.model_candidates["artifact_digest"],
                 inputs.predraw.random_baseline["artifact_digest"],
                 inputs.predraw.checkpoint["artifact_digest"]], "settlement_parent_changed")
        reproduced_settlement = p3.build_settlement_artifact(
            model=inputs.model, model_candidates=inputs.predraw.model_candidates,
            random_baseline=inputs.predraw.random_baseline, checkpoint=inputs.predraw.checkpoint,
            actual_red_numbers=sb["actual_red_numbers"], actual_blue_number=sb["actual_blue_number"],
            durable_event_key=sb["durable_event_key"], history_fingerprint=sb["history_fingerprint"],
            cohort_index=sb["cohort_index"])
        _require(reproduced_settlement == settlement, "settlement_parity_failed")
        expected = p3.build_settlement_replay_artifact(
            settlement=settlement, checkpoint=inputs.predraw.checkpoint)
        _require(expected == bundle.settlement_replay, "settlement_replay_changed")
        red, blue = sb["actual_red_numbers"], sb["actual_blue_number"]
        candidate_rank(red, universe=UNIVERSE)
        _require(type(blue) is int and 1 <= blue <= 16, "blue_label_invalid")
        payout = notification.validate_notification_artifact(payout)
        pb = payout["body"]
        _require(pb["issue"] == inputs.predraw.issue and pb["actual_red_numbers"] == red
                 and pb["actual_blue_number"] == blue and pb["status"] == "EXACT_ISSUE_PAYOUT_VALIDATED",
                 "opened_payout_labels_changed")
        available = _time(available_at)
        _require(_time(inputs.predraw.checkpoint["body"]["official_draw_time"]) <= available
                 <= datetime.now(timezone.utc), "label_availability_invalid")
        # Preserve the existing accounting implementation and its parent validation.
        return notification.build_post_report(bundle=bundle, payout=payout,
                                               recipient_digest="0" * 64)
    except DecisionIntegrityError:
        raise
    except (KeyError, ValueError, TypeError, RuntimeError) as exc:
        raise DecisionIntegrityError("invalid_opened_outcome") from exc


def _build_sample(record: dict[str, Any], inputs: FrozenInputs,
                 bundle: notification.PostdrawBundle, *, available_at: str) -> dict[str, Any]:
    """Internal: called only after frozen input and opened-outcome verification."""
    red = bundle.settlement["body"]["actual_red_numbers"]
    blue = bundle.settlement["body"]["actual_blue_number"]
    return _seal("learning_sample", {
        "issue": inputs.predraw.issue, "decision_digest": record["digest"],
        "original_prediction_digest": inputs.predraw.checkpoint["artifact_digest"],
        "model_digest": inputs.model["artifact_digest"],
        "dataset_digest": inputs.dataset["artifact_digest"],
        "settlement_digest": bundle.settlement["artifact_digest"],
        "settlement_replay_digest": bundle.settlement_replay["artifact_digest"],
        "original_checkpoint": inputs.predraw.checkpoint,
        "opened_settlement": bundle.settlement,
        "feature_version": inputs.model["body"]["feature_digest"],
        "features": {"number_event_counts_1_to_33": inputs.model["body"]["number_event_counts_1_to_33"],
                     "training_issue_count": inputs.model["body"]["training_issue_count"]},
        "original_marginal_probabilities": inputs.model["body"]["probabilities_q_1_to_33"],
        "original_top100": inputs.predraw.model_candidates["body"]["tickets"],
        "red_labels_1_to_33": [int(number in red) for number in range(1, 34)],
        "blue_labels_1_to_16": [int(number == blue) for number in range(1, 17)],
        "actual_red_numbers": red, "actual_blue_number": blue,
        "label_available_at": available_at,
        "sampling_rule": "ALL_OPENED_ISSUES_REGARDLESS_OF_SUCCESS; ALL_100_TICKETS",
        "training_status": "RECORDED_NOT_INGESTED_BY_NEW_LEARNER",
        "formal_refit": "Existing expanding-count refit remains unchanged; ingestion must be proven by the later frozen dataset, not this sample write.",
        "predictive_improvement": "NOT_EVALUATED",
    })


def eligible_samples(samples: list[dict[str, Any]], *, target_issue: str,
                     prediction_at: str) -> list[dict[str, Any]]:
    """Fail on a bad batch, rather than silently allow same-issue labels."""
    cutoff = _time(prediction_at)
    notification._issue(target_issue)
    output, seen = [], set()
    for raw in samples:
        sample = verify_sidecar(raw, "learning_sample")
        body = sample["body"]
        notification._issue(body["issue"])
        checkpoint = p3.validate_artifact(body["original_checkpoint"])
        settlement = p3.validate_artifact(body["opened_settlement"])
        _require(body["issue"] == checkpoint["body"]["target_issue"] == settlement["body"]["target_issue"]
                 and checkpoint["artifact_digest"] == body["original_prediction_digest"]
                 and settlement["artifact_digest"] == body["settlement_digest"]
                 and checkpoint["artifact_digest"] in settlement["parent_digests"]
                 and checkpoint["body"]["model_digest"] == body["model_digest"]
                 and body["actual_red_numbers"] == settlement["body"]["actual_red_numbers"]
                 and body["actual_blue_number"] == settlement["body"]["actual_blue_number"],
                 "learning_sample_source_chain_changed")
        _require(body["issue"] not in seen, "duplicate_learning_issue")
        _require(body["issue"] < target_issue and _time(body["label_available_at"]) < cutoff,
                 "label_not_available_for_prediction")
        candidate_rank(body["actual_red_numbers"], universe=UNIVERSE)
        _require(type(body["actual_blue_number"]) is int and 1 <= body["actual_blue_number"] <= 16,
                 "invalid_blue_label")
        _require(body["red_labels_1_to_33"] == [int(i in body["actual_red_numbers"]) for i in range(1, 34)]
                 and body["blue_labels_1_to_16"] == [int(i == body["actual_blue_number"]) for i in range(1, 17)],
                 "incomplete_labels")
        seen.add(body["issue"])
        output.append(sample)
    return sorted(output, key=lambda sample: sample["body"]["issue"])


def diagnose(index: DecisionIndex, red: list[int], blue: int) -> dict[str, Any]:
    candidate_rank(red, universe=UNIVERSE)
    actual = set(red)
    tickets = index.inputs.predraw.model_candidates["body"]["tickets"]
    all_tickets = []
    for ticket in tickets:
        numbers = ticket["red_numbers"]
        missing, extra = sorted(actual - set(numbers)), sorted(set(numbers) - actual)
        all_tickets.append({"rank": ticket["rank"], "red_numbers": numbers,
                            "blue_number": ticket["blue_number"], "red_hits": 6 - len(missing),
                            "blue_hit": ticket["blue_number"] == blue,
                            "missing": missing, "extra": extra,
                            "replacements": [index.replace(numbers, remove=remove, add=add)
                                             for remove in extra for add in missing]})
    frequency = Counter(number for ticket in tickets for number in ticket["red_numbers"])
    overlap = Counter(len(set(a["red_numbers"]) & set(b["red_numbers"])) for a, b in combinations(tickets, 2))
    hit_counts = Counter(ticket["red_hits"] for ticket in all_tickets)
    winning = index.locate(red)
    return {"mode": "POST_HOC_DIAGNOSTIC_NOT_NEW_PREDICTION", "winning_combination": winning,
            "all_100_tickets": all_tickets,
            "portfolio": {"number_frequency_1_to_33": [frequency[i] for i in range(1, 34)],
                          "pairwise_overlap_histogram": {str(i): overlap[i] for i in range(7)},
                          "red_hit_histogram": {str(i): hit_counts[i] for i in range(7)},
                          "number_exposure_hhi": sum((frequency[i] / 600) ** 2 for i in range(1, 34)),
                          "red_complete_hit_count": hit_counts[6],
                          "full_red_blue_hit_count": sum(t["red_hits"] == 6 and t["blue_hit"] for t in all_tickets)},
            "attribution": {"candidate_selection": winning["first_loss_stage"],
                            "model_scoring": "Frozen score/rank and additive count effects only; a miss does not establish a model defect.",
                            "learnable_cause": "NO_CLEAR_LEARNABLE_CAUSE_FROM_ONE_ISSUE",
                            "feature_failure": "No additional features in this model",
                            "probability_calibration": "Requires an authorized multi-issue evaluation",
                            "concentration": "Descriptive portfolio exposure, not evidence of a learnable draw mechanism"},
            "cumulative_error_patterns": {"status": "NOT_COMPUTED_SEALED_AGGREGATES_NOT_READ",
                                          "reason": "Only the explicitly opened issue is consumed; no cross-issue inference."}}


def render_preview(base: dict[str, Any], diagnosis: dict[str, Any], sample: dict[str, Any]) -> str:
    winning = diagnosis["winning_combination"]
    portfolio = diagnosis["portfolio"]
    stage_names = {"NOT_GENERATED": "未生成", "SCORE_BELOW_CUTOFF": "评分排名不足，未进入 Top-100",
                   "COVERED": "已覆盖", "UNKNOWN": "无法判断"}
    pool_rank = winning["actual_pool_rank"] if winning["generated"] else "无（未进入候选池）"
    lines = [base["body"]["text"], "", "误差归因 / 本期漏选原因",
             f"中奖红球组合首次落选阶段：{stage_names[winning['first_loss_stage']]}",
             f"冻结评分：{winning['score']:.12f}；实际候选池排名：{pool_rank}",
             f"假设插入原候选池后的排名：{winning['hypothetical_insertion_rank']}（不是实际生成或入选记录）",
             "当前合同无额外分散筛选；仅生成、评分和 Top-100 截断。",
             "以下逐票分析全部 100 注；分数贡献只解释模型计算，不是开奖原因；模型没有交互项。",
             f"模型仅使用开奖前 {sample['body']['features']['training_issue_count']} 期的单球历史计数 c；边际概率 q=(c+2/11)/(n+1)。",
             f"红球全中：{portfolio['red_complete_hit_count']} 注；完整红蓝组合命中：{portfolio['full_red_blue_hit_count']} 注。",
             f"红球命中分布：{portfolio['red_hit_histogram']}",
             f"号码集中度（HHI）：{portfolio['number_exposure_hhi']:.6f}",
             "33 个号码出现次数：" + "，".join(f"{i:02d}号 {count}次" for i, count in enumerate(portfolio['number_frequency_1_to_33'], 1)),
             f"100 注两两重叠分布：{portfolio['pairwise_overlap_histogram']}"]
    for ticket in diagnosis["all_100_tickets"]:
        lines.append(f"#{ticket['rank']:03d} 遗漏 {ticket['missing']}；多选 {ticket['extra']}；红中 {ticket['red_hits']}")
        for pair in ticket["replacements"]:
            old, new = pair["remove"], pair["add"]
            contribution = pair["exact_additive_contributions"]
            lines.append(
                f"  {old['number']}→{new['number']}：边际概率 {old['marginal_probability']:.8f}→{new['marginal_probability']:.8f}，"
                f"单球排名 {old['probability_rank']}→{new['probability_rank']}，历史计数 {old['historical_event_count']}→{new['historical_event_count']}；"
                f"组合分差 {pair['score_delta']:+.10f}，假设插入排名 {pair['before']['hypothetical_insertion_rank']}→{pair['after']['hypothetical_insertion_rank']}，"
                f"原生成/筛选结果：{stage_names[pair['after']['first_loss_stage']]}；"
                f"移除项贡献 {contribution['removed_event_delta']:+.10f}，加入项贡献 {contribution['added_event_delta']:+.10f}（其余31项不变）。")
    lines += ["", "累计误差模式", "未计算：本预览仅消费获准开放的当期资料，不读取封存汇总；单期现象不能证明可学习规律。",
              "", "学习状态", "本期全部红球/蓝球标签和原始预测已形成完整样本，包括成功和失败票据。",
              "完整样本已保存，尚未接入新学习规则。", "现有正式扩展计数训练规则未改变；本记录不代表新学习规则已进入训练。",
              "未新增调参或策略，尚未评估后续预测改进。", "离线预览，未发送邮件；盈亏始终为模拟盈亏。"]
    return "\n".join(lines)


def build_preview(record: dict[str, Any], bundle: notification.PostdrawBundle,
                  payout: dict[str, Any], *, code_root: Path, available_at: str,
                  renderer: Callable = render_preview, analyzer: Callable = diagnose) -> dict[str, Any]:
    # Mandatory validation and scoring reconstruction stay outside the optional
    # report failure boundary. Never use a blanket catch to bypass integrity.
    inputs = restore_decision(record, code_root=code_root)
    base = verify_opened_outcome(inputs, bundle, payout, available_at=available_at)
    index = DecisionIndex(inputs)
    sample = _build_sample(record, inputs, bundle, available_at=available_at)
    result = {"status": "OFFLINE_VERIFIED", "base_report": base, "sample": sample,
              "integration": "INTEGRATION_PENDING", "new_prediction": False}
    try:
        diagnosis = analyzer(index, sample["body"]["actual_red_numbers"], sample["body"]["actual_blue_number"])
        text = renderer(base, diagnosis, sample)
        result.update(diagnosis=diagnosis, text=text, html=preview_html(text))
    except DecisionIntegrityError:
        raise
    except Exception as exc:
        result.update(status="DIAGNOSTIC_REPORT_FAILED_BASE_REPORT_PRESERVED",
                      diagnostic_failure=type(exc).__name__,
                      text=base["body"]["text"] + "\n\n误差归因生成失败；已验证的原始模拟收益报告保留。\n学习状态：完整标签样本已记录，未进入新学习规则。")
    return result


def preview_html(text: str) -> str:
    """Keep every ticket available without a wall of replacement rows."""
    blocks, current = [], []
    for line in text.splitlines():
        if line.startswith("#") and "遗漏" in line:
            if current:
                blocks.append(current)
            current = [line]
        elif line == "累计误差模式":
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    content = []
    for block in blocks:
        if block[0].startswith("#") and "遗漏" in block[0]:
            content.append("<details><summary>" + html.escape(block[0]) + "</summary><pre>"
                           + html.escape("\n".join(block[1:])) + "</pre></details>")
        else:
            content.append("<pre>" + html.escape("\n".join(block)) + "</pre>")
    return ("<!doctype html><html lang='zh'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<title>预测复盘离线预览</title><style>body{font:16px/1.6 system-ui;margin:2rem auto;max-width:1100px;padding:0 1rem;color:#172633;background:#f7f9fc}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}details{background:white;padding:.7rem 1rem;margin:.5rem 0;border:1px solid #dae2eb;border-radius:8px}summary{cursor:pointer;font-weight:600}"
            "header{border-bottom:3px solid #426682;padding:1rem 0}</style><body><header><h1>预测误差归因与学习状态</h1>"
            "离线预览 · 事后诊断 · 模拟盈亏 · 未部署、未发送</header>" + "".join(content) + "</body></html>")


def missing_input_preview(base_report: dict[str, Any], *, missing: list[str]) -> dict[str, Any]:
    """Only for absent historical records, never for corrupt registered bytes."""
    base = notification.validate_notification_artifact(base_report)
    _require(base["artifact_type"] == notification.POST_REPORT_ARTIFACT_TYPE and bool(missing),
             "missing_input_report_invalid")
    text = (base["body"]["text"] + "\n\n误差归因\n缺少真实冻结记录：" + ", ".join(missing)
            + "。首次落选阶段 UNKNOWN；无法计算可靠替换排名，不用当前数据补造。\n累计误差模式\n未计算。"
            + "\n学习状态\nINCOMPLETE_NOT_TRAINABLE：未形成完整训练样本；原模拟盈亏报告保留。")
    return {"status": "MISSING_FROZEN_INPUT", "missing": missing,
            "first_loss_stage": "UNKNOWN", "sample": None, "base_report": base,
            "integration": "INTEGRATION_PENDING", "text": text, "html": preview_html(text)}
