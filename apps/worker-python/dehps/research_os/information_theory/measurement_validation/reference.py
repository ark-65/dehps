from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from math import log2
from pathlib import Path
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import (
    preregistration_digest,
)
from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    RuntimeAuditObserver,
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
from .journal import SettledFoldResumeJournal, StrictPriorCheckpointJournal
from .periodic_refit import LEARNED_PROBES, PeriodicRefitContract
from .schedule import AnalysisReplicate
from .statistics import (
    block_permutation_statistics,
    block_permutation_statistics_exact_runtime,
    moving_block_bootstrap_statistics,
    moving_block_bootstrap_statistics_exact_runtime,
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


def _prediction_checkpoint_digest(
    *,
    dataset_digest: str,
    replicate: AnalysisReplicate,
    probe_id: str,
    train_start_issue: int,
    train_end_issue: int,
    test_issue: int,
    probe_state_digest: str,
    probability: tuple[float, ...],
    git_commit: str,
) -> str:
    return canonical_digest(
        {
            "dataset_digest": dataset_digest,
            "scale_id": replicate.cell.scale_id,
            "scenario_id": replicate.cell.scenario_id,
            "replicate_index": replicate.replicate_index,
            "probe_id": probe_id,
            "train_start_issue": train_start_issue,
            "train_end_issue": train_end_issue,
            "test_issue": test_issue,
            "probe_state_digest": probe_state_digest,
            "probabilities": list(probability),
            "probability_order": "red_numbers_1_to_33",
            "target_access": "forbidden_before_this_checkpoint",
            "metric_kernel_digest": METRIC_KERNEL_DIGEST,
            "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
            "git_commit": git_commit,
        },
        domain="dehps.m4-p2.formal-prediction-checkpoint.v1",
    )


def _settle_prediction(
    *,
    checkpoint_digest: str,
    test_issue: int,
    target: tuple[int, ...],
    probability: tuple[float, ...],
) -> tuple[str, float, Any]:
    metric = evaluate_issue(
        issue_id=str(test_issue),
        cluster_id=str(test_issue),
        target_vector=target,
        baseline_probability_vector=(THEORETICAL_PROBABILITY,) * 33,
        probe_probability_vector=probability,
    )
    gain = metric.observed_log_loss_gain_bits_per_issue
    settlement_digest = canonical_digest(
        {
            "prediction_checkpoint_digest": checkpoint_digest,
            "target_digest": canonical_digest(
                list(target),
                domain="dehps.m4-p2.formal-fold-target.v1",
            ),
            "metric_kernel_digest": METRIC_KERNEL_DIGEST,
            "PE1_bits_per_issue": gain,
        },
        domain="dehps.m4-p2.formal-fold-settlement.v1",
    )
    return settlement_digest, gain, metric


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


def prepare_vectorized_p2_pe1_permutation_statistic(
    probabilities: np.ndarray,
    targets: np.ndarray,
) -> Callable[[Sequence[int]], float]:
    """Precompute invariant log terms while preserving the frozen row reduction."""

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
    positive_log2 = np.log2(clipped)
    negative_log2 = np.log2(1.0 - clipped)
    baseline_loss = -(
        6 * log2(THEORETICAL_PROBABILITY) + 27 * log2(1.0 - THEORETICAL_PROBABILITY)
    )

    def statistic_for_indices(indices: Sequence[int]) -> float:
        permuted = target[np.asarray(indices, dtype=np.int64)]
        probe_loss = -np.sum(
            permuted * positive_log2 + (1 - permuted) * negative_log2,
            axis=1,
        )
        return float((baseline_loss - probe_loss).mean())

    return statistic_for_indices


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
        periodic_refit_contract: PeriodicRefitContract | None = None,
        audit_observer: RuntimeAuditObserver | None = None,
        trace_records: list[dict[str, Any]] | None = None,
    ) -> None:
        self.manifest = manifest
        self.synthetic = synthetic
        self.inputs = inputs
        self.output_dir = output_dir
        self.periodic_refit_contract = periodic_refit_contract
        self.audit_observer = audit_observer or RuntimeAuditObserver(enabled=False)
        self.trace_records = trace_records
        if (
            manifest.artifact_digest != MEASUREMENT_VALIDATION_MANIFEST_DIGEST
            and manifest.payload.get("phase") != "M4-P2.6.1"
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_manifest_digest_mismatch",
                "reference evaluator requires a frozen P2.6 manifest",
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
        periodic_refit_contract: PeriodicRefitContract | None = None,
        audit_observer: RuntimeAuditObserver | None = None,
        trace_records: list[dict[str, Any]] | None = None,
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
            periodic_refit_contract=periodic_refit_contract,
            audit_observer=audit_observer,
            trace_records=trace_records,
        )

    def evaluate(self, replicate: AnalysisReplicate) -> Mapping[str, Any]:
        repaired = self.manifest.payload.get("phase") == "M4-P2.6.1"
        truth = self.inputs.truth_by_scenario.get(replicate.cell.scenario_id)
        with self.audit_observer.phase("dataset_generation"):
            dataset = generate_evaluation_dataset(
                replicate,
                synthetic=self.synthetic,
                truth_artifact=truth,
                expose_prior_state=repaired,
            )
        with self.audit_observer.phase("fold_construction"):
            folds = expanding_outer_folds(dataset)
        if len(folds) != replicate.cell.outer_issue_count:
            raise MeasurementValidationContractError(
                "measurement_validation_outer_fold_count_mismatch",
                "P2.3 expanding split did not produce the frozen outer count",
            )
        configs = deepcopy(
            self.inputs.preregistration["probe_models"]["hyperparameters"]
        )
        if repaired:
            frozen = self.manifest.payload["frozen_probe_configs"]
            selection_digest = self.manifest.payload[
                "development_selection_artifact_digest"
            ]
            configs["REGULARIZED_LOGISTIC_REGRESSION"] = dict(
                self.inputs.walk_forward_harness.probe(
                    "REGULARIZED_LOGISTIC_REGRESSION"
                )
            )
            configs["REGULARIZED_LOGISTIC_REGRESSION"].update(
                {
                    "selection_mode": "frozen_development",
                    "selected_C": frozen["REGULARIZED_LOGISTIC_REGRESSION"][
                        "selected_C"
                    ],
                    "C": [frozen["REGULARIZED_LOGISTIC_REGRESSION"]["selected_C"]],
                    "development_selection_digest": selection_digest,
                }
            )
            configs["NAIVE_BAYES"].update(
                {
                    "selection_mode": "frozen_development",
                    "selected_alpha": frozen["NAIVE_BAYES"]["selected_alpha"],
                    "alpha": [frozen["NAIVE_BAYES"]["selected_alpha"]],
                    "development_selection_digest": selection_digest,
                }
            )
            configs["SHALLOW_CALIBRATED_TREE"].update(
                {
                    "selection_mode": "frozen_development",
                    "selected_max_depth": frozen["SHALLOW_CALIBRATED_TREE"][
                        "selected_max_depth"
                    ],
                    "selected_min_samples_leaf": frozen["SHALLOW_CALIBRATED_TREE"][
                        "selected_min_samples_leaf"
                    ],
                    "max_depth": [
                        frozen["SHALLOW_CALIBRATED_TREE"]["selected_max_depth"]
                    ],
                    "min_samples_leaf": [
                        frozen["SHALLOW_CALIBRATED_TREE"]["selected_min_samples_leaf"]
                    ],
                    "development_selection_digest": selection_digest,
                }
            )
        checkpoint_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        settlement_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        state_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        issue_gains: dict[str, list[float]] = {probe: [] for probe in PROBES}
        gate_probabilities: list[tuple[float, ...]] = []
        ordered_targets: list[tuple[int, ...]] = []
        with (
            self.audit_observer.phase("feature_cache"),
            self.audit_observer.phase("feature_cache_initialization"),
        ):
            feature_cache = StrictPriorFeatureCache(
                dataset,
                include_prior_state=repaired,
            )
        checkpoint_journal = StrictPriorCheckpointJournal(
            output_dir=self.output_dir,
            replicate=replicate,
        )
        settlement_resume_journal = SettledFoldResumeJournal(
            output_dir=self.output_dir,
            replicate=replicate,
        )
        if len(settlement_resume_journal) > len(folds):
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_overflow",
                "settled fold prefix exceeds the frozen fold schedule",
            )
        if len(settlement_resume_journal) > len(checkpoint_journal):
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_checkpoint_gap",
                "settled fold prefix exceeds the strict-prior checkpoint prefix",
            )
        resume_prefix_length = (
            len(settlement_resume_journal)
            if self.trace_records is None and not self.audit_observer.enabled
            else 0
        )
        prepared_learned: dict[str, Any] = {}
        prepared_boundary_fold_index: int | None = None

        for fold_index, fold in enumerate(folds):
            self.audit_observer.count_fold()
            validate_outer_fold(
                fold,
                minimum_training_issues=dataset.minimum_training_length,
                dataset_issue_count=dataset.issue_count,
            )
            guard_train_test_overlap(fold)
            if fold_index < resume_prefix_length:
                checkpoint_entry = checkpoint_journal.entry(fold_index)
                if (
                    checkpoint_entry.get("fold_index") != fold_index
                    or checkpoint_entry.get("test_issue") != fold.test_issue
                    or checkpoint_entry.get("probe_order") != list(PROBES)
                    or checkpoint_entry.get("target_access")
                    != "forbidden_before_this_persisted_entry"
                ):
                    raise MeasurementValidationContractError(
                        "measurement_validation_settled_fold_checkpoint_mismatch",
                        f"strict-prior checkpoint identity changed at fold {fold_index}",
                    )
                (
                    restored_state_digests,
                    predictions,
                    restored_target,
                ) = settlement_resume_journal.restored_fold(
                    fold_index,
                    checkpoint_entry=checkpoint_entry,
                )
                checkpoint_entry_digests = checkpoint_entry.get("checkpoint_digests")
                if not isinstance(checkpoint_entry_digests, Mapping):
                    raise MeasurementValidationContractError(
                        "measurement_validation_settled_fold_checkpoint_mismatch",
                        f"strict-prior checkpoint digests are missing at fold {fold_index}",
                    )
                for probe_id in PROBES:
                    checkpoint_digest = _prediction_checkpoint_digest(
                        dataset_digest=dataset.artifact_digest,
                        replicate=replicate,
                        probe_id=probe_id,
                        train_start_issue=fold.train_issues[0],
                        train_end_issue=fold.train_issues[-1],
                        test_issue=fold.test_issue,
                        probe_state_digest=restored_state_digests[probe_id],
                        probability=predictions[probe_id],
                        git_commit=self.inputs.git_commit,
                    )
                    if checkpoint_entry_digests.get(probe_id) != checkpoint_digest:
                        raise MeasurementValidationContractError(
                            "measurement_validation_settled_fold_checkpoint_mismatch",
                            f"restored prediction changed at fold {fold_index}",
                        )
                    checkpoint_digests[probe_id].append(checkpoint_digest)
                    state_digests[probe_id].append(restored_state_digests[probe_id])
                # Target access is allowed only after every restored prediction
                # has reproduced its already-persisted strict-prior identity.
                target = dataset.issue(fold.test_issue).target_vector
                if target != restored_target:
                    raise MeasurementValidationContractError(
                        "measurement_validation_settled_fold_target_mismatch",
                        f"restored target changed at fold {fold_index}",
                    )
                ordered_targets.append(target)
                for probe_id in PROBES:
                    with self.audit_observer.phase("prediction_metric"):
                        settlement_digest, gain, _ = _settle_prediction(
                            checkpoint_digest=checkpoint_digests[probe_id][-1],
                            test_issue=fold.test_issue,
                            target=target,
                            probability=predictions[probe_id],
                        )
                    settlement_digests[probe_id].append(settlement_digest)
                    issue_gains[probe_id].append(gain)
                gate_probabilities.append(predictions[GATE_PROBE])
                continue
            training = restrict_to_training_history(
                dataset,
                available_through_issue=fold.train_issues[-1],
            )
            policy = self.periodic_refit_contract
            boundary_fold_index = (
                fold_index if policy is None else policy.boundary_fold_index(fold_index)
            )
            refit_learned = (
                policy is None
                or not prepared_learned
                or policy.is_refit_boundary(fold_index)
            )
            needs_full_current_view = (
                policy is None
                or policy.is_refit_boundary(fold_index)
                or self.trace_records is not None
            )
            with self.audit_observer.phase("feature_cache"):
                feature_cache.reveal_training_history(
                    training,
                    through_issue=fold.train_issues[-1],
                )
                train_view = (
                    feature_cache.build_runtime_train_feature_view(
                        training,
                        fold.train_issues,
                        exact_identity=self.trace_records is not None,
                    )
                    if needs_full_current_view
                    else feature_cache.build_runtime_empirical_prefix_view(
                        training,
                        fold.train_issues,
                    )
                )
                blind = feature_cache.build_blind_test_feature_view(
                    target_issue=fold.test_issue,
                )
            probe_runtime_cache = ExactProbeRuntimeCache(
                feature_cache=feature_cache,
                outer_train_view=train_view,
            )
            boundary_training = training
            boundary_train_view = train_view
            boundary_runtime_cache = probe_runtime_cache
            if refit_learned and boundary_fold_index != fold_index:
                boundary_fold = folds[boundary_fold_index]
                boundary_training = restrict_to_training_history(
                    dataset,
                    available_through_issue=boundary_fold.train_issues[-1],
                )
                boundary_train_view = feature_cache.build_runtime_train_feature_view(
                    boundary_training,
                    boundary_fold.train_issues,
                    exact_identity=self.trace_records is not None,
                )
                boundary_runtime_cache = ExactProbeRuntimeCache(
                    feature_cache=feature_cache,
                    outer_train_view=boundary_train_view,
                )
            guard_feature_timestamp(blind)
            if train_view.red_numbers:
                guard_number_event_rows(
                    issue_ids=train_view.issue_ids,
                    red_numbers=train_view.red_numbers,
                )
            elif needs_full_current_view:
                feature_cache.guard_runtime_number_event_rows(train_view)
            else:
                feature_cache.guard_runtime_empirical_prefix(train_view)
            if boundary_train_view is not train_view:
                feature_cache.guard_runtime_number_event_rows(boundary_train_view)

            predictions: dict[str, tuple[float, ...]] = {}
            probe_state_payloads: dict[str, dict[str, Any]] | None = (
                {} if self.trace_records is not None else None
            )
            for probe_id in PROBES:
                if probe_id == "EMPIRICAL_BASELINE":
                    config = {}
                elif probe_id == "REGULARIZED_LOGISTIC_REGRESSION":
                    config = (
                        configs[probe_id]
                        if repaired
                        else self.inputs.walk_forward_harness.probe(probe_id)
                    )
                else:
                    config = configs[probe_id]
                if probe_id == "EMPIRICAL_BASELINE":
                    with self.audit_observer.phase("estimator_calibrator_fit"):
                        prepared = probe_runtime_cache.prepare_empirical_baseline(
                            train_view
                        )
                    self.audit_observer.count_fit()
                elif refit_learned:
                    boundary_fold = folds[boundary_fold_index]
                    with self.audit_observer.phase("estimator_calibrator_fit"):
                        prepared = prepare_probe(
                            probe_id=probe_id,
                            dataset=boundary_training,
                            train_view=boundary_train_view,
                            probe_config=config,
                            outer_test_issue=boundary_fold.test_issue,
                            train_view_builder=(
                                boundary_runtime_cache.build_train_feature_view
                            ),
                            runtime_cache=boundary_runtime_cache,
                        )
                    prepared_learned[probe_id] = prepared
                    self.audit_observer.count_fit()
                else:
                    prepared = prepared_learned[probe_id]
                with self.audit_observer.phase("prediction_metric"):
                    probability = prepared.predict(blind)
                checkpoint_digest = _prediction_checkpoint_digest(
                    dataset_digest=dataset.artifact_digest,
                    replicate=replicate,
                    probe_id=probe_id,
                    train_start_issue=fold.train_issues[0],
                    train_end_issue=fold.train_issues[-1],
                    test_issue=fold.test_issue,
                    probe_state_digest=prepared.state.state_digest,
                    probability=probability,
                    git_commit=self.inputs.git_commit,
                )
                checkpoint_digests[probe_id].append(checkpoint_digest)
                state_digests[probe_id].append(prepared.state.state_digest)
                if probe_state_payloads is not None:
                    probe_state_payloads[probe_id] = prepared.state.to_dict()
                predictions[probe_id] = probability
            if refit_learned:
                if tuple(prepared_learned) != LEARNED_PROBES:
                    raise AssertionError("periodic learned-probe state is incomplete")
                prepared_boundary_fold_index = boundary_fold_index
            if (
                policy is not None
                and prepared_boundary_fold_index
                != policy.boundary_fold_index(fold_index)
            ):
                raise MeasurementValidationContractError(
                    "periodic_refit_boundary_mismatch",
                    f"learned state boundary changed at fold {fold_index}",
                )

            with self.audit_observer.phase("checkpoint_artifact_persistence"):
                checkpoint_journal.record(
                    fold_index=fold_index,
                    test_issue=fold.test_issue,
                    checkpoint_digests={
                        probe_id: checkpoint_digests[probe_id][-1]
                        for probe_id in PROBES
                    },
                )
            # First target access is deliberately below all four immutable
            # prediction identities and their persisted journal entry.
            target = dataset.issue(fold.test_issue).target_vector
            ordered_targets.append(target)
            trace_probe_payloads: dict[str, dict[str, Any]] | None = (
                {} if self.trace_records is not None else None
            )
            for probe_id in PROBES:
                with self.audit_observer.phase("prediction_metric"):
                    settlement_digest, gain, metric = _settle_prediction(
                        checkpoint_digest=checkpoint_digests[probe_id][-1],
                        test_issue=fold.test_issue,
                        target=target,
                        probability=predictions[probe_id],
                    )
                settlement_digests[probe_id].append(settlement_digest)
                issue_gains[probe_id].append(gain)
                if trace_probe_payloads is not None:
                    if probe_state_payloads is None:
                        raise AssertionError(
                            "trace probe state capture was not initialized"
                        )
                    trace_probe_payloads[probe_id] = {
                        "probe_state": probe_state_payloads[probe_id],
                        "probabilities": list(predictions[probe_id]),
                        "issue_metric": metric.to_dict(),
                        "prediction_checkpoint_digest": checkpoint_digests[probe_id][
                            -1
                        ],
                        "settlement_digest": settlement_digests[probe_id][-1],
                    }
            with self.audit_observer.phase("checkpoint_artifact_persistence"):
                settlement_resume_journal.record(
                    fold_index=fold_index,
                    test_issue=fold.test_issue,
                    checkpoint_entry=checkpoint_journal.entry(fold_index),
                    probe_state_digests={
                        probe_id: state_digests[probe_id][-1] for probe_id in PROBES
                    },
                    probabilities=predictions,
                    target_vector=target,
                )
            if self.trace_records is not None:
                if trace_probe_payloads is None:
                    raise AssertionError("trace capture was not initialized")
                self.trace_records.append(
                    {
                        "fold_index": fold_index,
                        "train_start_issue": fold.train_issues[0],
                        "train_end_issue": fold.train_issues[-1],
                        "test_issue": fold.test_issue,
                        **(
                            {
                                "learned_probe_refit_boundary_fold_index": (
                                    prepared_boundary_fold_index
                                )
                            }
                            if policy is not None
                            else {}
                        ),
                        "train_feature_view_digest": train_view.feature_view_digest,
                        "blind_feature_view_digest": blind.feature_view_digest,
                        "target_digest": canonical_digest(
                            list(target),
                            domain="dehps.m4-p2.formal-fold-target.v1",
                        ),
                        "target_vector": list(target),
                        "probes": trace_probe_payloads,
                    }
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
        bootstrap_runner = (
            moving_block_bootstrap_statistics
            if self.periodic_refit_contract is None
            else moving_block_bootstrap_statistics_exact_runtime
        )
        with self.audit_observer.phase("bootstrap"):
            bootstrap, bootstrap_seeds = bootstrap_runner(
                pe1_values,
                manifest=self.inputs.resampling,
                scenario_id=replicate.cell.scenario_id,
                parent_run_digest=replicate.artifact_digest,
                replicate_count=self.manifest.bootstrap_replicates,
            )
        self.audit_observer.count_resample(len(bootstrap))
        probability_matrix = np.asarray(gate_probabilities, dtype=np.float64)
        target_matrix = np.asarray(ordered_targets, dtype=np.int8)

        if self.periodic_refit_contract is None:

            def statistic_for_indices(indices: Sequence[int]) -> float:
                permuted = target_matrix[np.asarray(indices, dtype=np.int64)]
                return float(vectorized_p2_pe1(probability_matrix, permuted).mean())

        else:
            statistic_for_indices = prepare_vectorized_p2_pe1_permutation_statistic(
                probability_matrix,
                target_matrix,
            )

        permutation_runner = (
            block_permutation_statistics
            if self.periodic_refit_contract is None
            else block_permutation_statistics_exact_runtime
        )
        with self.audit_observer.phase("permutation"):
            permutation, permutation_seeds = permutation_runner(
                issue_count=len(folds),
                statistic_for_indices=statistic_for_indices,
                manifest=self.inputs.resampling,
                scenario_id=replicate.cell.scenario_id,
                parent_run_digest=replicate.artifact_digest,
                replicate_count=self.manifest.permutation_replicates,
            )
        self.audit_observer.count_resample(len(permutation))
        inference = primary_inference(
            pe1_issue_statistics=pe1_values,
            permutation_null_statistics=permutation,
            bootstrap_statistics=bootstrap,
        )
        truth_bits = (
            0.0
            if truth is None
            else float(
                truth[
                    (
                        "marginal_information_bits_per_issue"
                        if repaired
                        else "joint_draw_information_bits_per_issue"
                    )
                ]
            )
        )
        with self.audit_observer.phase("checkpoint_artifact_persistence"):
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
            "truth_estimand": (
                "marginal_information_bits_per_issue"
                if repaired
                else "joint_draw_information_bits_per_issue"
            ),
            "scenario_role": replicate.cell.scenario_role,
            "formal_power_eligible": replicate.cell.formal_power_eligible,
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
            **(
                {
                    "measurement_update_policy_digest": (
                        self.periodic_refit_contract.artifact_digest
                    ),
                    "learned_probe_refit_interval_folds": (
                        self.periodic_refit_contract.learned_probe_refit_interval_folds
                    ),
                    "learned_probe_refit_boundary_count": (
                        (
                            len(folds)
                            + self.periodic_refit_contract.learned_probe_refit_interval_folds
                            - 1
                        )
                        // self.periodic_refit_contract.learned_probe_refit_interval_folds
                    ),
                    "empirical_baseline_update_count": len(folds),
                }
                if self.periodic_refit_contract is not None
                else {}
            ),
            "gate_probe": GATE_PROBE,
            "metric_kernel_digest": METRIC_KERNEL_DIGEST,
            "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
            "resampling_kernel_digest": RESAMPLING_KERNEL_DIGEST,
            "git_commit": self.inputs.git_commit,
            "working_tree_clean": True,
            "real_history_used": False,
            "production_action": "none",
        }
