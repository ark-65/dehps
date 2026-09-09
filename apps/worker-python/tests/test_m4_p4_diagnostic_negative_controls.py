from __future__ import annotations

import importlib.util

import numpy as np
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    diagnostic_negative_controls as diagnostic,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_execution import (
    score_issue,
)


def _historical_inputs() -> tuple[dict, dict]:
    records = []
    for ordinal in range(diagnostic.HISTORICAL_ISSUE_COUNT):
        start = ordinal % diagnostic.NUMBER_COUNT
        red = sorted(
            ((start + offset) % diagnostic.NUMBER_COUNT) + 1
            for offset in range(diagnostic.DRAW_SIZE)
        )
        records.append(
            {
                "issue": f"S{ordinal + 1:04d}",
                "draw_date": f"2000-01-{(ordinal % 28) + 1:02d}",
                "red_numbers": red,
            }
        )
    folds = [
        {
            "fold_index": index,
            "fold_digest": f"{index + 1:064x}",
            "test_ordinal": diagnostic.INITIAL_TRAINING_ISSUES + index + 1,
            "training_end_ordinal": diagnostic.INITIAL_TRAINING_ISSUES + index,
            "test_issue": records[
                diagnostic.INITIAL_TRAINING_ISSUES + index
            ]["issue"],
        }
        for index in range(diagnostic.FOLD_COUNT)
    ]
    snapshot = {
        "artifact_digest": diagnostic.HISTORICAL_DATASET_SNAPSHOT_DIGEST,
        "dataset_content_digest": diagnostic.HISTORICAL_DATASET_CONTENT_DIGEST,
        "history_snapshot": {"records": records},
    }
    manifest = {
        "artifact_digest": diagnostic.HISTORICAL_FOLD_MANIFEST_DIGEST,
        "folds": folds,
    }
    return snapshot, manifest


def _mean_for_fixture(snapshot: dict, manifest: dict) -> float:
    records = snapshot["history_snapshot"]["records"]
    counts = np.zeros(diagnostic.NUMBER_COUNT, dtype=np.int64)
    for record in records[: diagnostic.INITIAL_TRAINING_ISSUES]:
        counts[np.asarray(record["red_numbers"], dtype=np.int64) - 1] += 1
    scores = []
    for fold in manifest["folds"]:
        record = records[fold["test_ordinal"] - 1]
        score, _ = score_issue(
            counts=counts,
            training_issue_count=fold["training_end_ordinal"],
            red_numbers=record["red_numbers"],
        )
        scores.append(score)
        counts[np.asarray(record["red_numbers"], dtype=np.int64) - 1] += 1
    return float(np.mean(np.asarray(scores, dtype=np.float64)))


def _preregistration() -> dict:
    return diagnostic._artifact(
        artifact_type=diagnostic.PREREGISTRATION_ARTIFACT_TYPE,
        schema_version=diagnostic.PREREGISTRATION_SCHEMA,
        domain=diagnostic.PREREGISTRATION_DOMAIN,
        body={
            "status": "FROZEN_RESULT_BLIND",
            "seed_manifest": diagnostic._seed_manifest(),
        },
        parent_digests=("1" * 64,),
    )


def _execution_artifact(
    *,
    anomalies: list[str] | None = None,
    equivariance: bool = True,
    future: bool = True,
    baseline: bool = True,
    complete: bool = True,
) -> dict:
    return diagnostic._artifact(
        artifact_type=diagnostic.EXECUTION_ARTIFACT_TYPE,
        schema_version=diagnostic.EXECUTION_SCHEMA,
        domain=diagnostic.EXECUTION_DOMAIN,
        body={
            "preregistration_artifact_digest": _preregistration()[
                "artifact_digest"
            ],
            "control_order": list(diagnostic.CONTROL_IDS),
            "required_controls_complete": complete,
            "resampling_precision_complete": complete,
            "signal_destruction_anomalies": anomalies or [],
            "predictive_p3_folds": 0,
            "controls": {
                "DATE_PERMUTATION": {},
                "TARGET_LABEL_PERMUTATION": {},
                "NUMBER_RELABELING": {"equivariance_passed": equivariance},
                "FEATURE_TIME_SHIFT": {"future_sentinel_passed": future},
                "RANDOM_FEATURE_SENTINEL": {},
                "BASELINE_IMPLEMENTATION_SENTINEL": {
                    "independent_implementation_passed": baseline
                },
            },
        },
        parent_digests=("2" * 64,),
    )


def test_source_contract_and_governance_are_frozen(tmp_path) -> None:
    from archival_source import original_source
    archive = original_source(tmp_path, contract_path=diagnostic.SOURCE_CONTRACT_PATH,
                              commit="b3b905aa3cbf9ee39f88d07f559d9159c4b58a42")
    source = diagnostic.load_source_contract(root_dir=archive)
    assert source["artifact_digest"]
    assert source["frozen_program"]["control_ids"] == list(
        diagnostic.CONTROL_IDS
    )
    assert source["frozen_program"]["eligible_for_p5"] is False
    assert source["limits"]["pass_to_p4_emitted"] is False


def test_p3_closure_and_preregistration_preserve_inconclusive_state() -> None:
    historical = {
        "artifact_digest": diagnostic.HISTORICAL_INFERENCE_DIGEST,
        "formal_historical_folds_executed": diagnostic.FOLD_COUNT,
        "mde_bits_per_issue": diagnostic.CURRENT_MDE,
        "primary_threshold_bits_per_issue": diagnostic.PRACTICAL_THRESHOLD,
        "equivalence_power_at_zero": diagnostic.CURRENT_POWER,
        "observed_mean_bits_per_issue": diagnostic.ORIGINAL_MEAN,
    }
    deeper = {
        "artifact_digest": diagnostic.DEEPER_VALIDATION_DECISION_DIGEST,
        "body": {"deeper_validation_decision": "FORWARD_EVIDENCE_REQUIRED"},
    }
    old_closure = {
        "artifact_digest": diagnostic.PREDICTIVE_P3_CLOSURE_DIGEST,
        "body": {
            "predictive_p3_status": (
                "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"
            )
        },
    }
    closure = diagnostic.build_p3_closure_artifact(
        historical_inference=historical,
        deeper_decision=deeper,
        predictive_p3_closure=old_closure,
        source_contract_digest="3" * 64,
    )
    body = closure["body"]
    assert body["p3_scientific_disposition"] == "INCONCLUSIVE_DUE_TO_POWER"
    assert body["pass_to_p4"] == "NOT_EMITTED"
    assert body["formal_p4"] == "DEPENDENCY_WAIT"


def test_six_control_execution_uses_only_frozen_unique_folds(monkeypatch) -> None:
    snapshot, manifest = _historical_inputs()
    monkeypatch.setattr(diagnostic, "REPEAT_COUNT", 2)
    monkeypatch.setattr(diagnostic, "BOOTSTRAP_REPLICATES", 16)
    monkeypatch.setattr(diagnostic, "ORIGINAL_MEAN", _mean_for_fixture(snapshot, manifest))
    artifact = diagnostic.execute_negative_controls(
        preregistration_artifact=_preregistration(),
        dataset_snapshot=snapshot,
        fold_manifest=manifest,
    )
    body = artifact["body"]
    assert list(body["controls"]) == list(diagnostic.CONTROL_IDS)
    assert body["diagnostic_unique_fold_count"] == diagnostic.FOLD_COUNT
    assert body["independent_information_count"] == diagnostic.FOLD_COUNT
    assert body["randomized_repeats_are_independent_information"] is False
    assert body["controls"]["NUMBER_RELABELING"]["equivariance_passed"]
    assert body["controls"]["FEATURE_TIME_SHIFT"]["future_values_read"] == 0
    assert (
        body["controls"]["FEATURE_TIME_SHIFT"]["future_legal_prediction_outputs"]
        == 0
    )
    assert body["controls"]["BASELINE_IMPLEMENTATION_SENTINEL"][
        "independent_implementation_passed"
    ]
    assert body["predictive_p3_folds"] == 0
    assert body["model_training_started"] is False


def test_decision_priority_is_frozen() -> None:
    preregistration = _preregistration()
    execution = _execution_artifact(anomalies=["DATE_PERMUTATION"])
    evidence = diagnostic.compile_diagnostic_evidence(
        preregistration_artifact=preregistration,
        execution_artifact=execution,
    )
    decision = diagnostic.build_diagnostic_decision(evidence_artifact=evidence)
    assert (
        decision["body"]["diagnostic_p4_decision"]
        == "LEAKAGE_OR_EVALUATOR_ARTIFACT_DETECTED"
    )
    assert decision["body"]["pass_to_p4"] == "NOT_EMITTED"
    assert decision["body"]["p5"] == "NOT_AUTHORIZED"


def test_registered_replay_does_not_rerun_workload() -> None:
    preregistration = _preregistration()
    execution = _execution_artifact()
    evidence = diagnostic.compile_diagnostic_evidence(
        preregistration_artifact=preregistration,
        execution_artifact=execution,
    )
    decision = diagnostic.build_diagnostic_decision(evidence_artifact=evidence)
    replay = diagnostic.build_decision_replay(
        decision_artifact=decision,
        decision_registration_digest="4" * 64,
    )
    assert replay["body"]["replay_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert replay["body"]["workload_rerun"] is False
    assert replay["body"]["formal_p4"] == "DEPENDENCY_WAIT"
    assert replay["body"]["model_training"] == "NOT_STARTED"


def test_manifest_builder_declares_six_tasks_and_separate_goal() -> None:
    path = (
        ROOT_DIR
        / "apps/worker-python/scripts/build_m4_p4_diagnostic_negative_controls_manifest.py"
    )
    spec = importlib.util.spec_from_file_location("diagnostic_builder_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.GOAL_KEY == "M4_P4_DIAGNOSTIC_NEGATIVE_CONTROLS"
    assert len(module.NEW_TASK_KEYS) == 6
    assert module.FORMAL_P4_TASK_KEY == "m4-p4-negative-controls-and-robustness"
