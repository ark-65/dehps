from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from dehps.config import ROOT_DIR
from dehps.notifications import p3_top100 as notification
from dehps.prediction import error_learning as learning
from dehps.prediction.error_learning_io import ScopedReader
from dehps.research_os.information_theory.measurement_system_v2 import forward_prequential_confirmatory as p3


@pytest.fixture(scope="module")
def inputs():
    source = p3.load_source_contract()
    prereg, _ = p3.build_preregistration_artifacts(source_contract=source)
    history = [(f"{2000 + i // 153:04d}{i % 153 + 1:03d}", date(2000, 1, 1),
                sorted(((i + k) % 33) + 1 for k in range(6))) for i in range(900)]
    dataset, model = p3.fit_model_artifacts(source_contract=source, preregistration=prereg,
                                          history_rows=history, target_issue="2026102")
    candidates, baseline, checkpoint, report = p3.generate_predraw_artifacts(
        preregistration=prereg, model=model, target_draw_date=date(2026, 9, 3),
        sealed_at=datetime(2026, 9, 2, 12, tzinfo=p3.SHANGHAI))
    replay = p3.build_predraw_replay_artifact(model_candidates=candidates, random_baseline=baseline,
                                             checkpoint=checkpoint, report=report)
    return learning.FrozenInputs(source, prereg, dataset, model,
                                 notification.PredrawBundle("2026102", candidates, baseline, checkpoint, report, replay))


def outcome(inputs, *, success=False):
    first = inputs.predraw.model_candidates["body"]["tickets"][0]
    red, blue = (first["red_numbers"], first["blue_number"]) if success else ([1, 2, 3, 4, 5, 6], 7)
    settlement = p3.build_settlement_artifact(
        model=inputs.model, model_candidates=inputs.predraw.model_candidates,
        random_baseline=inputs.predraw.random_baseline, checkpoint=inputs.predraw.checkpoint,
        actual_red_numbers=red, actual_blue_number=blue, durable_event_key="audited-test-event",
        history_fingerprint="a" * 64, cohort_index=6)
    replay = p3.build_settlement_replay_artifact(settlement=settlement, checkpoint=inputs.predraw.checkpoint)
    bundle = notification.PostdrawBundle(inputs.predraw, settlement, replay)
    raw = {"issue": "2026102", "frontWinningNum": " ".join(map(str, red)), "backWinningNum": str(blue),
           "winnerDetails": [{"awardEtc": tier, "baseBetWinner": {"awardMoney": amount, "awardNum": tier * 10}}
                             for tier, amount in enumerate(("10000000", "264245", "3000", "200", "10", "5"), 1)]}
    return bundle, notification.normalize_payout_record(record=raw, bundle=bundle)


@pytest.fixture(scope="module")
def record(inputs):
    return learning.capture_decision(inputs, code_root=ROOT_DIR)


def preview(inputs, record, **kwargs):
    bundle, payout = outcome(inputs)
    return learning.build_preview(record, bundle, payout, code_root=ROOT_DIR,
                                  available_at="2026-09-03T22:00:00+08:00", **kwargs)


def test_capture_parity_and_no_backdated_prediction(inputs, record):
    before = deepcopy(inputs)
    restored = learning.restore_decision(record, code_root=ROOT_DIR)
    assert restored == before == inputs
    assert record["body"]["record_mode"] == "POST_HOC_DIAGNOSTIC_INDEX"
    assert record["body"]["new_prediction"] is False
    assert record["body"]["original_sealed_at"] != record["body"]["recorded_at"]
    assert record["body"]["data_boundary"]["cutoff_timestamp"] is None
    assert record["body"]["mechanism"]["interactions"] is False
    assert record["body"]["frozen_inputs"]["model"]["body"]["probability_fractions_q_1_to_33"]


def test_earliest_omission_and_score_rank_ties(inputs):
    index = learning.DecisionIndex(inputs)
    selected = inputs.predraw.model_candidates["body"]["tickets"][0]
    assert index.locate(selected["red_numbers"])["first_loss_stage"] == "COVERED"
    losing_id = index.rows[100][1]
    losing = learning.candidate_unrank(losing_id, universe=learning.UNIVERSE)
    assert index.locate(losing)["first_loss_stage"] == "SCORE_BELOW_CUTOFF"
    assert index.locate(losing)["actual_pool_rank"] == 101
    ungenerated = next(i for i in range(learning.UNIVERSE.cardinality) if i not in index.ranks)
    trace = index.locate(learning.candidate_unrank(ungenerated, universe=learning.UNIVERSE))
    assert trace["first_loss_stage"] == "NOT_GENERATED"
    assert trace["actual_pool_rank"] is None and trace["selected"] is False
    assert trace["passes_extra_filter"] is None
    assert trace["final_selection_exclusion"] == "NOT_APPLIED_AFTER_TOP100_CUTOFF"
    for rank in (1, 100, 101, 10000):
        row = learning.candidate_unrank(index.rows[rank - 1][1], universe=learning.UNIVERSE)
        assert index.locate(row)["hypothetical_insertion_rank"] == rank


def test_requested_two_for_seven_counterfactual_exact_contributions(inputs):
    index = learning.DecisionIndex(inputs)
    trace = index.replace([1, 3, 4, 5, 6, 7], remove=7, add=2)
    assert trace["after"]["red_numbers"] == [1, 2, 3, 4, 5, 6]
    q = inputs.model["body"]["probabilities_q_1_to_33"]
    analytic = math.log2(q[1] / (1 - q[1])) - math.log2(q[6] / (1 - q[6]))
    assert trace["score_delta"] == pytest.approx(analytic, abs=1e-13)
    c = trace["exact_additive_contributions"]
    assert trace["score_delta"] == pytest.approx(c["removed_event_delta"] + c["added_event_delta"], abs=1e-13)
    assert c["interaction_contribution"] is None
    assert trace["remove"]["historical_event_count"] == inputs.model["body"]["number_event_counts_1_to_33"][6]


@pytest.mark.parametrize("success", [False, True])
def test_all_tickets_complete_labels_and_report_preview(inputs, record, success):
    bundle, payout = outcome(inputs, success=success)
    before = deepcopy(bundle)
    result = learning.build_preview(record, bundle, payout, code_root=ROOT_DIR,
                                    available_at="2026-09-03T22:00:00+08:00")
    assert result["status"] == "OFFLINE_VERIFIED"
    assert bundle == before
    sample = result["sample"]["body"]
    assert len(sample["red_labels_1_to_33"]) == 33 and sum(sample["red_labels_1_to_33"]) == 6
    assert len(sample["blue_labels_1_to_16"]) == 16 and sum(sample["blue_labels_1_to_16"]) == 1
    assert len(sample["original_top100"]) == 100
    assert sample["training_status"] == "RECORDED_NOT_INGESTED_BY_NEW_LEARNER"
    tickets = result["diagnosis"]["all_100_tickets"]
    assert len(tickets) == 100 and [t["rank"] for t in tickets] == list(range(1, 101))
    assert all(len(t["replacements"]) == len(t["missing"]) * len(t["extra"]) for t in tickets)
    assert sum(result["diagnosis"]["portfolio"]["pairwise_overlap_histogram"].values()) == 4950
    assert sum(result["diagnosis"]["portfolio"]["red_hit_histogram"].values()) == 100
    assert sum(result["diagnosis"]["portfolio"]["number_frequency_1_to_33"]) == 600
    if success:
        assert result["diagnosis"]["portfolio"]["full_red_blue_hit_count"] == 1
    for phrase in ("模拟投入", "误差归因", "累计误差模式", "学习状态", "未发送邮件"):
        assert phrase in result["text"]
    assert result["diagnosis"]["attribution"]["learnable_cause"] == "NO_CLEAR_LEARNABLE_CAUSE_FROM_ONE_ISSUE"


@pytest.mark.parametrize("field", ["renderer", "analyzer"])
def test_explanation_failure_preserves_verified_prediction_settlement_and_pnl(inputs, record, field):
    def broken(*args):
        raise RuntimeError("diagnostic-only failure")
    result = preview(inputs, record, **{field: broken})
    bundle, payout = outcome(inputs)
    assert result["status"] == "DIAGNOSTIC_REPORT_FAILED_BASE_REPORT_PRESERVED"
    assert result["base_report"] == notification.build_post_report(bundle=bundle, payout=payout, recipient_digest="0" * 64)
    assert result["sample"]["body"]["training_status"] == "RECORDED_NOT_INGESTED_BY_NEW_LEARNER"
    # Canonical producers remain callable and byte-identical after the failure.
    assert p3.generate_predraw_artifacts(preregistration=inputs.preregistration, model=inputs.model,
        target_draw_date=date(2026, 9, 3), sealed_at=datetime(2026, 9, 2, 12, tzinfo=p3.SHANGHAI))[0] == bundle.predraw.model_candidates
    assert outcome(inputs)[0].settlement == bundle.settlement


def test_integrity_failure_never_downgraded_to_optional_report_error(inputs, record):
    broken = deepcopy(record)
    broken["body"]["frozen_inputs"]["predraw"]["model_candidates"]["body"]["tickets"][0]["blue_number"] = 16
    broken = learning._seal("decision", broken["body"])
    called = []
    with pytest.raises(learning.DecisionIntegrityError):
        preview(inputs, broken, renderer=lambda *args: called.append(True))
    assert not called
    def integrity_fault(*args):
        raise learning.DecisionIntegrityError("integrity")
    with pytest.raises(learning.DecisionIntegrityError, match="integrity"):
        preview(inputs, record, analyzer=integrity_fault)


def test_missing_history_not_reconstructed_from_current_data(inputs):
    dataset = deepcopy(inputs.dataset)
    dataset["body"].pop("rows")
    with pytest.raises(learning.DecisionIntegrityError):
        learning.capture_decision(replace(inputs, dataset=dataset), code_root=ROOT_DIR)


def test_missing_historical_record_preview_is_explicitly_unknown(inputs):
    bundle, payout = outcome(inputs)
    base = notification.build_post_report(bundle=bundle, payout=payout, recipient_digest="0" * 64)
    result = learning.missing_input_preview(base, missing=["registered_refit_dataset_and_model"])
    assert result["first_loss_stage"] == "UNKNOWN"
    assert result["sample"] is None
    assert result["base_report"] == base
    assert "不" in result["text"] and "INCOMPLETE_NOT_TRAINABLE" in result["text"]


def test_duplicate_and_current_issue_history_fail_even_with_resealed_artifact(inputs):
    for issue in (inputs.predraw.issue, inputs.dataset["body"]["rows"][0]["issue"]):
        body = deepcopy(inputs.dataset["body"])
        body["rows"][-1]["issue"] = issue
        dataset = p3._artifact(artifact_type=p3.DATASET_ARTIFACT_TYPE, body=body,
                               parent_digests=inputs.dataset["parent_digests"])
        with pytest.raises(learning.DecisionIntegrityError, match="future_or_duplicate_history"):
            learning.capture_decision(replace(inputs, dataset=dataset), code_root=ROOT_DIR)


def test_labels_never_available_to_same_or_earlier_prediction(inputs, record):
    result = preview(inputs, record)
    sample = result["sample"]
    for target in ("2026101", "2026102"):
        with pytest.raises(learning.DecisionIntegrityError, match="label_not_available"):
            learning.eligible_samples([sample], target_issue=target, prediction_at="2026-09-04T12:00:00+08:00")
    for moment in ("2026-09-03T21:30:00+08:00", "2026-09-03T22:00:00+08:00"):
        with pytest.raises(learning.DecisionIntegrityError, match="label_not_available"):
            learning.eligible_samples([sample], target_issue="2026103", prediction_at=moment)
    assert learning.eligible_samples([sample], target_issue="2026103", prediction_at="2026-09-04T12:00:00+08:00") == [sample]
    with pytest.raises(learning.DecisionIntegrityError, match="duplicate_learning_issue"):
        learning.eligible_samples([sample, sample], target_issue="2026103", prediction_at="2026-09-04T12:00:00+08:00")
    backdated_body = deepcopy(sample["body"])
    backdated_body["issue"] = "2026101"
    with pytest.raises(learning.DecisionIntegrityError, match="source_chain_changed"):
        learning.eligible_samples([learning._seal("learning_sample", backdated_body)],
                                  target_issue="2026102", prediction_at="2026-09-04T12:00:00+08:00")


def test_wrong_opened_labels_and_predraw_availability_fail(inputs, record):
    bundle, payout = outcome(inputs)
    body = deepcopy(payout["body"])
    body["actual_blue_number"] = 1
    changed = notification._artifact(artifact_type=notification.PAYOUT_SOURCE_ARTIFACT_TYPE,
                                      body=body, parent_digests=payout["parent_digests"])
    with pytest.raises(learning.DecisionIntegrityError, match="opened_payout_labels_changed"):
        learning.build_preview(record, bundle, changed, code_root=ROOT_DIR, available_at="2026-09-03T22:00:00+08:00")
    with pytest.raises(learning.DecisionIntegrityError, match="label_availability_invalid"):
        learning.build_preview(record, bundle, payout, code_root=ROOT_DIR, available_at="2026-09-03T17:00:00+08:00")


def test_wrong_label_encoding_and_settlement_scores_are_integrity_failures(inputs, record):
    sample = preview(inputs, record)["sample"]
    body = deepcopy(sample["body"])
    body["red_labels_1_to_33"] = list(reversed(body["red_labels_1_to_33"]))
    malformed = learning._seal("learning_sample", body)
    with pytest.raises(learning.DecisionIntegrityError, match="incomplete_labels"):
        learning.eligible_samples([malformed], target_issue="2026103", prediction_at="2026-09-04T12:00:00+08:00")
    bundle, payout = outcome(inputs)
    body = deepcopy(bundle.settlement["body"])
    body["model_probability_log2_score"] += 1
    corrupt = p3._artifact(artifact_type=p3.SETTLEMENT_ARTIFACT_TYPE, body=body,
                           parent_digests=bundle.settlement["parent_digests"])
    changed = replace(bundle, settlement=corrupt)
    with pytest.raises(learning.DecisionIntegrityError, match="settlement_parity_failed"):
        learning.build_preview(record, changed, payout, code_root=ROOT_DIR, available_at="2026-09-03T22:00:00+08:00")


def test_registration_after_draw_rejected_even_with_old_self_reported_seal(inputs):
    late = replace(inputs, registration_proof=[{"event_type": "completed", "recorded_at": "2026-09-04T00:00:00+08:00"}])
    with pytest.raises(learning.DecisionIntegrityError, match="registration_not_before_draw"):
        learning.capture_decision(late, code_root=ROOT_DIR)


def test_scoped_reader_blocks_aggregate_and_postdraw_reads_in_predraw_phase():
    calls = []
    repo = SimpleNamespace(list_mainline_execution_event_metadata=lambda **kw: calls.append(kw) or ())
    reader = ScopedReader(repo, issue="2026102", post=False)
    for task in (p3.review_task_key(20), p3.issue_task_keys("2026102")["settlement"], p3.issue_task_keys("2026101")["refit"]):
        with pytest.raises(learning.DecisionIntegrityError, match="outside_opened_scope"):
            reader.list_mainline_execution_events(control_plane_key=notification.P3_CONTROL_PLANE_KEY, task_key=task)
    assert calls == []
    reader.list_mainline_execution_events(control_plane_key=notification.P3_CONTROL_PLANE_KEY,
                                           task_key=p3.issue_task_keys("2026102")["refit"])
    assert len(calls) == 1
    with pytest.raises(learning.DecisionIntegrityError, match="execution_outside_scope"):
        reader.list_mainline_artifacts(control_plane_key=notification.P3_CONTROL_PLANE_KEY, execution_id="sealed")


def test_immutable_store_retries_and_corruption_fail_closed(tmp_path, record):
    path = learning.write_immutable(tmp_path, record)
    assert learning.write_immutable(tmp_path, record) == path
    assert json.loads(path.read_text()) == record
    path.write_text("corrupted")
    with pytest.raises(learning.DecisionIntegrityError, match="immutable_output_conflict"):
        learning.write_immutable(tmp_path, record)
