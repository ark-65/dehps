from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import numpy as np

from dehps.research_os.information_theory.measurement_validation import (
    PASS_FACT,
    REPAIR_FACT,
    StrictPriorFeatureCache,
    aggregate_cell,
    assign_shard,
    bca_interval,
    build_cells,
    build_mde_summary,
    build_replicate,
    evaluate_automatic_gate,
    execution_plan_summary,
    generate_evaluation_dataset,
    holm_adjust,
    load_measurement_validation_manifest,
    locate_truth_artifacts,
    primary_inference,
    run_parallel_execution,
    run_shard,
    type7_quantile,
    wilson_interval,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.resampling import (
    load_resampling_manifest,
)
from dehps.research_os.information_theory.measurement_validation.reference import (
    ReferenceReplicateEvaluator,
    vectorized_p2_pe1,
)
from dehps.research_os.information_theory.measurement_validation.journal import (
    StrictPriorCheckpointJournal,
    verify_checkpoint_journal,
)
from dehps.research_os.information_theory.metrics import (
    evaluate_issue,
    probe_log_loss_bits_per_issue_batch,
)
from dehps.research_os.information_theory.walk_forward.contracts import (
    THEORETICAL_PROBABILITY,
)
from dehps.research_os.information_theory.walk_forward import (
    build_blind_test_feature_view,
    build_train_feature_view,
    restrict_to_training_history,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-6-measurement-validation-v1.json"
)
SYNTHETIC_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)
RESAMPLING_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-5-resampling-kernel-v1.json"
)
EXECUTION_ID = "a" * 64
PROBES = (
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)
P24_EXECUTION_ID = (
    "772b5063f1a3578c7e8f8a2cd9f102357828608de8fbd80c2c1fb2c82b79afa2"
)
P24_TRUTH_SPECS = {
    "WEAK_SINGLE_NUMBER": (
        "23a41f005f369e762f26c728eb13a5fa4888b9c04590d6e0d2410506956c7e2f",
        "single_number_conditional_shift",
        0.0010000000558177125,
        0.014354376630335237,
    ),
    "WEAK_LOCAL_TEMPORAL": (
        "709133b116c40ba95d10018c94160786c554186b94a0fc9dfaeef539d30eb58e",
        "local_temporal_state",
        0.0010000000835004644,
        0.018614336848240355,
    ),
    "WEAK_PAIR": (
        "6c8a2c30941255e617205f4a59e594e4ac894dd8057accaa6b538026263654e2",
        "pair_conditional_signal",
        0.0009999999995979596,
        0.008577358338132095,
    ),
    "WEAK_MARGINAL_PRESERVING": (
        "a3516898188a0e8b22d0cd61f9a8b1412e4f14e80096f34a437ad720731cd179",
        "marginal_preserving_conditional_signal",
        0.0010000000066530295,
        0.03725493326779454,
    ),
    "MEDIUM_PRACTICAL_SINGLE_NUMBER": (
        "97e126b5ec61cb8bc8599f35754b3968fec037cc1349a419196238849eef87ab",
        "single_number_conditional_shift",
        0.010000000029762889,
        0.0452148758551839,
    ),
    "MEDIUM_PRACTICAL_LOCAL_TEMPORAL": (
        "0a04a7251b982c80af0c8944ecf96f6faa224ad408a2f92207c4fe5fbf603e06",
        "local_temporal_state",
        0.009999999955732669,
        0.05880238860839686,
    ),
    "MEDIUM_PRACTICAL_PAIR": (
        "dbc2f7a58f5b506fc911f6b9d1f27a4b3fb18215db961b50ea519baf3668b3be",
        "pair_conditional_signal",
        0.010000000029310811,
        0.02666319687397467,
    ),
    "MEDIUM_PRACTICAL_MARGINAL_PRESERVING": (
        "9623cdf111538f1883f1ed1b2b2f33ca852517744812e16e9f4f2fb4acf51f97",
        "marginal_preserving_conditional_signal",
        0.010000000043814683,
        0.11768773291248236,
    ),
    "STRONG_SINGLE_NUMBER": (
        "dee510d7ebee2e3a8248657f2c71c984250a842626d3c3e3e29e917ff5025320",
        "single_number_conditional_shift",
        0.04999999991203453,
        0.09924511509852887,
    ),
    "STRONG_LOCAL_TEMPORAL": (
        "025befa6028bb19f9cf79ea368a214f1228242ce6e05009845c6621332bc2537",
        "local_temporal_state",
        0.04999999998812052,
        0.1308722510001245,
    ),
    "STRONG_PAIR": (
        "1a5401cbe3acd347a0a617dc3b8b153db61b995f759e229cbab77e4a4f45e44c",
        "pair_conditional_signal",
        0.05000000003108555,
        0.05394322249372052,
    ),
    "STRONG_MARGINAL_PRESERVING": (
        "0ce5a4353051ab8dd6e033e33508f050274a5b0166f9169a4c90f0124f7a2e5d",
        "marginal_preserving_conditional_signal",
        0.0500000000670463,
        0.2619290994477633,
    ),
}


def _contract():
    return load_measurement_validation_manifest(CONTRACT_PATH)


def _synthetic():
    return load_synthetic_run_manifest(SYNTHETIC_PATH)


def _materialize_frozen_truths(root: Path) -> dict[str, dict]:
    resampling = load_resampling_manifest(RESAMPLING_PATH)
    assert tuple(
        spec[0] for spec in P24_TRUTH_SPECS.values()
    ) == resampling.truth_artifact_digests
    truth_root = (
        root
        / "runtime/research-os/mainline/tasks/"
        "m4-p2-injected-signal-calibration"
        / P24_EXECUTION_ID
        / "artifacts/truth"
    )
    for scenario_id, (
        digest,
        mechanism,
        truth_bits,
        parameter,
    ) in P24_TRUTH_SPECS.items():
        path = truth_root / digest / "truth.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "artifact_digest": digest,
                    "artifact_type": "injected_signal_truth",
                    "scenario_id": scenario_id,
                    "mechanism": mechanism,
                    "joint_draw_information_bits_per_issue": truth_bits,
                    "parameter_value": parameter,
                    "preregistration_digest": resampling.payload[
                        "preregistration_digest"
                    ],
                    "decision_policy_digest": resampling.payload[
                        "decision_policy_digest"
                    ],
                    "synthetic_manifest_digest": resampling.payload[
                        "synthetic_manifest_digest"
                    ],
                    "eligible_for_p2_5_input": True,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return locate_truth_artifacts(
        root,
        required_digests=resampling.truth_artifact_digests,
    )


def _replicate_payload(
    *,
    cell,
    replicate_index: int,
    positive: bool,
    pe2: float | None = None,
) -> dict:
    truth = cell.target_bits_per_issue
    estimate = truth if pe2 is None else pe2
    identity = build_replicate(
        cell=cell,
        replicate_index=replicate_index,
        parent_execution_id=EXECUTION_ID,
    )
    return {
        "artifact_digest": f"{replicate_index + 1:064x}",
        **cell.to_dict(),
        "replicate_index": replicate_index,
        "evaluation_dataset_seed_digest": (
            identity.evaluation_dataset_seed_digest
        ),
        "status": "COMPLETE",
        "truth_bits_per_issue": truth,
        "PE2": estimate,
        "positive_signal_decision": positive,
        "confidence_intervals": {
            "PE2": {
                "lower": truth - 0.001,
                "upper": truth + 0.001,
            }
        },
    }


def test_full_schedule_has_exact_frozen_workload_and_stable_child_seeds() -> None:
    manifest = _contract()
    synthetic = _synthetic()
    cells = build_cells(manifest, synthetic)
    assert len(cells) == 31
    assert sum(cell.outer_issue_count * 1000 for cell in cells) == 64_656_000
    assert sum(cell.scenario_id == "NULL_UNIFORM" for cell in cells) == 3

    child = build_replicate(
        cell=cells[0],
        replicate_index=42,
        parent_execution_id=EXECUTION_ID,
    )
    one = assign_shard(child, shard_count=7)
    two = assign_shard(child, shard_count=19)
    assert one.replicate.artifact_digest == two.replicate.artifact_digest
    assert (
        one.replicate.power_replicate_seed_digest
        == two.replicate.power_replicate_seed_digest
    )
    assert (
        one.replicate.evaluation_dataset_seed_digest
        == two.replicate.evaluation_dataset_seed_digest
    )


def test_execution_plan_materializes_all_31000_unique_identities() -> None:
    plan = execution_plan_summary(
        manifest=_contract(),
        synthetic=_synthetic(),
        parent_execution_id=EXECUTION_ID,
        shard_count=22,
    )
    assert plan["cell_count"] == 31
    assert plan["replicate_count"] == 31_000
    assert plan["outer_issue_predictions"] == 64_656_000
    assert sum(plan["replicate_count_by_shard"]) == 31_000
    assert max(plan["replicate_count_by_shard"]) - min(
        plan["replicate_count_by_shard"]
    ) < 150
    assert len(plan["artifact_digest"]) == 64
    assert len(plan["seed_set_digest"]) == 64


def test_evaluation_dataset_uses_separate_seed_domain_and_p24_truth(
    tmp_path: Path,
) -> None:
    cells = build_cells(_contract(), _synthetic())
    cell = next(
        item
        for item in cells
        if item.scale_id == "FORWARD_61"
        and item.scenario_id == "WEAK_SINGLE_NUMBER"
    )
    replicate = build_replicate(
        cell=cell,
        replicate_index=17,
        parent_execution_id=EXECUTION_ID,
    )
    truths = _materialize_frozen_truths(tmp_path)
    first = generate_evaluation_dataset(
        replicate,
        synthetic=_synthetic(),
        truth_artifact=truths[cell.scenario_id],
    )
    second = generate_evaluation_dataset(
        replicate,
        synthetic=_synthetic(),
        truth_artifact=truths[cell.scenario_id],
    )
    assert first.artifact_digest == second.artifact_digest
    assert first.raw_payload["draw_digest"] == second.raw_payload["draw_digest"]
    assert first.issue_count == 961
    assert first.outer_evaluation_length == 61
    assert first.raw_payload["evaluation_seed_domain"] == "M4_P2_EVALUATION_DATASET"
    assert first.raw_payload["calibration_seed_domain_used"] is False
    assert first.raw_payload["truth_artifact_digest"] == truths[cell.scenario_id][
        "artifact_digest"
    ]
    assert first.raw_payload["truth"][
        "joint_draw_information_bits_per_issue"
    ] == truths[cell.scenario_id]["joint_draw_information_bits_per_issue"]


def test_reference_evaluator_loads_all_frozen_p2_1_through_p2_5_inputs(
    tmp_path: Path,
) -> None:
    truths = _materialize_frozen_truths(tmp_path)
    evaluator = ReferenceReplicateEvaluator.from_paths(
        manifest=_contract(),
        synthetic=_synthetic(),
        preregistration_path=(
            ROOT
            / "configs/research-os/"
            "m4-information-theory-preregistration-v1.0.3.json"
        ),
        walk_forward_harness_path=(
            ROOT
            / "configs/research-os/"
            "m4-information-theory-walk-forward-harness-v1.json"
        ),
        resampling_path=RESAMPLING_PATH,
        truth_by_scenario=truths,
        git_commit="f" * 40,
        output_dir=tmp_path,
    )
    assert evaluator.manifest.artifact_digest == _contract().artifact_digest
    assert (
        evaluator.inputs.walk_forward_harness.artifact_digest
        == _contract().payload["upstream_identities"][
            "walk_forward_harness_digest"
        ]
    )


def test_strict_prior_feature_cache_is_digest_equivalent_without_future_access(
    tmp_path: Path,
) -> None:
    cell = next(
        item
        for item in build_cells(_contract(), _synthetic())
        if item.scale_id == "FORWARD_61"
        and item.scenario_id == "WEAK_SINGLE_NUMBER"
    )
    replicate = build_replicate(
        cell=cell,
        replicate_index=19,
        parent_execution_id=EXECUTION_ID,
    )
    truths = _materialize_frozen_truths(tmp_path)
    dataset = generate_evaluation_dataset(
        replicate,
        synthetic=_synthetic(),
        truth_artifact=truths[cell.scenario_id],
    )
    cache = StrictPriorFeatureCache(dataset)
    training_900 = restrict_to_training_history(
        dataset,
        available_through_issue=900,
    )
    cache.reveal_training_history(training_900, through_issue=900)
    issue_ids = tuple(range(1, 901))
    assert cache.build_train_feature_view(
        training_900,
        issue_ids,
    ) == build_train_feature_view(training_900, issue_ids)
    assert cache.build_blind_test_feature_view(
        target_issue=901,
    ) == build_blind_test_feature_view(dataset, target_issue=901)

    training_901 = restrict_to_training_history(
        dataset,
        available_through_issue=901,
    )
    cache.reveal_training_history(training_901, through_issue=901)
    validation_ids = tuple(range(701, 902))
    assert cache.build_train_feature_view(
        training_901,
        validation_ids,
    ) == build_train_feature_view(training_901, validation_ids)
    assert cache.build_blind_test_feature_view(
        target_issue=902,
    ) == build_blind_test_feature_view(dataset, target_issue=902)


def test_frozen_statistics_use_type7_holm_wilson_and_explicit_bca_fallback() -> None:
    assert type7_quantile([0.0, 10.0], 0.25) == pytest.approx(2.5)
    assert holm_adjust({"PE1": 0.01, "PE2": 0.04}) == {
        "PE1": 0.02,
        "PE2": 0.04,
    }
    lower, upper = wilson_interval(75, 1000)
    assert lower < 0.075 < upper
    assert upper < 0.1

    interval = bca_interval(
        observed=1.0,
        bootstrap_statistics=[1.0] * 2000,
        jackknife_statistics=[1.0] * 20,
    )
    assert interval["method"] == "two_sided_percentile"
    assert interval["fallback_used"] is True
    assert interval["fallback_reason"] == [
        "jackknife_acceleration_denominator_nonfinite_or_zero"
    ]


def test_vectorized_permutation_metric_is_numerically_equivalent_to_p22() -> None:
    generator = np.random.default_rng(81273)
    probabilities = generator.uniform(0.01, 0.8, size=(12, 33))
    targets = np.zeros((12, 33), dtype=np.int8)
    for row in targets:
        row[generator.choice(np.arange(33), 6, replace=False)] = 1
    vectorized = vectorized_p2_pe1(probabilities, targets)
    reference = [
        evaluate_issue(
            issue_id=str(index + 1),
            cluster_id=str(index + 1),
            target_vector=targets[index],
            baseline_probability_vector=(THEORETICAL_PROBABILITY,) * 33,
            probe_probability_vector=probabilities[index],
        ).observed_log_loss_gain_bits_per_issue
        for index in range(12)
    ]
    assert vectorized == pytest.approx(reference, abs=2e-14, rel=0.0)
    batch_losses = probe_log_loss_bits_per_issue_batch(
        target_vectors=targets,
        probe_probability_vectors=probabilities,
    )
    assert batch_losses == tuple(
        evaluate_issue(
            issue_id=str(index + 1),
            cluster_id=str(index + 1),
            target_vector=targets[index],
            baseline_probability_vector=(THEORETICAL_PROBABILITY,) * 33,
            probe_probability_vector=probabilities[index],
        ).probe_log_loss_bits_per_issue
        for index in range(12)
    )


def test_primary_inference_requires_both_holm_endpoints_and_positive_intervals() -> None:
    issue_values = [0.02 + (index % 7) * 0.0001 for index in range(61)]
    null = [-0.01 + index * 0.000005 for index in range(2000)]
    bootstrap = [0.018 + index * 0.000002 for index in range(2000)]
    result = primary_inference(
        pe1_issue_statistics=issue_values,
        permutation_null_statistics=null,
        bootstrap_statistics=bootstrap,
    )
    assert result["PE1"] > 0.0
    assert result["PE2"] > result["PE1"]
    assert result["Holm_adjusted_p_values"]["PE1"] <= 0.05
    assert result["Holm_adjusted_p_values"]["PE2"] <= 0.05
    assert result["positive_signal_decision"] is True


def test_checkpoint_journal_is_persisted_before_target_and_replayable(
    tmp_path: Path,
) -> None:
    cell = next(
        item
        for item in build_cells(_contract(), _synthetic())
        if item.scale_id == "FORWARD_61"
        and item.scenario_id == "NULL_UNIFORM"
    )
    replicate = build_replicate(
        cell=cell,
        replicate_index=3,
        parent_execution_id=EXECUTION_ID,
    )
    journal = StrictPriorCheckpointJournal(
        output_dir=tmp_path,
        replicate=replicate,
    )
    for fold_index in range(2):
        journal.record(
            fold_index=fold_index,
            test_issue=901 + fold_index,
            checkpoint_digests={
                probe: f"{index + fold_index + 1:064x}"
                for index, probe in enumerate(PROBES)
            },
        )
    digest, count = journal.finalize(expected_fold_count=2)
    assert count == 2
    verify_checkpoint_journal(
        output_dir=tmp_path,
        replicate=replicate,
        expected_digest=digest,
        expected_fold_count=2,
    )
    resumed = StrictPriorCheckpointJournal(
        output_dir=tmp_path,
        replicate=replicate,
    )
    resumed.record(
        fold_index=0,
        test_issue=901,
        checkpoint_digests={
            probe: f"{index + 1:064x}"
            for index, probe in enumerate(PROBES)
        },
    )


def test_cell_aggregate_is_local_and_enforces_all_1000_replicates() -> None:
    cell = next(
        item
        for item in build_cells(_contract(), _synthetic())
        if item.scale_id == "FORWARD_61"
        and item.scenario_id == "MEDIUM_PRACTICAL_SINGLE_NUMBER"
    )
    replicates = [
        _replicate_payload(
            cell=cell,
            replicate_index=index,
            positive=index < 800,
        )
        for index in range(1000)
    ]
    aggregate = aggregate_cell(replicates, manifest=_contract())
    assert aggregate["empirical_power"] == 0.8
    assert aggregate["practical_power_gate_pass"] is True
    assert aggregate["bias_bits_per_issue"] == pytest.approx(0.0)
    assert aggregate["PE2_coverage_rate"] == 1.0
    assert aggregate["coverage_gate_pass"] is False
    with pytest.raises(Exception, match="exactly 1000"):
        aggregate_cell(replicates[:-1], manifest=_contract())


def _aggregate_for_cell(cell, *, power: float = 0.96, coverage: float = 0.95) -> dict:
    null = cell.scenario_id == "NULL_UNIFORM"
    return {
        "artifact_digest": build_replicate(
            cell=cell,
            replicate_index=0,
            parent_execution_id=EXECUTION_ID,
        ).artifact_digest,
        **cell.to_dict(),
        "false_positive_rate": 0.04 if null else None,
        "empirical_power": None if null else power,
        "false_positive_point_gate_pass": True if null else None,
        "false_positive_wilson_gate_pass": True if null else None,
        "practical_power_gate_pass": (
            power >= 0.8 if cell.signal_strength == "MEDIUM_PRACTICAL" else None
        ),
        "strong_power_gate_pass": (
            power >= 0.95 if cell.signal_strength == "STRONG" else None
        ),
        "bias_gate_pass": True,
        "coverage_gate_pass": True,
        "rmse_finite_gate_pass": True,
        "PE2_coverage_rate": coverage,
    }


def test_mde_and_automatic_gate_never_average_across_cells() -> None:
    cells = build_cells(_contract(), _synthetic())
    aggregates = [_aggregate_for_cell(cell) for cell in cells]
    mde = build_mde_summary(aggregates)
    assert mde["decision_policy_mde_at_61_bits_per_issue"] == 0.001
    assert mde["interpolation_used"] is False

    completion = {
        "artifact_digest": "f" * 64,
        "replicate_count": 31_000,
        "duplicate_replicate_count": 0,
        "failed_replicate_count": 0,
        "negative_control_id": "NC6_SYNTHETIC_NULL",
        "negative_control_cell_count": 3,
        "negative_control_replicates_per_cell": 1000,
        "negative_control_replicate_count": 3000,
        "checkpoint_journal_count": 31_000,
        "checkpoint_journal_failure_count": 0,
        "bootstrap_seed_count": 31_000 * 2000,
        "permutation_seed_count": 31_000 * 2000,
        "incomplete_seed_set_count": 0,
        "leakage_failure_count": 0,
    }
    gate = evaluate_automatic_gate(
        manifest=_contract(),
        completion=completion,
        aggregates=aggregates,
        deterministic_replay_passed=True,
    )
    assert gate["decision"] == "PASS_TO_P3"
    assert gate["decision_fact"] == PASS_FACT

    failing = deepcopy(aggregates)
    target = next(
        item
        for item in failing
        if item["scale_id"] == "FORWARD_61"
        and item["scenario_id"] == "MEDIUM_PRACTICAL_PAIR"
    )
    target["empirical_power"] = 0.799
    target["practical_power_gate_pass"] = False
    repair = evaluate_automatic_gate(
        manifest=_contract(),
        completion=completion,
        aggregates=failing,
        deterministic_replay_passed=True,
    )
    assert repair["decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert repair["decision_fact"] == REPAIR_FACT
    assert repair["P3_reachable"] is False


class _FakeEvaluator:
    def evaluate(self, replicate):
        truth = replicate.cell.target_bits_per_issue
        return {
            **replicate.to_dict(),
            "status": "COMPLETE",
            "dataset_digest": "1" * 64,
            "truth_artifact_digest": "2" * 64,
            "probe_run_digests": {
                probe: f"{index + 3:064x}"
                for index, probe in enumerate(PROBES)
            },
            "ordered_outer_checkpoint_digest": "7" * 64,
            "ordered_settlement_digest": "8" * 64,
            "checkpoint_journal_digest": "b" * 64,
            "checkpoint_journal_entry_count": (
                replicate.cell.outer_issue_count
            ),
            "checkpoint_journal_path": (
                "checkpoint-journals/"
                f"{replicate.cell.scale_id}/"
                f"{replicate.cell.scenario_id}/"
                f"{replicate.replicate_index:04d}-"
                f"{replicate.artifact_digest}.jsonl"
            ),
            "bootstrap_seed_set_digest": "9" * 64,
            "permutation_seed_set_digest": "a" * 64,
            "bootstrap_replicate_count": 2000,
            "permutation_replicate_count": 2000,
            "PE1": truth,
            "PE2": truth,
            "truth_bits_per_issue": truth,
            "negative_control_id": (
                "NC6_SYNTHETIC_NULL"
                if replicate.cell.scenario_id == "NULL_UNIFORM"
                else None
            ),
            "negative_control_replicate_index": (
                replicate.replicate_index
                if replicate.cell.scenario_id == "NULL_UNIFORM"
                else None
            ),
            "confidence_intervals": {
                "PE1": {"lower": truth - 0.001, "upper": truth + 0.001},
                "PE2": {"lower": truth - 0.001, "upper": truth + 0.001},
            },
            "raw_p_values": {"PE1": 0.01, "PE2": 0.01},
            "Holm_adjusted_p_values": {"PE1": 0.02, "PE2": 0.02},
            "positive_signal_decision": truth > 0.0,
            "leakage_status": "PASS",
        }


def test_shard_resume_reuses_immutable_replicate_and_child_seed(tmp_path: Path) -> None:
    first = run_shard(
        manifest=_contract(),
        synthetic=_synthetic(),
        parent_execution_id=EXECUTION_ID,
        output_dir=tmp_path,
        shard_index=0,
        shard_count=1,
        evaluator=_FakeEvaluator(),
        stop_after=1,
    )
    assert first.completed_replicates == 1
    second = run_shard(
        manifest=_contract(),
        synthetic=_synthetic(),
        parent_execution_id=EXECUTION_ID,
        output_dir=tmp_path,
        shard_index=0,
        shard_count=1,
        evaluator=_FakeEvaluator(),
        stop_after=1,
    )
    assert second.reused_replicates >= 1


def test_parallel_coordinator_materializes_plan_and_projects_resumable_progress(
    tmp_path: Path,
) -> None:
    progress = tmp_path / "progress.json"
    result = run_parallel_execution(
        manifest=_contract(),
        synthetic=_synthetic(),
        parent_execution_id=EXECUTION_ID,
        output_dir=tmp_path / "execution",
        evaluator=_FakeEvaluator(),
        worker_count=2,
        progress_projection_path=progress,
        stop_after_new_replicates=2,
    )
    projected = json.loads(progress.read_text(encoding="utf-8"))
    assert result.status == "INTERRUPTED"
    assert result.completed_replicates == 2
    assert result.execution_plan["replicate_count"] == 31_000
    assert projected["status"] == "INTERRUPTED"
    assert projected["completed_replicates"] == 2
    assert projected["result_selection_used"] is False
