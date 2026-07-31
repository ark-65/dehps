from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from math import log2
from pathlib import Path
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import (
    preregistration_digest,
)
from dehps.research_os.information_theory.metrics import evaluate_issue
from dehps.research_os.information_theory.probes import prepare_probe
from dehps.research_os.information_theory.probes.runtime_cache import (
    ExactProbeRuntimeCache,
)
from dehps.research_os.information_theory.resampling import (
    ResamplingKernelManifest,
    load_resampling_manifest,
)
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)
from dehps.research_os.information_theory.walk_forward import (
    expanding_outer_folds,
    load_harness_manifest,
    restrict_to_training_history,
    validate_outer_fold,
)
from dehps.research_os.information_theory.walk_forward.contracts import (
    THEORETICAL_PROBABILITY,
    HarnessManifest,
)
from dehps.research_os.information_theory.walk_forward.leakage import (
    guard_feature_timestamp,
    guard_number_event_rows,
    guard_train_test_overlap,
)

from .contracts import (
    MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    METRIC_KERNEL_DIGEST,
    PREREGISTRATION_DIGEST,
    RESAMPLING_KERNEL_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST,
    MeasurementValidationContractError,
    MeasurementValidationManifest,
)
from .dataset import generate_evaluation_dataset
from .feature_cache import StrictPriorFeatureCache
from .journal import StrictPriorCheckpointJournal
from .schedule import AnalysisReplicate
from .statistics import (
    block_permutation_statistics,
    moving_block_bootstrap_statistics,
    primary_inference,
    seed_set_digest,
)

PROBES = (
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)
GATE_PROBE = "REGULARIZED_LOGISTIC_REGRESSION"
PROBABILITY_EPSILON = 0.000001


def vectorized_p2_pe1(
    probabilities: np.ndarray,
    targets: np.ndarray,
) -> np.ndarray:
    probability = np.asarray(probabilities, dtype=np.float64)
    target = np.asarray(targets, dtype=np.int8)
    if (
        probability.ndim != 2
        or probability.shape != target.shape
        or probability.shape[1] != 33
        or not np.isfinite(probability).all()
        or not np.isin(target, (0, 1)).all()
        or not np.all(target.sum(axis=1) == 6)
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_metric_input_invalid",
            "formal metric arrays must be aligned N x 33 predictions and legal targets",
        )
    clipped = np.clip(
        probability,
        PROBABILITY_EPSILON,
        1.0 - PROBABILITY_EPSILON,
    )
    probe_loss = -np.sum(
        target * np.log2(clipped) + (1 - target) * np.log2(1.0 - clipped),
        axis=1,
    )
    baseline_loss = -(
        6 * log2(THEORETICAL_PROBABILITY) + 27 * log2(1.0 - THEORETICAL_PROBABILITY)
    )
    return baseline_loss - probe_loss


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementValidationContractError(
            "measurement_validation_reference_invalid",
            f"{path}: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise MeasurementValidationContractError(
            "measurement_validation_reference_invalid",
            f"{path} is not an object",
        )
    return value


@dataclass(frozen=True)
class ReferenceInputs:
    preregistration: Mapping[str, Any]
    walk_forward_harness: HarnessManifest
    resampling: ResamplingKernelManifest
    truth_by_scenario: Mapping[str, Mapping[str, Any]]
    git_commit: str


class ReferenceReplicateEvaluator:
    """Literal frozen P2.1-P2.5 implementation used as the equivalence oracle."""

    def __init__(
        self,
        *,
        manifest: MeasurementValidationManifest,
        synthetic: SyntheticRunManifest,
        inputs: ReferenceInputs,
        output_dir: Path,
    ) -> None:
        self.manifest = manifest
        self.synthetic = synthetic
        self.inputs = inputs
        self.output_dir = output_dir
        if manifest.artifact_digest != MEASUREMENT_VALIDATION_MANIFEST_DIGEST:
            raise MeasurementValidationContractError(
                "measurement_validation_manifest_digest_mismatch",
                "reference evaluator requires the frozen P2.6 manifest",
            )
        if inputs.resampling.artifact_digest != RESAMPLING_KERNEL_DIGEST:
            raise MeasurementValidationContractError(
                "measurement_validation_resampling_invalid",
                "reference evaluator requires the accepted P2.5 kernel",
            )
        if inputs.walk_forward_harness.artifact_digest != WALK_FORWARD_HARNESS_DIGEST:
            raise MeasurementValidationContractError(
                "measurement_validation_walk_forward_invalid",
                "reference evaluator requires the accepted P2.3 harness",
            )
        if (
            inputs.preregistration.get("artifact_digest") != PREREGISTRATION_DIGEST
            or preregistration_digest(inputs.preregistration) != PREREGISTRATION_DIGEST
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_preregistration_invalid",
                "reference evaluator requires preregistration v1.0.3",
            )
        if tuple(manifest.payload["workload"]["probe_allowlist"]) != PROBES:
            raise MeasurementValidationContractError(
                "measurement_validation_probe_output_incomplete",
                "frozen four-probe order changed",
            )

    @classmethod
    def from_paths(
        cls,
        *,
        manifest: MeasurementValidationManifest,
        synthetic: SyntheticRunManifest,
        preregistration_path: Path,
        walk_forward_harness_path: Path,
        resampling_path: Path,
        truth_by_scenario: Mapping[str, Mapping[str, Any]],
        git_commit: str,
        output_dir: Path,
    ) -> ReferenceReplicateEvaluator:
        return cls(
            manifest=manifest,
            synthetic=synthetic,
            inputs=ReferenceInputs(
                preregistration=_load_json(preregistration_path),
                walk_forward_harness=load_harness_manifest(walk_forward_harness_path),
                resampling=load_resampling_manifest(resampling_path),
                truth_by_scenario=truth_by_scenario,
                git_commit=git_commit,
            ),
            output_dir=output_dir,
        )

    def evaluate(self, replicate: AnalysisReplicate) -> Mapping[str, Any]:
        truth = self.inputs.truth_by_scenario.get(replicate.cell.scenario_id)
        dataset = generate_evaluation_dataset(
            replicate,
            synthetic=self.synthetic,
            truth_artifact=truth,
        )
        folds = expanding_outer_folds(dataset)
        if len(folds) != replicate.cell.outer_issue_count:
            raise MeasurementValidationContractError(
                "measurement_validation_outer_fold_count_mismatch",
                "P2.3 expanding split did not produce the frozen outer count",
            )
        configs = self.inputs.preregistration["probe_models"]["hyperparameters"]
        checkpoint_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        settlement_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        state_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        issue_gains: dict[str, list[float]] = {probe: [] for probe in PROBES}
        gate_probabilities: list[tuple[float, ...]] = []
        ordered_targets: list[tuple[int, ...]] = []
        feature_cache = StrictPriorFeatureCache(dataset)
        checkpoint_journal = StrictPriorCheckpointJournal(
            output_dir=self.output_dir,
            replicate=replicate,
        )

        for fold_index, fold in enumerate(folds):
            probe_runtime_cache = ExactProbeRuntimeCache()
            validate_outer_fold(
                fold,
                minimum_training_issues=dataset.minimum_training_length,
                dataset_issue_count=dataset.issue_count,
            )
            guard_train_test_overlap(fold)
            training = restrict_to_training_history(
                dataset,
                available_through_issue=fold.train_issues[-1],
            )
            feature_cache.reveal_training_history(
                training,
                through_issue=fold.train_issues[-1],
            )
            train_view = feature_cache.build_train_feature_view(
                training,
                fold.train_issues,
            )
            blind = feature_cache.build_blind_test_feature_view(
                target_issue=fold.test_issue,
            )
            guard_feature_timestamp(blind)
            guard_number_event_rows(
                issue_ids=train_view.issue_ids,
                red_numbers=train_view.red_numbers,
            )

            predictions: dict[str, tuple[float, ...]] = {}
            for probe_id in PROBES:
                if probe_id == "EMPIRICAL_BASELINE":
                    config = {}
                elif probe_id == "REGULARIZED_LOGISTIC_REGRESSION":
                    config = self.inputs.walk_forward_harness.probe(probe_id)
                else:
                    config = configs[probe_id]
                prepared = prepare_probe(
                    probe_id=probe_id,
                    dataset=training,
                    train_view=train_view,
                    probe_config=config,
                    outer_test_issue=fold.test_issue,
                    train_view_builder=(feature_cache.build_train_feature_view),
                    runtime_cache=probe_runtime_cache,
                )
                probability = prepared.predict(blind)
                checkpoint_identity = {
                    "dataset_digest": dataset.artifact_digest,
                    "scale_id": replicate.cell.scale_id,
                    "scenario_id": replicate.cell.scenario_id,
                    "replicate_index": replicate.replicate_index,
                    "probe_id": probe_id,
                    "train_start_issue": fold.train_issues[0],
                    "train_end_issue": fold.train_issues[-1],
                    "test_issue": fold.test_issue,
                    "probe_state_digest": prepared.state.state_digest,
                    "probabilities": list(probability),
                    "probability_order": "red_numbers_1_to_33",
                    "target_access": "forbidden_before_this_checkpoint",
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                    "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
                    "git_commit": self.inputs.git_commit,
                }
                checkpoint_digest = canonical_digest(
                    checkpoint_identity,
                    domain="dehps.m4-p2.formal-prediction-checkpoint.v1",
                )
                checkpoint_digests[probe_id].append(checkpoint_digest)
                state_digests[probe_id].append(prepared.state.state_digest)
                predictions[probe_id] = probability

            checkpoint_journal.record(
                fold_index=fold_index,
                test_issue=fold.test_issue,
                checkpoint_digests={
                    probe_id: checkpoint_digests[probe_id][-1] for probe_id in PROBES
                },
            )
            # First target access is deliberately below all four immutable
            # prediction identities and their persisted journal entry.
            target = dataset.issue(fold.test_issue).target_vector
            ordered_targets.append(target)
            for probe_id in PROBES:
                metric = evaluate_issue(
                    issue_id=str(fold.test_issue),
                    cluster_id=str(fold.test_issue),
                    target_vector=target,
                    baseline_probability_vector=(THEORETICAL_PROBABILITY,) * 33,
                    probe_probability_vector=predictions[probe_id],
                )
                settlement_identity = {
                    "prediction_checkpoint_digest": checkpoint_digests[probe_id][-1],
                    "target_digest": canonical_digest(
                        list(target),
                        domain="dehps.m4-p2.formal-fold-target.v1",
                    ),
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                    "PE1_bits_per_issue": (
                        metric.observed_log_loss_gain_bits_per_issue
                    ),
                }
                settlement_digests[probe_id].append(
                    canonical_digest(
                        settlement_identity,
                        domain="dehps.m4-p2.formal-fold-settlement.v1",
                    )
                )
                issue_gains[probe_id].append(
                    metric.observed_log_loss_gain_bits_per_issue
                )
            gate_probabilities.append(predictions[GATE_PROBE])

        probe_run_digests = {
            probe_id: canonical_digest(
                {
                    "probe_id": probe_id,
                    "dataset_digest": dataset.artifact_digest,
                    "checkpoint_digests": checkpoint_digests[probe_id],
                    "settlement_digests": settlement_digests[probe_id],
                    "probe_state_digests": state_digests[probe_id],
                    "PE1_issue_statistics": issue_gains[probe_id],
                    "outer_fold_count": len(folds),
                    "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                },
                domain="dehps.m4-p2.formal-probe-run.v1",
            )
            for probe_id in PROBES
        }
        ordered_checkpoint_digest = canonical_digest(
            [
                checkpoint_digests[probe][index]
                for index in range(len(folds))
                for probe in PROBES
            ],
            domain="dehps.m4-p2.ordered-formal-checkpoints.v1",
        )
        ordered_settlement_digest = canonical_digest(
            [
                settlement_digests[probe][index]
                for index in range(len(folds))
                for probe in PROBES
            ],
            domain="dehps.m4-p2.ordered-formal-settlements.v1",
        )

        pe1_values = tuple(issue_gains[GATE_PROBE])
        bootstrap, bootstrap_seeds = moving_block_bootstrap_statistics(
            pe1_values,
            manifest=self.inputs.resampling,
            scenario_id=replicate.cell.scenario_id,
            parent_run_digest=replicate.artifact_digest,
            replicate_count=self.manifest.bootstrap_replicates,
        )
        probability_matrix = np.asarray(gate_probabilities, dtype=np.float64)
        target_matrix = np.asarray(ordered_targets, dtype=np.int8)

        def statistic_for_indices(indices: tuple[int, ...]) -> float:
            permuted = target_matrix[np.asarray(indices, dtype=np.int64)]
            return float(vectorized_p2_pe1(probability_matrix, permuted).mean())

        permutation, permutation_seeds = block_permutation_statistics(
            issue_count=len(folds),
            statistic_for_indices=statistic_for_indices,
            manifest=self.inputs.resampling,
            scenario_id=replicate.cell.scenario_id,
            parent_run_digest=replicate.artifact_digest,
            replicate_count=self.manifest.permutation_replicates,
        )
        inference = primary_inference(
            pe1_issue_statistics=pe1_values,
            permutation_null_statistics=permutation,
            bootstrap_statistics=bootstrap,
        )
        truth_bits = (
            0.0
            if truth is None
            else float(truth["joint_draw_information_bits_per_issue"])
        )
        journal_digest, journal_count = checkpoint_journal.finalize(
            expected_fold_count=len(folds)
        )
        is_negative_control = replicate.cell.scenario_id == "NULL_UNIFORM"
        return {
            **replicate.to_dict(),
            "status": "COMPLETE",
            "measurement_validation_manifest_digest": (self.manifest.artifact_digest),
            "dataset_digest": dataset.artifact_digest,
            "truth_artifact_digest": dataset.raw_payload["truth_artifact_digest"],
            "truth_bits_per_issue": truth_bits,
            "negative_control_id": (
                "NC6_SYNTHETIC_NULL" if is_negative_control else None
            ),
            "negative_control_replicate_index": (
                replicate.replicate_index if is_negative_control else None
            ),
            "probe_run_digests": probe_run_digests,
            "ordered_outer_checkpoint_digest": ordered_checkpoint_digest,
            "ordered_settlement_digest": ordered_settlement_digest,
            "checkpoint_journal_digest": journal_digest,
            "checkpoint_journal_entry_count": journal_count,
            "checkpoint_journal_path": str(
                checkpoint_journal.path.relative_to(self.output_dir)
            ),
            "bootstrap_seed_set_digest": seed_set_digest(
                bootstrap_seeds,
                method="bootstrap",
            ),
            "permutation_seed_set_digest": seed_set_digest(
                permutation_seeds,
                method="permutation",
            ),
            "bootstrap_replicate_count": len(bootstrap),
            "permutation_replicate_count": len(permutation),
            **inference,
            "leakage_status": "PASS",
            "actual_outer_fold_count": len(folds),
            "number_probability_predictions": len(folds) * 33 * len(PROBES),
            "gate_probe": GATE_PROBE,
            "metric_kernel_digest": METRIC_KERNEL_DIGEST,
            "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
            "resampling_kernel_digest": RESAMPLING_KERNEL_DIGEST,
            "git_commit": self.inputs.git_commit,
            "working_tree_clean": True,
            "real_history_used": False,
            "production_action": "none",
        }
