from __future__ import annotations

import json
import math
import os
import platform
import sys
import sysconfig
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from importlib import import_module
from importlib.metadata import distribution, version
from math import log2
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np
from threadpoolctl import threadpool_info

from dehps.contracts import canonical_digest
from dehps.golden_source_identity import (
    GoldenSourceIdentityError,
    golden_source_identity_from_contract,
    project_golden_source_integrity_contract,
    validate_golden_source_integrity_identity,
)
from dehps.research_os.information_theory.digest import preregistration_digest
from dehps.research_os.information_theory.metrics import evaluate_issue
from dehps.research_os.information_theory.metrics.contracts import (
    ISSUE_SCHEMA_VERSION,
    NUMBER_EVENT_SCHEMA_VERSION,
)
from dehps.research_os.information_theory.metrics.kernel import BASELINE_IDENTITY
from dehps.research_os.information_theory.metrics.probability import (
    PROBABILITY_EPSILON,
)
from dehps.research_os.information_theory.probes import prepare_probe
from dehps.research_os.information_theory.resampling import (
    ResamplingKernelManifest,
    load_resampling_manifest,
)
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)
from dehps.research_os.information_theory.walk_forward.contracts import (
    THEORETICAL_PROBABILITY,
    BlindTestFeatureView,
    HarnessManifest,
    OuterFold,
    SyntheticDataset,
    TrainFeatureView,
    TrainingDatasetView,
)
from dehps.research_os.information_theory.walk_forward.errors import (
    WalkForwardError,
)
from dehps.research_os.information_theory.walk_forward.feature_view import (
    FEATURE_NAMES,
)
from dehps.research_os.information_theory.walk_forward.leakage import (
    guard_feature_timestamp,
    guard_number_event_rows,
    guard_train_test_overlap,
)
from dehps.research_os.information_theory.walk_forward.manifest import (
    load_harness_manifest,
)
from dehps.research_os.information_theory.walk_forward.split import (
    validate_outer_fold,
)

from .contracts import (
    METRIC_KERNEL_DIGEST,
    PREREGISTRATION_DIGEST,
    RESAMPLING_KERNEL_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST,
    MeasurementValidationContractError,
    MeasurementValidationManifest,
)
from .dataset import generate_evaluation_dataset
from .float_identity import (
    FloatIdentityError,
)
from .float_identity import (
    assert_float64_tree as _assert_float64_tree,
)
from .float_identity import (
    encode_float64_tree as _encode_float64_tree,
)
from .float_identity import (
    float64_bits as _float64_bits,
)
from .repaired_contracts import STATE_VISIBLE_FEATURE_MANIFEST_DIGEST
from .schedule import AnalysisReplicate, build_cells, build_replicate
from .statistics import (
    block_permutation_statistics,
    block_permutation_statistics_exact_runtime,
    moving_block_bootstrap_statistics,
    moving_block_bootstrap_statistics_exact_runtime,
    primary_inference,
    seed_set_digest,
)

GOLDEN_REFERENCE_SCHEMA = "dehps-m4-p2-9-phase0-golden-reference.v1"
GOLDEN_EQUIVALENCE_SCHEMA = "dehps-m4-p2-9-phase0-golden-equivalence.v1"
FLOAT64_ENCODING = "ieee754-binary64-big-endian-lower-hex"
ACCELERATION_BOUNDARY_SCOPE = "literal_behavior_path_and_fresh_import_closure"
FIXTURE_PARENT_EXECUTION_ID = sha256(
    b"dehps.m4-p2-9.phase0-golden-fixture-parent.v1"
).hexdigest()
# Real repository commit that freezes the P2.6.1 implementation used by the
# fixture.  The measurement-validation/probe/metric/resampling surface is
# unchanged between this commit and the Phase 0 implementation base.
FIXTURE_GIT_COMMIT = "70f83a5400c6207cbe3806e69329a233e461e311"
PROBES = (
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)
GOLDEN_LEARNED_PROBES = (
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)
P263_PERIODIC_REFIT_CONTRACT_DIGEST = (
    "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
)
SHARED_FROZEN_COMPONENTS = (
    "synthetic_dataset_generator",
    "probe_model_core",
    "issue_metric_kernel",
    "bootstrap_kernel",
    "block_permutation_schedule",
    "primary_inference_kernel",
)
ACCELERATION_BOUNDARY_COMPONENTS = (
    "outer_fold_orchestration",
    "state_visible_feature_construction",
    "probe_runtime_cache",
    "replicate_evaluator",
    "permutation_pe1_arithmetic",
    "checkpoint_journal_serialization",
)
PROBE_STATE_KEYS = frozenset(
    {
        "probe_id",
        "probe_type",
        "training_start_issue",
        "training_end_issue",
        "training_issue_count",
        "training_row_count",
        "feature_manifest_digest",
        "hyperparameters",
        "hyperparameter_selection_digest",
        "seed_policy",
        "preprocessing_state_digest",
        "model_parameters_digest",
        "convergence_status",
        "failure",
        "state_digest",
    }
)
ISSUE_METRIC_KEYS = frozenset(
    {
        "schema_version",
        "issue_id",
        "cluster_id",
        "probability_epsilon",
        "baseline_identity",
        "number_events",
        "baseline_log_loss_nats_per_issue",
        "probe_log_loss_nats_per_issue",
        "observed_log_loss_gain_nats_per_issue",
        "baseline_log_loss_bits_per_issue",
        "probe_log_loss_bits_per_issue",
        "observed_log_loss_gain_bits_per_issue",
        "baseline_log_loss_nats_per_number_event",
        "probe_log_loss_nats_per_number_event",
        "baseline_log_loss_bits_per_number_event",
        "probe_log_loss_bits_per_number_event",
        "baseline_brier_sum_per_issue",
        "probe_brier_sum_per_issue",
        "brier_gain_per_issue",
        "baseline_brier_mean_per_number_event",
        "probe_brier_mean_per_number_event",
        "actual_red_count",
        "predicted_red_count",
        "red_count_error",
        "mean_predicted_probability",
        "eligible_for_pe1",
        "eligible_for_final_pe2",
        "gain_direction",
        "baseline_clip_diagnostics",
        "probe_clip_diagnostics",
    }
)
NUMBER_EVENT_METRIC_KEYS = frozenset(
    {
        "schema_version",
        "issue_id",
        "cluster_id",
        "red_number",
        "target",
        "baseline_raw_probability",
        "probe_raw_probability",
        "baseline_clipped_probability",
        "probe_clipped_probability",
        "baseline_log_loss_nats_per_number_event",
        "probe_log_loss_nats_per_number_event",
        "baseline_log_loss_bits_per_number_event",
        "probe_log_loss_bits_per_number_event",
        "baseline_brier_per_number_event",
        "probe_brier_per_number_event",
    }
)
CLIP_DIAGNOSTIC_KEYS = frozenset(
    {
        "raw_min_probability",
        "raw_max_probability",
        "clipped_min_probability",
        "clipped_max_probability",
        "clip_count_low",
        "clip_count_high",
        "clip_fraction",
        "epsilon",
    }
)
STATE_NUMBER_INTERACTION_NAMES = tuple(
    f"prior_state_x_red_{number:02d}" for number in range(1, 34)
)
STATE_VISIBLE_FEATURE_NAMES = (
    *FEATURE_NAMES,
    "prior_mechanism_state",
    *STATE_NUMBER_INTERACTION_NAMES,
)
_TRAIN_FEATURE_DOMAIN = "dehps.m4.walk-forward.train-feature-view.v1"
_BLIND_FEATURE_DOMAIN = "dehps.m4.walk-forward.blind-feature-view.v1"
EXECUTOR_THREAD_ENV_KEYS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
EXECUTOR_HASH_ENV_KEY = "PYTHONHASHSEED"
EXECUTOR_JIT_ENV_PREFIXES = ("NUMBA_", "LLVMLITE_")
EXECUTOR_ML_ENV_PREFIXES = ("JOBLIB_", "LOKY_", "SKLEARN_")
EXECUTOR_NUMERIC_ENV_PREFIXES = (
    "BLIS_",
    "MKL_",
    "NPY_",
    "NUMEXPR_",
    "OMP_",
    "OPENBLAS_",
    "SCIPY_",
    "VECLIB_",
)
CONSTRUCTION_SOURCE_INTEGRITY_IDENTITY_KEYS = (
    "source_integrity_contract_digest",
    "shared_frozen_source_set_digest",
    "approved_acceleration_source_set_digest",
    "independent_oracle_source_set_digest",
    "audit_orchestration_source_set_digest",
)


class GoldenReferenceError(RuntimeError):
    pass


def _validated_construction_source_identity(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(
        CONSTRUCTION_SOURCE_INTEGRITY_IDENTITY_KEYS
    ):
        raise GoldenReferenceError(
            "golden_reference_construction_source_identity_invalid"
        )
    identity = {
        key: value.get(key) for key in CONSTRUCTION_SOURCE_INTEGRITY_IDENTITY_KEYS
    }
    if any(not _is_lower_hex_digest(digest) for digest in identity.values()):
        raise GoldenReferenceError(
            "golden_reference_construction_source_identity_invalid"
        )
    return {key: str(digest) for key, digest in identity.items()}


def _validated_golden_source_identity(value: object) -> dict[str, str]:
    try:
        return validate_golden_source_integrity_identity(value)
    except GoldenSourceIdentityError as exc:
        raise GoldenReferenceError(
            f"golden_reference_golden_source_identity_invalid:{exc}"
        ) from exc


def float64_bits(value: Real) -> str:
    try:
        return _float64_bits(value)
    except FloatIdentityError as exc:
        raise GoldenReferenceError(str(exc)) from exc


def encode_float64_tree(value: Any) -> Any:
    """Return a JSON primitive tree with every real float encoded by bits.

    Integers and booleans remain integers and booleans.  This avoids the
    ordinary Python equality rule that considers ``0.0 == -0.0`` while keeping
    the artifact consumable by implementations in other languages.
    """

    try:
        return _encode_float64_tree(value)
    except FloatIdentityError as exc:
        raise GoldenReferenceError(str(exc)) from exc


def assert_float64_tree(value: Any) -> None:
    """Fail when an encoded fixture still contains an unencoded real float."""
    try:
        _assert_float64_tree(value)
    except FloatIdentityError as exc:
        raise GoldenReferenceError(str(exc)) from exc


def canonical_journal_bytes(entries: Sequence[Mapping[str, Any]]) -> bytes:
    lines = [
        json.dumps(
            dict(entry),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        for entry in entries
    ]
    return b"" if not lines else b"\n".join(lines) + b"\n"


def journal_bytes_sha256(value: bytes) -> str:
    return sha256(value).hexdigest()


def build_exact_golden_attestation(
    *,
    plan_digest: str,
    reference_payload: Mapping[str, Any],
    observed_payload: Mapping[str, Any],
    reference_journal_bytes: bytes,
    observed_journal_bytes: bytes,
) -> dict[str, Any]:
    reference = encode_float64_tree(reference_payload)
    observed = encode_float64_tree(observed_payload)
    assert_float64_tree(reference)
    assert_float64_tree(observed)
    _require_attestation_fixture_shape(reference, plan_digest=plan_digest)
    _require_attestation_fixture_shape(observed, plan_digest=plan_digest)
    golden_source_identity = _validated_golden_source_identity(
        reference.get("golden_source_integrity_identity")
    )
    mismatch = _first_mismatch(reference, observed)
    if mismatch is not None:
        raise GoldenReferenceError(f"golden_reference_payload_mismatch:{mismatch}")
    fixture_digest = _attested_fixture_digest(reference)
    observed_fixture_digest = _attested_fixture_digest(observed)
    if reference_journal_bytes != observed_journal_bytes:
        raise GoldenReferenceError("golden_reference_journal_bytes_mismatch")
    _require_attested_journal_bytes(reference, reference_journal_bytes)
    _require_attested_journal_bytes(observed, observed_journal_bytes)
    journal_digest = journal_bytes_sha256(reference_journal_bytes)
    payload: dict[str, Any] = {
        "schema_version": GOLDEN_EQUIVALENCE_SCHEMA,
        "artifact_type": "GoldenReferenceReplayArtifact",
        "artifact_digest": "",
        "benchmark_plan_digest": plan_digest,
        "executor_fingerprint_digest": reference["executor_fingerprint_digest"],
        "golden_source_integrity_identity": golden_source_identity,
        "exact_replay_scope": "same_canonical_executor_fingerprint_only",
        "status": "EXACT_GOLDEN_REPLAY_VERIFIED",
        "oracle_kind": "immutable_registered_golden_fixture",
        "immutable_golden_fixture_is_oracle": True,
        "acceleration_boundary_independent": True,
        "acceleration_boundary_independence_scope": ACCELERATION_BOUNDARY_SCOPE,
        "oracle_construction_process_isolated": False,
        "oracle_construction_fully_implementation_independent": False,
        "shared_frozen_components": list(SHARED_FROZEN_COMPONENTS),
        "independent_acceleration_boundary_components": list(
            ACCELERATION_BOUNDARY_COMPONENTS
        ),
        "float_encoding": FLOAT64_ENCODING,
        "fixture_artifact_digest": fixture_digest,
        "reference_fixture_digest": fixture_digest,
        "observed_fixture_digest": observed_fixture_digest,
        "checkpoint_journal_bytes_sha256": journal_digest,
        "payload_exact": True,
        "float_bits_exact": True,
        "journal_bytes_exact": True,
        "evidence_created": False,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "historical_outcomes_read": False,
        "production_action": "none",
        "promotion_gate_opened": False,
        "parent_digests": sorted(
            {
                plan_digest,
                fixture_digest,
                journal_digest,
                *golden_source_identity.values(),
            }
        ),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2-9.phase0-golden-replay.v1",
    )
    return payload


def _require_attestation_fixture_shape(
    payload: Mapping[str, Any],
    *,
    plan_digest: str,
) -> None:
    if payload.get("artifact_type") != "Phase0GoldenReferenceFixture.v1":
        raise GoldenReferenceError("golden_reference_fixture_type_invalid")
    if payload.get("benchmark_plan_digest") != plan_digest:
        raise GoldenReferenceError("golden_reference_fixture_plan_mismatch")
    if payload.get("float_encoding") != FLOAT64_ENCODING:
        raise GoldenReferenceError("golden_reference_fixture_float_encoding_changed")
    _validated_golden_source_identity(payload.get("golden_source_integrity_identity"))
    if (
        not _is_lower_hex_digest(payload.get("executor_fingerprint_digest"))
        or payload.get("exact_replay_scope")
        != "same_canonical_executor_fingerprint_only"
        or payload.get("oracle_kind") != "immutable_registered_golden_fixture"
        or payload.get("immutable_golden_fixture_is_oracle") is not True
        or payload.get("acceleration_boundary_independent") is not True
        or payload.get("acceleration_boundary_independence_scope")
        != ACCELERATION_BOUNDARY_SCOPE
        or payload.get("oracle_construction_process_isolated") is not False
        or payload.get("oracle_construction_fully_implementation_independent")
        is not False
        or payload.get("shared_frozen_components") != list(SHARED_FROZEN_COMPONENTS)
        or payload.get("independent_acceleration_boundary_components")
        != list(ACCELERATION_BOUNDARY_COMPONENTS)
    ):
        raise GoldenReferenceError("golden_reference_fixture_executor_changed")


def _require_attested_journal_bytes(
    payload: Mapping[str, Any],
    journal_bytes: bytes,
) -> None:
    text = payload.get("checkpoint_journal_utf8")
    if not isinstance(text, str) or text.encode("utf-8") != journal_bytes:
        raise GoldenReferenceError("golden_reference_fixture_journal_binding_mismatch")
    if payload.get("checkpoint_journal_bytes_sha256") != journal_bytes_sha256(
        journal_bytes
    ):
        raise GoldenReferenceError("golden_reference_fixture_journal_digest_mismatch")


def _attested_fixture_digest(payload: Mapping[str, Any]) -> str:
    claimed = payload.get("artifact_digest")
    if not isinstance(claimed, str) or len(claimed) != 64:
        raise GoldenReferenceError("golden_reference_fixture_digest_invalid")
    identity = dict(payload)
    identity.pop("artifact_digest", None)
    expected = canonical_digest(
        identity,
        domain="dehps.m4-p2-9.phase0-golden-fixture.v1",
    )
    if claimed != expected:
        raise GoldenReferenceError("golden_reference_fixture_digest_mismatch")
    return claimed


def _first_mismatch(expected: Any, observed: Any, path: str = "$") -> str | None:
    if type(expected) is not type(observed):
        return f"{path}:type:{type(expected).__name__}!={type(observed).__name__}"
    if isinstance(expected, Mapping):
        expected_keys = set(expected)
        observed_keys = set(observed)
        if expected_keys != observed_keys:
            return f"{path}:keys:{sorted(expected_keys ^ observed_keys)}"
        for key in sorted(expected_keys):
            mismatch = _first_mismatch(expected[key], observed[key], f"{path}.{key}")
            if mismatch is not None:
                return mismatch
        return None
    if isinstance(expected, list):
        if len(expected) != len(observed):
            return f"{path}:length:{len(expected)}!={len(observed)}"
        for index, (expected_item, observed_item) in enumerate(
            zip(expected, observed, strict=True)
        ):
            mismatch = _first_mismatch(expected_item, observed_item, f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None
    if expected != observed:
        return f"{path}:value"
    return None


def literal_outer_folds(dataset: SyntheticDataset) -> tuple[OuterFold, ...]:
    minimum = dataset.minimum_training_length
    if dataset.issue_count <= minimum:
        raise WalkForwardError(
            "insufficient_training_history",
            f"need more than {minimum} issues for one outer prediction",
        )
    folds = tuple(
        OuterFold(tuple(range(1, test_issue)), test_issue)
        for test_issue in range(minimum + 1, dataset.issue_count + 1)
    )
    if len(folds) != dataset.outer_evaluation_length:
        raise WalkForwardError(
            "outer_scale_contract_mismatch",
            "literal outer fold count changed",
        )
    return folds


def literal_training_view(
    dataset: SyntheticDataset,
    *,
    available_through_issue: int,
) -> TrainingDatasetView:
    if available_through_issue < 1 or available_through_issue >= dataset.issue_count:
        raise WalkForwardError(
            "target_access_boundary_violation",
            "literal training view must stop before the test issue",
        )
    return TrainingDatasetView(
        source_dataset_digest=dataset.artifact_digest,
        scenario_id=dataset.scenario_id,
        scale_id=dataset.scale_id,
        minimum_training_length=dataset.minimum_training_length,
        seed_policy=dict(dataset.seed_policy),
        seed_policy_digest=dataset.seed_policy_digest,
        replicate_seed=dataset.replicate_seed,
        issues=tuple(
            dataset.issue(index) for index in range(1, available_through_issue + 1)
        ),
        available_through_issue=available_through_issue,
    )


class PythonReferenceBackend:
    """Literal, uncached oracle for the frozen P2.6.1 fold computation.

    This class deliberately has no dependency on the incremental feature
    cache, the fold-local runtime cache, vectorized/native metrics, or the
    observed replicate evaluator.  It is slow by design.
    """

    def __init__(self, dataset: SyntheticDataset) -> None:
        self.dataset = dataset
        raw_states = dataset.raw_payload.get("prior_states")
        if (
            dataset.raw_payload.get("data_source") != "synthetic_only"
            or dataset.raw_payload.get("prior_state_for_real_history") != "forbidden"
            or dataset.raw_payload.get("prior_state_access")
            != "synthetic_instrument_only_strictly_before_target"
            or dataset.raw_payload.get("prior_state_available_strictly_before_target")
            is not True
            or not isinstance(raw_states, list)
            or len(raw_states) != dataset.issue_count
            or any(value not in (None, 0, 1) for value in raw_states)
        ):
            raise WalkForwardError(
                "prior_state_contract_missing",
                "literal P2.6.1 oracle requires frozen synthetic prior states",
            )
        state_digest = canonical_digest(
            raw_states,
            domain="dehps.m4-p2.evaluation-prior-states.v1",
        )
        if dataset.raw_payload.get("prior_state_digest") != state_digest:
            raise WalkForwardError(
                "prior_state_digest_mismatch",
                "literal prior-state sequence changed",
            )
        self._prior_states = tuple(raw_states)

    def outer_folds(self) -> tuple[OuterFold, ...]:
        return literal_outer_folds(self.dataset)

    def training_view(self, *, available_through_issue: int) -> TrainingDatasetView:
        return literal_training_view(
            self.dataset,
            available_through_issue=available_through_issue,
        )

    def build_train_feature_view(
        self,
        dataset: TrainingDatasetView,
        issue_ids: tuple[int, ...],
    ) -> TrainFeatureView:
        if (
            not issue_ids
            or tuple(sorted(set(issue_ids))) != issue_ids
            or dataset.artifact_digest != self.dataset.artifact_digest
            or max(issue_ids) > dataset.available_through_issue
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "literal train issues must be ordered and already revealed",
            )
        red_numbers, rows, targets, availability = self._feature_rows(
            dataset,
            issue_ids,
            include_targets=True,
        )
        identity = {
            "dataset_digest": dataset.artifact_digest,
            "issue_ids": issue_ids,
            "available_through_by_issue": availability,
            "construction_start_issue": 1,
            "construction_end_issue": issue_ids[-1] - 1,
            "feature_manifest_digest": STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
            "feature_names": STATE_VISIBLE_FEATURE_NAMES,
            "values": rows,
            "target_access": "outer_training_targets_only",
        }
        return TrainFeatureView(
            issue_ids=issue_ids,
            red_numbers=red_numbers,
            feature_names=STATE_VISIBLE_FEATURE_NAMES,
            values=rows,
            targets=targets,
            available_through_by_issue=availability,
            construction_start_issue=1,
            construction_end_issue=issue_ids[-1] - 1,
            feature_manifest_digest=STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
            feature_view_digest=canonical_digest(
                identity,
                domain=_TRAIN_FEATURE_DOMAIN,
            ),
        )

    def build_blind_test_feature_view(
        self,
        *,
        target_issue: int,
    ) -> BlindTestFeatureView:
        if target_issue < 2 or target_issue > self.dataset.issue_count:
            raise WalkForwardError(
                "target_access_boundary_violation",
                "literal blind issue is outside the dataset",
            )
        red_numbers, rows, _targets, availability = self._feature_rows(
            literal_training_view(
                self.dataset,
                available_through_issue=target_issue - 1,
            ),
            (target_issue,),
            include_targets=False,
        )
        history_count = target_issue - 1
        identity = {
            "dataset_digest": self.dataset.artifact_digest,
            "target_issue": target_issue,
            "available_through_issue": availability[0][1],
            "construction_start_issue": 1,
            "construction_end_issue": history_count,
            "feature_manifest_digest": STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
            "feature_names": STATE_VISIBLE_FEATURE_NAMES,
            "red_numbers": red_numbers,
            "values": rows,
            "target_access": "forbidden",
        }
        return BlindTestFeatureView(
            target_issue=target_issue,
            red_numbers=red_numbers,
            feature_names=STATE_VISIBLE_FEATURE_NAMES,
            values=rows,
            available_through_issue=history_count,
            construction_start_issue=1,
            construction_end_issue=history_count,
            feature_manifest_digest=STATE_VISIBLE_FEATURE_MANIFEST_DIGEST,
            feature_view_digest=canonical_digest(
                identity,
                domain=_BLIND_FEATURE_DOMAIN,
            ),
        )

    def evaluate_fold(
        self,
        *,
        fold: OuterFold,
        probe_configs: Mapping[str, Mapping[str, Any]],
        prepared_learned: dict[str, Any] | None = None,
        refit_learned: bool = True,
        before_target: Any | None = None,
    ) -> dict[str, Any]:
        validate_outer_fold(
            fold,
            minimum_training_issues=self.dataset.minimum_training_length,
            dataset_issue_count=self.dataset.issue_count,
        )
        guard_train_test_overlap(fold)
        training = self.training_view(available_through_issue=fold.train_issues[-1])
        train = self.build_train_feature_view(training, fold.train_issues)
        blind = self.build_blind_test_feature_view(target_issue=fold.test_issue)
        guard_feature_timestamp(blind)
        guard_number_event_rows(
            issue_ids=train.issue_ids,
            red_numbers=train.red_numbers,
        )
        prepared_by_probe: dict[str, Any] = {}
        predictions: dict[str, tuple[float, ...]] = {}
        for probe_id in PROBES:
            if (
                probe_id in GOLDEN_LEARNED_PROBES
                and not refit_learned
                and prepared_learned is not None
            ):
                prepared = prepared_learned[probe_id]
            else:
                prepared = prepare_probe(
                    probe_id=probe_id,
                    dataset=training,
                    train_view=train,
                    probe_config=probe_configs.get(probe_id, {}),
                    outer_test_issue=fold.test_issue,
                    train_view_builder=self.build_train_feature_view,
                    runtime_cache=None,
                )
                if (
                    probe_id in GOLDEN_LEARNED_PROBES
                    and prepared_learned is not None
                ):
                    prepared_learned[probe_id] = prepared
            prepared_by_probe[probe_id] = prepared
            predictions[probe_id] = prepared.predict(blind)
        if before_target is not None:
            before_target(
                fold=fold,
                train=train,
                blind=blind,
                prepared_by_probe=prepared_by_probe,
                predictions=predictions,
            )
        # Target access is intentionally after all four predictions.
        target = self.dataset.issue(fold.test_issue).target_vector
        probes: dict[str, Any] = {}
        for probe_id in PROBES:
            metric = evaluate_issue(
                issue_id=str(fold.test_issue),
                cluster_id=str(fold.test_issue),
                target_vector=target,
                baseline_probability_vector=(THEORETICAL_PROBABILITY,) * 33,
                probe_probability_vector=predictions[probe_id],
            )
            probes[probe_id] = {
                "probe_state": prepared_by_probe[probe_id].state.to_dict(),
                "probabilities": list(predictions[probe_id]),
                "issue_metric": metric.to_dict(),
            }
        return {
            "train_start_issue": fold.train_issues[0],
            "train_end_issue": fold.train_issues[-1],
            "test_issue": fold.test_issue,
            "train_feature_view_digest": train.feature_view_digest,
            "blind_feature_view_digest": blind.feature_view_digest,
            "target_digest": canonical_digest(
                list(target),
                domain="dehps.m4-p2.formal-fold-target.v1",
            ),
            "probes": probes,
        }

    def _feature_rows(
        self,
        dataset: TrainingDatasetView,
        issue_ids: tuple[int, ...],
        *,
        include_targets: bool,
    ) -> tuple[
        tuple[int, ...],
        tuple[tuple[float, ...], ...],
        tuple[int, ...],
        tuple[tuple[int, int], ...],
    ]:
        requested = set(issue_ids)
        red_numbers: list[int] = []
        rows: list[tuple[float, ...]] = []
        targets: list[int] = []
        availability: list[tuple[int, int]] = []
        counts = [0] * 33
        last_seen = [0] * 33
        previous_target = [0] * 33
        last_requested = max(issue_ids)
        for issue_index in range(1, last_requested + 1):
            if issue_index in requested:
                history_count = issue_index - 1
                availability.append((issue_index, history_count))
                prior_state = self._prior_states[issue_index - 1]
                encoded_state = 0.5 if prior_state is None else float(prior_state)
                for offset, red_number in enumerate(range(1, 34)):
                    gap = (
                        history_count - last_seen[offset] + 1
                        if last_seen[offset] > 0
                        else history_count
                    )
                    interactions = tuple(
                        encoded_state if candidate == red_number else 0.0
                        for candidate in range(1, 34)
                    )
                    red_numbers.append(red_number)
                    rows.append(
                        (
                            float(previous_target[offset]),
                            counts[offset] / history_count if history_count else 0.0,
                            float(gap),
                            red_number / 33.0,
                            encoded_state,
                            *interactions,
                        )
                    )
                    if include_targets:
                        targets.append(dataset.issue(issue_index).target_vector[offset])
            if not include_targets and issue_index == last_requested:
                break
            issue_target = dataset.issue(issue_index).target_vector
            for offset, value in enumerate(issue_target):
                if value:
                    counts[offset] += 1
                    last_seen[offset] = issue_index
            previous_target = list(issue_target)
        return (
            tuple(red_numbers),
            tuple(rows),
            tuple(targets),
            tuple(availability),
        )


@dataclass(frozen=True)
class PythonReferenceInputs:
    preregistration: Mapping[str, Any]
    walk_forward_harness: HarnessManifest
    resampling: ResamplingKernelManifest
    truth_by_scenario: Mapping[str, Mapping[str, Any]]
    fixture_git_commit: str


@dataclass(frozen=True)
class PythonReferenceEvaluation:
    result_payload: Mapping[str, Any]
    fold_traces: tuple[Mapping[str, Any], ...]
    checkpoint_journal_bytes: bytes


class LiteralCheckpointJournal:
    """Independent UTF-8/LF journal writer used by the golden oracle."""

    def __init__(self, *, output_dir: Path, replicate: AnalysisReplicate) -> None:
        self.path = (
            output_dir
            / "checkpoint-journals"
            / replicate.cell.scale_id
            / replicate.cell.scenario_id
            / f"{replicate.replicate_index:04d}-{replicate.artifact_digest}.jsonl"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        if self.path.is_file():
            raw = self.path.read_bytes()
            if raw and not raw.endswith(b"\n"):
                raise GoldenReferenceError("golden_reference_journal_missing_final_lf")
            for line in raw.splitlines():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise GoldenReferenceError("golden_reference_journal_entry_invalid")
                self._entries.append(value)

    def record(
        self,
        *,
        fold_index: int,
        test_issue: int,
        checkpoint_digests: Mapping[str, str],
    ) -> None:
        entry = {
            "schema_version": ("dehps-m4-p2-strict-prior-checkpoint-journal-entry.v1"),
            "fold_index": fold_index,
            "test_issue": test_issue,
            "probe_order": list(PROBES),
            "checkpoint_digests": dict(checkpoint_digests),
            "target_access": "forbidden_before_this_persisted_entry",
        }
        if fold_index < len(self._entries):
            if self._entries[fold_index] != entry:
                raise GoldenReferenceError(
                    f"golden_reference_journal_replay_mismatch:{fold_index}"
                )
            return
        if fold_index != len(self._entries):
            raise GoldenReferenceError("golden_reference_journal_gap")
        encoded = canonical_journal_bytes((entry,))
        with self.path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
        self._entries.append(entry)

    def finalize(self, *, expected_fold_count: int) -> tuple[str, int, bytes]:
        if len(self._entries) != expected_fold_count:
            raise GoldenReferenceError("golden_reference_journal_incomplete")
        with self.path.open("rb") as handle:
            os.fsync(handle.fileno())
            raw = handle.read()
        expected = canonical_journal_bytes(self._entries)
        if raw != expected:
            raise GoldenReferenceError("golden_reference_journal_encoding_changed")
        return (
            canonical_digest(
                self._entries,
                domain="dehps.m4-p2.strict-prior-checkpoint-journal.v1",
            ),
            len(self._entries),
            raw,
        )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldenReferenceError(
            f"golden_reference_input_invalid:{path}:{exc}"
        ) from exc
    if not isinstance(value, dict):
        raise GoldenReferenceError(f"golden_reference_input_not_object:{path}")
    return value


def _binary64_pairwise_sum(values: Sequence[float]) -> float:
    """Scalar transcription of the frozen binary64 reduction order.

    NumPy's fast-axis float64 sum uses eight accumulators for blocks up to
    128 values.  Reproducing that frozen numerical contract here preserves
    bit equality while keeping clipping, term selection, and reduction out of
    the vectorized production kernel.
    """

    count = len(values)
    if count < 8:
        result = -0.0
        for value in values:
            result += float(value)
        return result
    if count > 128:
        split = count // 2
        split -= split % 8
        return _binary64_pairwise_sum(values[:split]) + _binary64_pairwise_sum(
            values[split:]
        )
    accumulators = [float(values[index]) for index in range(8)]
    index = 8
    aligned_stop = count - (count % 8)
    while index < aligned_stop:
        for lane in range(8):
            accumulators[lane] += float(values[index + lane])
        index += 8
    result = (
        (accumulators[0] + accumulators[1]) + (accumulators[2] + accumulators[3])
    ) + ((accumulators[4] + accumulators[5]) + (accumulators[6] + accumulators[7]))
    while index < count:
        result += float(values[index])
        index += 1
    return result


def _literal_permutation_pe1(
    probabilities: np.ndarray,
    targets: np.ndarray,
) -> np.ndarray:
    """Scalar oracle for the frozen P2.6 permutation arithmetic.

    Deliberately avoid NumPy clipping, logarithm ufuncs, broadcasting, and
    reductions so a vectorized-kernel defect cannot validate itself.
    """

    probability = np.asarray(probabilities)
    target = np.asarray(targets)
    if (
        probability.ndim != 2
        or target.ndim != 2
        or probability.shape != target.shape
        or probability.shape[1] != 33
    ):
        raise GoldenReferenceError("golden_reference_permutation_input_invalid")
    baseline_loss = -(
        6 * log2(THEORETICAL_PROBABILITY) + 27 * log2(1.0 - THEORETICAL_PROBABILITY)
    )
    statistics: list[float] = []
    for probability_row, target_row in zip(probability, target, strict=True):
        loss_terms: list[float] = []
        red_count = 0
        for raw_probability, raw_target in zip(
            probability_row,
            target_row,
            strict=True,
        ):
            value = float(raw_probability)
            target_value = int(raw_target)
            if not math.isfinite(value) or target_value not in (0, 1):
                raise GoldenReferenceError("golden_reference_permutation_input_invalid")
            red_count += target_value
            clipped = min(max(value, PROBABILITY_EPSILON), 1.0 - PROBABILITY_EPSILON)
            loss_terms.append(
                log2(clipped) if target_value == 1 else log2(1.0 - clipped)
            )
        if red_count != 6:
            raise GoldenReferenceError("golden_reference_permutation_input_invalid")
        probe_loss = -_binary64_pairwise_sum(loss_terms)
        statistics.append(baseline_loss - probe_loss)
    return np.asarray(statistics, dtype=np.float64)


def _distribution_record_sha256(distribution_name: str) -> str:
    record = distribution(distribution_name).read_text("RECORD")
    if not record:
        raise GoldenReferenceError(
            f"golden_reference_distribution_record_missing:{distribution_name}"
        )
    return sha256(record.encode("utf-8")).hexdigest()


def _distribution_installed_tree_identity(
    distribution_name: str,
) -> dict[str, Any]:
    package = distribution(distribution_name)
    files = package.files
    if not files:
        raise GoldenReferenceError(
            f"golden_reference_distribution_files_missing:{distribution_name}"
        )
    entries: list[dict[str, Any]] = []
    for package_path in sorted(files, key=str):
        relative_path = str(package_path).replace(os.sep, "/")
        path_parts = Path(relative_path).parts
        if "__pycache__" in path_parts or relative_path.endswith(".pyc"):
            continue
        installed_path = Path(package.locate_file(package_path))
        if not installed_path.is_file():
            raise GoldenReferenceError(
                f"golden_reference_distribution_file_missing:{distribution_name}:"
                f"{relative_path}"
            )
        entries.append(
            {
                "path": relative_path,
                "size_bytes": installed_path.stat().st_size,
                "content_sha256": _binary_sha256(str(installed_path)),
            }
        )
    if not entries:
        raise GoldenReferenceError(
            f"golden_reference_distribution_files_missing:{distribution_name}"
        )
    return {
        "file_count": len(entries),
        "installed_tree_digest": canonical_digest(
            entries,
            domain=(
                "dehps.m4-p2-9.distribution-installed-tree." f"{distribution_name}.v1"
            ),
        ),
    }


def _binary_sha256(path_value: object) -> str:
    if not isinstance(path_value, str):
        raise GoldenReferenceError("golden_reference_native_binary_missing")
    path = Path(path_value)
    if not path.is_file():
        raise GoldenReferenceError("golden_reference_native_binary_missing")
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _critical_binary_sha256() -> dict[str, str]:
    modules = (
        "numpy._core._multiarray_umath",
        "numpy.random.bit_generator",
        "numpy.random._bounded_integers",
        "numpy.random._generator",
        "numpy.random._pcg64",
        "numba._helperlib",
        "orjson.orjson",
        "scipy.linalg._fblas",
        "scipy.optimize._lbfgsb",
        "scipy.special._special_ufuncs",
        "scipy.special._ufuncs",
        "sklearn._loss._loss",
        "sklearn.svm._liblinear",
        "sklearn.tree._criterion",
        "sklearn.tree._partitioner",
        "sklearn.tree._splitter",
        "sklearn.tree._tree",
        "sklearn.tree._utils",
    )
    binaries = {
        module_name: _binary_sha256(import_module(module_name).__file__)
        for module_name in modules
    }
    binaries["python_executable"] = _binary_sha256(sys.executable)
    library_directory = sysconfig.get_config_var("LIBDIR")
    library_names = (
        sysconfig.get_config_var("LDLIBRARY"),
        sysconfig.get_config_var("INSTSONAME"),
    )
    if not isinstance(library_directory, str):
        raise GoldenReferenceError("golden_reference_python_library_missing")
    library_path = next(
        (
            Path(library_directory) / name
            for name in library_names
            if isinstance(name, str) and (Path(library_directory) / name).is_file()
        ),
        None,
    )
    if library_path is None:
        raise GoldenReferenceError("golden_reference_python_library_missing")
    binaries["python_shared_library"] = _binary_sha256(str(library_path))

    llvmlite_ffi = import_module("llvmlite.binding.ffi")
    package_library = (
        Path(str(llvmlite_ffi.__file__)).resolve().parent
        / str(llvmlite_ffi.get_library_name())
    ).resolve()
    loaded_library = Path(str(llvmlite_ffi.lib._name)).resolve()
    try:
        mapped_libraries = {
            Path(line.rsplit(maxsplit=1)[-1]).resolve()
            for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
            if line.rsplit(maxsplit=1)[-1].startswith("/")
            and Path(line.rsplit(maxsplit=1)[-1]).name == package_library.name
        }
    except OSError as exc:
        raise GoldenReferenceError(
            "golden_reference_llvmlite_library_identity_unavailable"
        ) from exc
    if (
        not package_library.is_file()
        or loaded_library != package_library
        or mapped_libraries != {package_library}
    ):
        raise GoldenReferenceError(
            "golden_reference_llvmlite_library_identity_ambiguous"
        )
    binaries["llvmlite.binding.libllvmlite"] = _binary_sha256(str(package_library))
    return binaries


def _jit_runtime_identity() -> dict[str, Any]:
    llvm = import_module("llvmlite.binding")
    numba_config = import_module("numba.core.config")
    try:
        host_cpu_name = str(llvm.get_host_cpu_name())
        host_cpu_features = str(llvm.get_host_cpu_features().flatten())
        default_triple = str(llvm.get_default_triple())
        process_triple = str(llvm.get_process_triple())
        llvm_version_info = [int(value) for value in llvm.llvm_version_info]
    except (AttributeError, TypeError, ValueError) as exc:
        raise GoldenReferenceError(
            "golden_reference_llvm_codegen_identity_unavailable"
        ) from exc
    if (
        not host_cpu_name
        or not host_cpu_features
        or not default_triple
        or not process_triple
        or not llvm_version_info
    ):
        raise GoldenReferenceError("golden_reference_llvm_codegen_identity_unavailable")
    return {
        "llvm_version_info": llvm_version_info,
        "default_triple": default_triple,
        "process_triple": process_triple,
        "host_cpu_name": host_cpu_name,
        "host_cpu_features": host_cpu_features,
        "numba_codegen_config": {
            "disable_jit": int(numba_config.DISABLE_JIT),
            "cpu_name": numba_config.CPU_NAME,
            "cpu_features": numba_config.CPU_FEATURES,
            "optimization_level": int(numba_config.OPT),
            "loop_vectorize": int(numba_config.LOOP_VECTORIZE),
            "slp_vectorize": int(numba_config.SLP_VECTORIZE),
            "enable_avx": bool(numba_config.ENABLE_AVX),
            "boundscheck": numba_config.BOUNDSCHECK,
        },
    }


def _machine_learning_runtime_identity() -> dict[str, Any]:
    sklearn = import_module("sklearn")
    joblib_parallel = import_module("joblib.parallel")
    try:
        backend, configured_n_jobs = joblib_parallel.get_active_backend()
        effective_n_jobs = int(joblib_parallel.effective_n_jobs(None))
        sklearn_config = dict(sklearn.get_config())
    except (AttributeError, TypeError, ValueError) as exc:
        raise GoldenReferenceError(
            "golden_reference_ml_runtime_identity_unavailable"
        ) from exc
    backend_identity = {
        "module": type(backend).__module__,
        "qualname": type(backend).__qualname__,
        "configured_n_jobs": configured_n_jobs,
        "effective_n_jobs_for_none": effective_n_jobs,
        "nesting_level": getattr(backend, "nesting_level", None),
        "inner_max_num_threads": getattr(backend, "inner_max_num_threads", None),
    }
    if (
        backend_identity["module"] != "joblib._parallel_backends"
        or backend_identity["qualname"] != "LokyBackend"
        or configured_n_jobs is not None
        or effective_n_jobs != 1
    ):
        raise GoldenReferenceError("golden_reference_joblib_runtime_not_canonical")
    return {
        "sklearn_config": sklearn_config,
        "joblib_active_backend": backend_identity,
    }


def _loaded_system_library_sha256() -> dict[str, str]:
    try:
        lines = Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise GoldenReferenceError(
            "golden_reference_system_library_identity_unavailable"
        ) from exc
    prefixes = {
        "libc.so": "libc",
        "libm.so": "libm",
        "libstdc++.so": "libstdc++",
        "libgcc_s.so": "libgcc_s",
    }
    paths: dict[str, Path] = {}
    for line in lines:
        candidate = line.rsplit(maxsplit=1)[-1]
        if not candidate.startswith("/"):
            continue
        path = Path(candidate).resolve()
        for prefix, logical_name in prefixes.items():
            if path.name.startswith(prefix):
                previous = paths.get(logical_name)
                if previous is not None and previous != path:
                    raise GoldenReferenceError(
                        "golden_reference_system_library_identity_ambiguous"
                    )
                paths[logical_name] = path
    if "libc" not in paths or "libm" not in paths:
        raise GoldenReferenceError(
            "golden_reference_system_library_identity_unavailable"
        )
    return {
        logical_name: _binary_sha256(str(path))
        for logical_name, path in sorted(paths.items())
    }


def build_canonical_executor_fingerprint() -> dict[str, Any]:
    thread_environment = {key: os.environ.get(key) for key in EXECUTOR_THREAD_ENV_KEYS}
    if any(value != "1" for value in thread_environment.values()):
        raise GoldenReferenceError(
            "golden_reference_executor_requires_single_thread_environment"
        )
    hash_environment = {EXECUTOR_HASH_ENV_KEY: os.environ.get(EXECUTOR_HASH_ENV_KEY)}
    if hash_environment[EXECUTOR_HASH_ENV_KEY] != "0":
        raise GoldenReferenceError(
            "golden_reference_executor_requires_pythonhashseed_zero"
        )
    jit_environment = {
        key: value
        for key, value in sorted(os.environ.items())
        if key.startswith(EXECUTOR_JIT_ENV_PREFIXES)
    }
    if jit_environment:
        raise GoldenReferenceError(
            "golden_reference_executor_requires_unset_jit_environment"
        )
    ml_environment = {
        key: value
        for key, value in sorted(os.environ.items())
        if key.startswith(EXECUTOR_ML_ENV_PREFIXES)
    }
    if ml_environment:
        raise GoldenReferenceError(
            "golden_reference_executor_requires_unset_ml_environment"
        )
    numeric_environment = {
        key: value
        for key, value in sorted(os.environ.items())
        if key.startswith(EXECUTOR_NUMERIC_ENV_PREFIXES)
    }
    if numeric_environment != thread_environment:
        raise GoldenReferenceError(
            "golden_reference_executor_numeric_environment_not_canonical"
        )
    critical_binary_hashes = _critical_binary_sha256()
    jit_runtime = _jit_runtime_identity()
    ml_runtime = _machine_learning_runtime_identity()
    pools = threadpool_info()
    if (
        not isinstance(pools, list)
        or not pools
        or any(
            not isinstance(pool, Mapping) or pool.get("num_threads") != 1
            for pool in pools
        )
    ):
        raise GoldenReferenceError(
            "golden_reference_executor_threadpool_not_single_threaded"
        )
    threadpools = sorted(
        (
            {
                "user_api": pool.get("user_api"),
                "internal_api": pool.get("internal_api"),
                "prefix": pool.get("prefix"),
                "version": pool.get("version"),
                "num_threads": pool.get("num_threads"),
                "threading_layer": pool.get("threading_layer"),
                "architecture": pool.get("architecture"),
                "binary_sha256": _binary_sha256(pool.get("filepath")),
            }
            for pool in pools
        ),
        key=lambda pool: json.dumps(pool, sort_keys=True),
    )
    try:
        numpy_config = np.show_config(mode="dicts")
    except (TypeError, ValueError) as exc:
        raise GoldenReferenceError(
            "golden_reference_numpy_build_identity_unavailable"
        ) from exc
    if not isinstance(numpy_config, Mapping):
        raise GoldenReferenceError("golden_reference_numpy_build_identity_unavailable")
    build_dependencies = numpy_config.get("Build Dependencies", {})
    machine_information = numpy_config.get("Machine Information", {})
    simd_extensions = numpy_config.get("SIMD Extensions", {})
    blas = (
        build_dependencies.get("blas", {})
        if isinstance(build_dependencies, Mapping)
        else {}
    )
    host = (
        machine_information.get("host", {})
        if isinstance(machine_information, Mapping)
        else {}
    )
    if not all(isinstance(value, Mapping) for value in (blas, host)):
        raise GoldenReferenceError("golden_reference_numpy_build_identity_unavailable")
    libc_name, libc_version = platform.libc_ver()
    if (
        platform.python_implementation() != "CPython"
        or platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or sys.byteorder != "little"
        or libc_name != "glibc"
        or not libc_version
    ):
        raise GoldenReferenceError("golden_reference_executor_platform_not_canonical")
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-9-canonical-executor-fingerprint.v1",
        "artifact_type": "CanonicalExecutorFingerprint",
        "artifact_digest": "",
        "replay_scope": "same_canonical_executor_fingerprint_only",
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "build": sys.version,
            "compiler": platform.python_compiler(),
            "cache_tag": sys.implementation.cache_tag,
            "byteorder": sys.byteorder,
            "soabi": sysconfig.get_config_var("SOABI"),
            "py_debug": sysconfig.get_config_var("Py_DEBUG"),
            "math_module_kind": (
                "builtin" if getattr(math, "__file__", None) is None else "extension"
            ),
        },
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "libc_name": libc_name,
            "libc_version": libc_version,
        },
        "packages": {
            "joblib": version("joblib"),
            "llvmlite": version("llvmlite"),
            "narwhals": version("narwhals"),
            "numba": version("numba"),
            "numpy": np.__version__,
            "orjson": version("orjson"),
            "scipy": version("scipy"),
            "scikit_learn": version("scikit-learn"),
            "threadpoolctl": version("threadpoolctl"),
        },
        "distribution_record_sha256": {
            name: _distribution_record_sha256(name)
            for name in (
                "joblib",
                "llvmlite",
                "narwhals",
                "numba",
                "numpy",
                "orjson",
                "scipy",
                "scikit-learn",
                "threadpoolctl",
            )
        },
        "distribution_installed_tree_identity": {
            name: _distribution_installed_tree_identity(name)
            for name in (
                "joblib",
                "llvmlite",
                "narwhals",
                "numba",
                "numpy",
                "orjson",
                "scipy",
                "scikit-learn",
                "threadpoolctl",
            )
        },
        "critical_binary_sha256": critical_binary_hashes,
        "loaded_system_library_sha256": _loaded_system_library_sha256(),
        "jit_runtime": jit_runtime,
        "machine_learning_runtime": ml_runtime,
        "numpy_build": {
            "blas_name": blas.get("name"),
            "blas_version": blas.get("version"),
            "openblas_configuration": blas.get("openblas configuration"),
            "host_cpu": host.get("cpu"),
            "host_family": host.get("family"),
            "host_endian": host.get("endian"),
            "host_system": host.get("system"),
            "simd_extensions": (
                dict(simd_extensions) if isinstance(simd_extensions, Mapping) else {}
            ),
        },
        "thread_environment": thread_environment,
        "hash_environment": hash_environment,
        "jit_environment": jit_environment,
        "ml_environment": ml_environment,
        "numeric_environment": numeric_environment,
        "runtime_hash_probe": {
            "string_hash_decimal": str(
                hash("dehps.m4-p2-9.canonical-executor.hash-probe.v1")
            ),
            "bytes_hash_decimal": str(
                hash(b"dehps.m4-p2-9.canonical-executor.hash-probe.v1")
            ),
            "frozenset_iteration": list(
                frozenset(
                    {
                        "alpha-dehps",
                        "beta-m4",
                        "gamma-p2-9",
                        "delta-golden",
                    }
                )
            ),
        },
        "threadpools": threadpools,
        "worker_count": 1,
        "dependency_lock_status": (
            "runtime_fingerprint_required_repository_has_no_exact_python_lock"
        ),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2-9.canonical-executor-fingerprint.v1",
    )
    return payload


def build_golden_reference_plan_artifact(
    runtime_audit_plan: Mapping[str, Any],
    *,
    executor_fingerprint: Mapping[str, Any],
    construction_source_integrity_identity: Mapping[str, Any],
) -> dict[str, Any]:
    source_digest = str(runtime_audit_plan.get("artifact_digest") or "")
    if len(source_digest) != 64:
        raise GoldenReferenceError("golden_reference_source_plan_digest_missing")
    try:
        construction_source_identity = _validated_construction_source_identity(
            construction_source_integrity_identity
        )
        golden_source_contract = project_golden_source_integrity_contract(
            runtime_audit_plan.get("source_integrity_contract")
        )
        golden_source_identity = _validated_golden_source_identity(
            golden_source_identity_from_contract(golden_source_contract)
        )
    except RuntimeError as exc:
        raise GoldenReferenceError(
            f"golden_reference_source_integrity_contract_invalid:{exc}"
        ) from exc
    if any(
        construction_source_identity[key] != golden_source_identity[key]
        for key in (
            "shared_frozen_source_set_digest",
            "independent_oracle_source_set_digest",
        )
    ):
        raise GoldenReferenceError(
            "golden_reference_source_identity_projection_mismatch"
        )
    fingerprint = dict(executor_fingerprint)
    fingerprint_identity = dict(fingerprint)
    fingerprint_digest = fingerprint_identity.pop("artifact_digest", None)
    if (
        fingerprint.get("artifact_type") != "CanonicalExecutorFingerprint"
        or fingerprint_digest
        != canonical_digest(
            fingerprint_identity,
            domain="dehps.m4-p2-9.canonical-executor-fingerprint.v1",
        )
        or fingerprint.get("replay_scope") != "same_canonical_executor_fingerprint_only"
    ):
        raise GoldenReferenceError("golden_reference_executor_fingerprint_invalid")
    oracle_contract = runtime_audit_plan.get("oracle_contract")
    executor_contract = (
        oracle_contract.get("canonical_executor_fingerprint")
        if isinstance(oracle_contract, Mapping)
        else None
    )
    if (
        not isinstance(executor_contract, Mapping)
        or executor_contract.get("required_fingerprint_digest") != fingerprint_digest
    ):
        raise GoldenReferenceError(
            "golden_reference_executor_fingerprint_not_canonical"
        )
    boundary_identities = [
        dict(identity) for identity in golden_boundary_identity_contract()
    ]
    boundary_identity_schedule_digest = canonical_digest(
        boundary_identities,
        domain="dehps.m4-p2-9.golden-boundary-identity-schedule.v1",
    )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-9-golden-reference-plan.v1",
        "artifact_type": "GoldenReferencePlanArtifact",
        "artifact_digest": "",
        "source_runtime_audit_plan_digest": source_digest,
        "fixture_parent_execution_id": FIXTURE_PARENT_EXECUTION_ID,
        "fixture_source_git_commit": FIXTURE_GIT_COMMIT,
        "worker_count": 1,
        "executor_fingerprint": fingerprint,
        "executor_fingerprint_digest": fingerprint_digest,
        "construction_source_integrity_identity": construction_source_identity,
        "golden_source_integrity_contract": golden_source_contract,
        "golden_source_integrity_identity": golden_source_identity,
        "exact_replay_scope": "same_canonical_executor_fingerprint_only",
        "full_replicate": {
            "scale_id": "FORWARD_61",
            "scenario_id": "NULL_UNIFORM",
            "replicate_index": 0,
            "outer_fold_count": 61,
            "probe_order": list(PROBES),
        },
        "boundary_suite": {
            "replicate_index": 0,
            "scales": ["FORWARD_61", "HISTORICAL", "LONG"],
            "mechanisms": [
                "uniform_choose_6_without_replacement_from_33",
                "single_number_conditional_shift",
                "local_temporal_state",
                "pair_conditional_signal",
                "marginal_preserving_conditional_signal",
            ],
            "fold_positions": ["first", "middle", "last"],
            "identity_count": 45,
            "identity_schedule_digest": boundary_identity_schedule_digest,
            "identities": boundary_identities,
        },
        "equivalence_contract": {
            "golden_source_integrity_identity": "EXACT_THREE_DIGESTS",
            "construction_source_integrity_identity": (
                "PROVENANCE_ONLY_NOT_OPTIMIZED_EQUIVALENCE"
            ),
            "replicate_result_payload": "EXACT",
            "fold_trace_payload": "EXACT_BINARY64_BITS",
            "issue_metric_payload": "FULL_EXACT_BINARY64_BITS",
            "boundary_full_feature_view_payloads": ("EXACT_CANONICAL_PAYLOAD_DIGEST"),
            "artifact_digests": "EXACT",
            "checkpoint_journal_bytes": "EXACT_UTF8_LF",
            "first_mismatch_policy": "FAIL_CLOSED",
        },
        "oracle_contract": {
            "oracle_kind": "immutable_registered_golden_fixture",
            "immutable_golden_fixture_is_oracle": True,
            "acceleration_boundary_independent": True,
            "acceleration_boundary_independence_scope": (ACCELERATION_BOUNDARY_SCOPE),
            "oracle_construction_process_isolated": False,
            "oracle_construction_fully_implementation_independent": False,
            "shared_frozen_components": list(SHARED_FROZEN_COMPONENTS),
            "independent_acceleration_boundary_components": list(
                ACCELERATION_BOUNDARY_COMPONENTS
            ),
            "shared_component_change_policy": (
                "requires_new_reviewed_fixture_version_before_optimization"
            ),
            "future_acceleration_source_policy": (
                "superseding_runtime_plan_must_reuse_registered_golden_identity"
            ),
        },
        "oracle_dependency_denylist": [
            "StrictPriorFeatureCache",
            "ExactProbeRuntimeCache",
            "ReferenceReplicateEvaluator",
            "native_or_numba_metric_kernel",
        ],
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "production_action": "none",
        "parent_digests": sorted(
            {
                source_digest,
                *construction_source_identity.values(),
                *golden_source_identity.values(),
            }
        ),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2-9.phase0-golden-plan.v1",
    )
    return payload


def build_canonical_executor_event_attestation(
    runtime_audit_plan: Mapping[str, Any],
    *,
    executor_fingerprint: Mapping[str, Any],
    construction_source_integrity_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind the resolver event to a replayable canonical-host attestation."""

    source_digest = str(runtime_audit_plan.get("artifact_digest") or "")
    try:
        construction_source_identity = _validated_construction_source_identity(
            construction_source_integrity_identity
        )
    except RuntimeError as exc:
        raise GoldenReferenceError(
            f"golden_reference_source_integrity_contract_invalid:{exc}"
        ) from exc
    fingerprint = dict(executor_fingerprint)
    fingerprint_identity = dict(fingerprint)
    fingerprint_digest = fingerprint_identity.pop("artifact_digest", None)
    oracle_contract = runtime_audit_plan.get("oracle_contract")
    executor_contract = (
        oracle_contract.get("canonical_executor_fingerprint")
        if isinstance(oracle_contract, Mapping)
        else None
    )
    if (
        len(source_digest) != 64
        or fingerprint.get("artifact_type") != "CanonicalExecutorFingerprint"
        or fingerprint_digest
        != canonical_digest(
            fingerprint_identity,
            domain="dehps.m4-p2-9.canonical-executor-fingerprint.v1",
        )
        or fingerprint.get("replay_scope") != "same_canonical_executor_fingerprint_only"
        or fingerprint.get("worker_count") != 1
        or not isinstance(executor_contract, Mapping)
        or executor_contract.get("required_fingerprint_digest") != fingerprint_digest
    ):
        raise GoldenReferenceError(
            "golden_reference_canonical_executor_attestation_invalid"
        )
    event_key = f"m4-canonical-executor:{fingerprint_digest}"
    payload: dict[str, Any] = {
        "schema_version": ("dehps-m4-p2-9-canonical-executor-event-attestation.v1"),
        "artifact_type": "CanonicalExecutorEventAttestation",
        "artifact_digest": "",
        "status": "VERIFIED",
        "source_runtime_audit_plan_digest": source_digest,
        "construction_source_integrity_identity": construction_source_identity,
        "canonical_executor_fingerprint": fingerprint,
        "canonical_executor_fingerprint_digest": fingerprint_digest,
        "external_event": event_key,
        "exact_replay_scope": "same_canonical_executor_fingerprint_only",
        "worker_count": 1,
        "import_performed": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "production_action": "none",
        "promotion_gate_opened": False,
        "parent_digests": sorted(
            {
                source_digest,
                fingerprint_digest,
                *construction_source_identity.values(),
            }
        ),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2-9.canonical-executor-event-attestation.v1",
    )
    return payload


def golden_full_replicate(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
) -> AnalysisReplicate:
    cell = next(
        (
            item
            for item in build_cells(manifest, synthetic)
            if item.scale_id == "FORWARD_61" and item.scenario_id == "NULL_UNIFORM"
        ),
        None,
    )
    if cell is None or cell.outer_issue_count != 61:
        raise GoldenReferenceError("golden_reference_forward61_cell_missing")
    return build_replicate(
        cell=cell,
        replicate_index=0,
        parent_execution_id=FIXTURE_PARENT_EXECUTION_ID,
    )


def golden_boundary_identity_contract() -> tuple[dict[str, Any], ...]:
    scale_contracts = {
        "FORWARD_61": {
            "signal_strength": "WEAK",
            "prefix": "WEAK",
            "fold_count": 61,
        },
        "HISTORICAL": {
            "signal_strength": "WEAK",
            "prefix": "WEAK",
            "fold_count": 2581,
        },
        "LONG": {
            "signal_strength": "MEDIUM_PRACTICAL",
            "prefix": "MEDIUM_PRACTICAL",
            "fold_count": 6062,
        },
    }
    mechanism_contracts = {
        "uniform_choose_6_without_replacement_from_33": ("NULL_UNIFORM", "ZERO"),
        "single_number_conditional_shift": ("SINGLE_NUMBER", None),
        "local_temporal_state": ("LOCAL_TEMPORAL", None),
        "pair_conditional_signal": ("PAIR", None),
        "marginal_preserving_conditional_signal": ("MARGINAL_PRESERVING", None),
    }
    identities: list[dict[str, Any]] = []
    for scale_id, scale in scale_contracts.items():
        fold_count = int(scale["fold_count"])
        positions = {
            "first": 0,
            "middle": fold_count // 2,
            "last": fold_count - 1,
        }
        for mechanism, (scenario_suffix, fixed_strength) in mechanism_contracts.items():
            signal_strength = fixed_strength or str(scale["signal_strength"])
            scenario_id = (
                scenario_suffix
                if fixed_strength is not None
                else f"{scale['prefix']}_{scenario_suffix}"
            )
            for position, fold_index in positions.items():
                test_issue = 901 + fold_index
                identities.append(
                    {
                        "scale_id": scale_id,
                        "scenario_id": scenario_id,
                        "mechanism": mechanism,
                        "signal_strength": signal_strength,
                        "replicate_index": 0,
                        "fold_position": position,
                        "fold_index": fold_index,
                        "train_start_issue": 1,
                        "train_end_issue": test_issue - 1,
                        "test_issue": test_issue,
                    }
                )
    return tuple(identities)


def full_train_feature_view_payload_digest(view: TrainFeatureView) -> str:
    return canonical_digest(
        {
            "view_type": "TrainFeatureView",
            "issue_ids": list(view.issue_ids),
            "red_numbers": list(view.red_numbers),
            "feature_names": list(view.feature_names),
            "values": [list(row) for row in view.values],
            "targets": list(view.targets),
            "available_through_by_issue": [
                list(item) for item in view.available_through_by_issue
            ],
            "construction_start_issue": view.construction_start_issue,
            "construction_end_issue": view.construction_end_issue,
            "feature_manifest_digest": view.feature_manifest_digest,
            "feature_view_digest": view.feature_view_digest,
        },
        domain="dehps.m4-p2-9.full-train-feature-view-payload.v1",
    )


def full_blind_feature_view_payload_digest(view: BlindTestFeatureView) -> str:
    return canonical_digest(
        {
            "view_type": "BlindTestFeatureView",
            "target_issue": view.target_issue,
            "red_numbers": list(view.red_numbers),
            "feature_names": list(view.feature_names),
            "values": [list(row) for row in view.values],
            "available_through_issue": view.available_through_issue,
            "construction_start_issue": view.construction_start_issue,
            "construction_end_issue": view.construction_end_issue,
            "feature_manifest_digest": view.feature_manifest_digest,
            "feature_view_digest": view.feature_view_digest,
        },
        domain="dehps.m4-p2-9.full-blind-feature-view-payload.v1",
    )


def build_reference_boundary_snapshots(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    truth_by_scenario: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    cells = {
        (cell.scale_id, cell.scenario_id): cell
        for cell in build_cells(manifest, synthetic)
    }
    snapshots: list[dict[str, Any]] = []
    active_key: tuple[str, str] | None = None
    active: (
        tuple[Any, AnalysisReplicate, SyntheticDataset, PythonReferenceBackend] | None
    ) = None
    for identity in golden_boundary_identity_contract():
        key = (str(identity["scale_id"]), str(identity["scenario_id"]))
        cell = cells.get(key)
        if cell is None:
            raise GoldenReferenceError("golden_reference_boundary_cell_missing")
        if key != active_key:
            replicate = build_replicate(
                cell=cell,
                replicate_index=0,
                parent_execution_id=FIXTURE_PARENT_EXECUTION_ID,
            )
            truth = truth_by_scenario.get(cell.scenario_id)
            dataset = generate_evaluation_dataset(
                replicate,
                synthetic=synthetic,
                truth_artifact=truth,
                expose_prior_state=True,
            )
            backend = PythonReferenceBackend(dataset)
            active = (cell, replicate, dataset, backend)
            active_key = key
        if active is None:
            raise GoldenReferenceError("golden_reference_boundary_state_missing")
        cell, replicate, dataset, backend = active
        fold_index = int(identity["fold_index"])
        test_issue = int(identity["test_issue"])
        if (
            dataset.outer_evaluation_length != cell.outer_issue_count
            or fold_index < 0
            or fold_index >= dataset.outer_evaluation_length
            or test_issue != dataset.minimum_training_length + fold_index + 1
            or identity["train_start_issue"] != 1
            or identity["train_end_issue"] != test_issue - 1
            or cell.mechanism != identity["mechanism"]
            or cell.signal_strength != identity["signal_strength"]
        ):
            raise GoldenReferenceError(
                "golden_reference_boundary_identity_contract_changed"
            )
        # Construct only the three preregistered boundary folds.  Materializing
        # every expanding LONG fold would allocate tens of millions of issue
        # references even though the intervening folds are not part of Phase 0.
        fold = OuterFold(tuple(range(1, test_issue)), test_issue)
        validate_outer_fold(
            fold,
            minimum_training_issues=dataset.minimum_training_length,
            dataset_issue_count=dataset.issue_count,
        )
        training = backend.training_view(available_through_issue=fold.train_issues[-1])
        train = backend.build_train_feature_view(training, fold.train_issues)
        blind = backend.build_blind_test_feature_view(target_issue=fold.test_issue)
        snapshots.append(
            {
                "scale_id": key[0],
                "scenario_id": key[1],
                "mechanism": cell.mechanism,
                "signal_strength": cell.signal_strength,
                "replicate_index": replicate.replicate_index,
                "replicate_digest": replicate.artifact_digest,
                "dataset_digest": dataset.artifact_digest,
                "fold_position": identity["fold_position"],
                "fold_index": fold_index,
                "train_start_issue": fold.train_issues[0],
                "train_end_issue": fold.train_issues[-1],
                "test_issue": fold.test_issue,
                "train_feature_view_digest": train.feature_view_digest,
                "blind_feature_view_digest": blind.feature_view_digest,
                "train_feature_view_payload_digest": (
                    full_train_feature_view_payload_digest(train)
                ),
                "blind_feature_view_payload_digest": (
                    full_blind_feature_view_payload_digest(blind)
                ),
            }
        )
    if len(snapshots) != 45:
        raise GoldenReferenceError("golden_reference_boundary_snapshot_count_changed")
    _validate_boundary_snapshots(snapshots)
    return tuple(snapshots)


class PythonReferenceReplicateEvaluator:
    """Cache/evaluator-independent constructor for the immutable fixture.

    Frozen generator, estimator, metric, and resampling primitives are shared;
    the registered fixture, not this constructor alone, is the runtime oracle.
    """

    def __init__(
        self,
        *,
        manifest: MeasurementValidationManifest,
        synthetic: SyntheticRunManifest,
        inputs: PythonReferenceInputs,
        output_dir: Path,
        periodic_refit_contract: Any | None = None,
    ) -> None:
        self.manifest = manifest
        self.synthetic = synthetic
        self.inputs = inputs
        self.output_dir = output_dir
        self.periodic_refit_contract = periodic_refit_contract
        require_repaired_manifest(manifest.payload.get("phase"))
        if inputs.resampling.artifact_digest != RESAMPLING_KERNEL_DIGEST:
            raise GoldenReferenceError("golden_reference_resampling_digest_changed")
        if inputs.walk_forward_harness.artifact_digest != WALK_FORWARD_HARNESS_DIGEST:
            raise GoldenReferenceError("golden_reference_harness_digest_changed")
        if (
            inputs.preregistration.get("artifact_digest") != PREREGISTRATION_DIGEST
            or preregistration_digest(inputs.preregistration) != PREREGISTRATION_DIGEST
        ):
            raise GoldenReferenceError("golden_reference_preregistration_changed")
        if tuple(manifest.payload["workload"]["probe_allowlist"]) != PROBES:
            raise GoldenReferenceError("golden_reference_probe_order_changed")

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
        fixture_git_commit: str,
        output_dir: Path,
        periodic_refit_contract: Any | None = None,
    ) -> PythonReferenceReplicateEvaluator:
        return cls(
            manifest=manifest,
            synthetic=synthetic,
            inputs=PythonReferenceInputs(
                preregistration=_load_json_object(preregistration_path),
                walk_forward_harness=load_harness_manifest(walk_forward_harness_path),
                resampling=load_resampling_manifest(resampling_path),
                truth_by_scenario=truth_by_scenario,
                fixture_git_commit=fixture_git_commit,
            ),
            output_dir=output_dir,
            periodic_refit_contract=periodic_refit_contract,
        )

    def evaluate(self, replicate: AnalysisReplicate) -> PythonReferenceEvaluation:
        if (
            replicate.cell.scale_id != "FORWARD_61"
            or replicate.cell.scenario_id != "NULL_UNIFORM"
            or replicate.cell.outer_issue_count != 61
        ):
            raise GoldenReferenceError(
                "golden_reference_full_replicate_must_be_forward61_null"
            )
        truth = self.inputs.truth_by_scenario.get(replicate.cell.scenario_id)
        dataset = generate_evaluation_dataset(
            replicate,
            synthetic=self.synthetic,
            truth_artifact=truth,
            expose_prior_state=True,
        )
        backend = PythonReferenceBackend(dataset)
        folds = backend.outer_folds()
        if len(folds) != 61:
            raise GoldenReferenceError("golden_reference_fold_count_changed")
        configs = self._probe_configs()
        checkpoint_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        settlement_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        state_digests: dict[str, list[str]] = {probe: [] for probe in PROBES}
        issue_gains: dict[str, list[float]] = {probe: [] for probe in PROBES}
        gate_probabilities: list[tuple[float, ...]] = []
        ordered_targets: list[tuple[int, ...]] = []
        fold_traces: list[dict[str, Any]] = []
        journal = LiteralCheckpointJournal(
            output_dir=self.output_dir,
            replicate=replicate,
        )
        prepared_learned: dict[str, Any] = {}

        def checkpoint_callback(
            *,
            fold_index_value: int,
            checkpoint_for_fold: dict[str, str],
        ) -> Any:
            def before_target(**context: Any) -> None:
                fold_value = context["fold"]
                predictions = context["predictions"]
                prepared_by_probe = context["prepared_by_probe"]
                for probe_id in PROBES:
                    probability = predictions[probe_id]
                    state = prepared_by_probe[probe_id].state
                    checkpoint_identity = {
                        "dataset_digest": dataset.artifact_digest,
                        "scale_id": replicate.cell.scale_id,
                        "scenario_id": replicate.cell.scenario_id,
                        "replicate_index": replicate.replicate_index,
                        "probe_id": probe_id,
                        "train_start_issue": fold_value.train_issues[0],
                        "train_end_issue": fold_value.train_issues[-1],
                        "test_issue": fold_value.test_issue,
                        "probe_state_digest": state.state_digest,
                        "probabilities": list(probability),
                        "probability_order": "red_numbers_1_to_33",
                        "target_access": "forbidden_before_this_checkpoint",
                        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
                        "git_commit": self.inputs.fixture_git_commit,
                    }
                    digest = canonical_digest(
                        checkpoint_identity,
                        domain="dehps.m4-p2.formal-prediction-checkpoint.v1",
                    )
                    checkpoint_digests[probe_id].append(digest)
                    state_digests[probe_id].append(state.state_digest)
                    checkpoint_for_fold[probe_id] = digest
                journal.record(
                    fold_index=fold_index_value,
                    test_issue=fold_value.test_issue,
                    checkpoint_digests=checkpoint_for_fold,
                )

            return before_target

        for fold_index, fold in enumerate(folds):
            checkpoint_for_fold: dict[str, str] = {}
            policy = self.periodic_refit_contract
            refit_learned = (
                policy is None
                or not prepared_learned
                or policy.is_refit_boundary(fold_index)
            )

            trace = backend.evaluate_fold(
                fold=fold,
                probe_configs=configs,
                prepared_learned=prepared_learned,
                refit_learned=refit_learned,
                before_target=checkpoint_callback(
                    fold_index_value=fold_index,
                    checkpoint_for_fold=checkpoint_for_fold,
                ),
            )
            target = dataset.issue(fold.test_issue).target_vector
            ordered_targets.append(target)
            trace_probes = dict(trace["probes"])
            for probe_id in PROBES:
                metric = trace_probes[probe_id]["issue_metric"]
                settlement_identity = {
                    "prediction_checkpoint_digest": checkpoint_for_fold[probe_id],
                    "target_digest": trace["target_digest"],
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                    "PE1_bits_per_issue": metric[
                        "observed_log_loss_gain_bits_per_issue"
                    ],
                }
                settlement = canonical_digest(
                    settlement_identity,
                    domain="dehps.m4-p2.formal-fold-settlement.v1",
                )
                settlement_digests[probe_id].append(settlement)
                issue_gains[probe_id].append(
                    metric["observed_log_loss_gain_bits_per_issue"]
                )
                trace_probes[probe_id] = {
                    **trace_probes[probe_id],
                    "prediction_checkpoint_digest": checkpoint_for_fold[probe_id],
                    "settlement_digest": settlement,
                }
            gate_probabilities.append(
                tuple(trace_probes["REGULARIZED_LOGISTIC_REGRESSION"]["probabilities"])
            )
            fold_traces.append(
                {
                    "fold_index": fold_index,
                    **(
                        {
                            "learned_probe_refit_boundary_fold_index": (
                                policy.boundary_fold_index(fold_index)
                            )
                        }
                        if policy is not None
                        else {}
                    ),
                    **trace,
                    "target_vector": list(target),
                    "probes": trace_probes,
                }
            )

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
        pe1_values = tuple(issue_gains["REGULARIZED_LOGISTIC_REGRESSION"])
        bootstrap_runner = (
            moving_block_bootstrap_statistics
            if self.periodic_refit_contract is None
            else moving_block_bootstrap_statistics_exact_runtime
        )
        bootstrap, bootstrap_seeds = bootstrap_runner(
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
            return float(_literal_permutation_pe1(probability_matrix, permuted).mean())

        permutation_runner = (
            block_permutation_statistics
            if self.periodic_refit_contract is None
            else block_permutation_statistics_exact_runtime
        )
        permutation, permutation_seeds = permutation_runner(
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
        journal_digest, journal_count, journal_bytes = journal.finalize(
            expected_fold_count=len(folds)
        )
        truth_bits = (
            0.0
            if truth is None
            else float(truth["marginal_information_bits_per_issue"])
        )
        result: dict[str, Any] = {
            **replicate.to_dict(),
            "status": "COMPLETE",
            "measurement_validation_manifest_digest": self.manifest.artifact_digest,
            "dataset_digest": dataset.artifact_digest,
            "truth_artifact_digest": dataset.raw_payload["truth_artifact_digest"],
            "truth_bits_per_issue": truth_bits,
            "truth_estimand": "marginal_information_bits_per_issue",
            "scenario_role": replicate.cell.scenario_role,
            "formal_power_eligible": replicate.cell.formal_power_eligible,
            "negative_control_id": "NC6_SYNTHETIC_NULL",
            "negative_control_replicate_index": replicate.replicate_index,
            "probe_run_digests": probe_run_digests,
            "ordered_outer_checkpoint_digest": ordered_checkpoint_digest,
            "ordered_settlement_digest": ordered_settlement_digest,
            "checkpoint_journal_digest": journal_digest,
            "checkpoint_journal_entry_count": journal_count,
            "checkpoint_journal_path": str(journal.path.relative_to(self.output_dir)),
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
            "gate_probe": "REGULARIZED_LOGISTIC_REGRESSION",
            "metric_kernel_digest": METRIC_KERNEL_DIGEST,
            "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
            "resampling_kernel_digest": RESAMPLING_KERNEL_DIGEST,
            "git_commit": self.inputs.fixture_git_commit,
            "working_tree_clean": True,
            "real_history_used": False,
            "production_action": "none",
        }
        return PythonReferenceEvaluation(
            result_payload=result,
            fold_traces=tuple(fold_traces),
            checkpoint_journal_bytes=journal_bytes,
        )

    def _probe_configs(self) -> dict[str, Mapping[str, Any]]:
        configs = deepcopy(
            self.inputs.preregistration["probe_models"]["hyperparameters"]
        )
        frozen = self.manifest.payload["frozen_probe_configs"]
        selection_digest = self.manifest.payload[
            "development_selection_artifact_digest"
        ]
        configs["REGULARIZED_LOGISTIC_REGRESSION"] = dict(
            self.inputs.walk_forward_harness.probe("REGULARIZED_LOGISTIC_REGRESSION")
        )
        configs["REGULARIZED_LOGISTIC_REGRESSION"].update(
            {
                "selection_mode": "frozen_development",
                "selected_C": frozen["REGULARIZED_LOGISTIC_REGRESSION"]["selected_C"],
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
                "max_depth": [frozen["SHALLOW_CALIBRATED_TREE"]["selected_max_depth"]],
                "min_samples_leaf": [
                    frozen["SHALLOW_CALIBRATED_TREE"]["selected_min_samples_leaf"]
                ],
                "development_selection_digest": selection_digest,
            }
        )
        return configs


def _is_lower_hex_digest(value: object, *, length: int = 64) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _validated_fixture_journal(
    evaluation: PythonReferenceEvaluation,
) -> tuple[dict[str, Any], ...]:
    raw = evaluation.checkpoint_journal_bytes
    if not raw or not raw.endswith(b"\n") or b"\r" in raw:
        raise GoldenReferenceError("golden_reference_fixture_journal_not_utf8_lf")
    try:
        text = raw.decode("utf-8")
        entries = tuple(json.loads(line) for line in text.splitlines())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GoldenReferenceError("golden_reference_fixture_journal_invalid") from exc
    if (
        len(entries) != 61
        or any(not isinstance(entry, dict) for entry in entries)
        or canonical_journal_bytes(entries) != raw
    ):
        raise GoldenReferenceError("golden_reference_fixture_journal_invalid")
    return entries


def _validate_probe_state(
    state: object,
    *,
    probe_id: str,
    training_end_issue: int,
) -> bool:
    return bool(
        isinstance(state, Mapping)
        and set(state) == PROBE_STATE_KEYS
        and state.get("probe_id") == probe_id
        and state.get("training_start_issue") == 1
        and state.get("training_end_issue") == training_end_issue
        and state.get("training_issue_count") == training_end_issue
        and state.get("training_row_count") == training_end_issue * 33
        and state.get("feature_manifest_digest")
        == STATE_VISIBLE_FEATURE_MANIFEST_DIGEST
        and _is_lower_hex_digest(state.get("state_digest"))
    )


def _validate_issue_metric(
    metric: object,
    *,
    target: list[int],
    probabilities: list[Real],
    test_issue: int,
) -> bool:
    if not isinstance(metric, Mapping) or set(metric) != ISSUE_METRIC_KEYS:
        return False
    events = metric.get("number_events")
    baseline_clip = metric.get("baseline_clip_diagnostics")
    probe_clip = metric.get("probe_clip_diagnostics")
    if (
        metric.get("schema_version") != ISSUE_SCHEMA_VERSION
        or metric.get("issue_id") != str(test_issue)
        or metric.get("cluster_id") != str(test_issue)
        or metric.get("baseline_identity") != BASELINE_IDENTITY
        or metric.get("probability_epsilon") != PROBABILITY_EPSILON
        or metric.get("actual_red_count") != 6
        or metric.get("eligible_for_pe1") is not True
        or metric.get("eligible_for_final_pe2") is not False
        or metric.get("gain_direction")
        not in {"positive_probe_better", "negative_probe_worse", "zero_equal"}
        or not isinstance(baseline_clip, Mapping)
        or set(baseline_clip) != CLIP_DIAGNOSTIC_KEYS
        or baseline_clip.get("epsilon") != PROBABILITY_EPSILON
        or not isinstance(probe_clip, Mapping)
        or set(probe_clip) != CLIP_DIAGNOSTIC_KEYS
        or probe_clip.get("epsilon") != PROBABILITY_EPSILON
        or not isinstance(events, list)
        or len(events) != 33
    ):
        return False
    for red_number, event in enumerate(events, start=1):
        if (
            not isinstance(event, Mapping)
            or set(event) != NUMBER_EVENT_METRIC_KEYS
            or event.get("schema_version") != NUMBER_EVENT_SCHEMA_VERSION
            or event.get("issue_id") != str(test_issue)
            or event.get("cluster_id") != str(test_issue)
            or event.get("red_number") != red_number
            or event.get("target") != target[red_number - 1]
            or event.get("probe_raw_probability") != probabilities[red_number - 1]
        ):
            return False
    return True


def _validate_fixture_evaluation(
    *,
    replicate: AnalysisReplicate,
    evaluation: PythonReferenceEvaluation,
) -> None:
    if (
        replicate.cell.scale_id != "FORWARD_61"
        or replicate.cell.scenario_id != "NULL_UNIFORM"
        or replicate.cell.outer_issue_count != 61
        or replicate.replicate_index != 0
        or replicate.parent_execution_id != FIXTURE_PARENT_EXECUTION_ID
    ):
        raise GoldenReferenceError("golden_reference_fixture_replicate_changed")
    result = evaluation.result_payload
    for key, expected in replicate.to_dict().items():
        if result.get(key) != expected:
            raise GoldenReferenceError(
                f"golden_reference_fixture_result_identity_mismatch:{key}"
            )
    if (
        result.get("status") != "COMPLETE"
        or result.get("actual_outer_fold_count") != 61
        or result.get("checkpoint_journal_entry_count") != 61
        or result.get("number_probability_predictions") != 61 * 33 * len(PROBES)
        or result.get("git_commit") != FIXTURE_GIT_COMMIT
        or not _is_lower_hex_digest(result.get("dataset_digest"))
        or result.get("metric_kernel_digest") != METRIC_KERNEL_DIGEST
        or result.get("walk_forward_harness_digest") != WALK_FORWARD_HARNESS_DIGEST
        or result.get("resampling_kernel_digest") != RESAMPLING_KERNEL_DIGEST
    ):
        raise GoldenReferenceError("golden_reference_fixture_result_incomplete")
    periodic = "measurement_update_policy_digest" in result
    if periodic and (
        result.get("measurement_update_policy_digest")
        != P263_PERIODIC_REFIT_CONTRACT_DIGEST
        or result.get("learned_probe_refit_interval_folds") != 64
        or result.get("learned_probe_refit_boundary_count") != 1
        or result.get("empirical_baseline_update_count") != 61
    ):
        raise GoldenReferenceError("golden_reference_periodic_refit_contract_changed")
    traces = evaluation.fold_traces
    entries = _validated_fixture_journal(evaluation)
    if len(traces) != 61:
        raise GoldenReferenceError("golden_reference_fixture_fold_count_changed")
    expected_journal_digest = canonical_digest(
        entries,
        domain="dehps.m4-p2.strict-prior-checkpoint-journal.v1",
    )
    if result.get("checkpoint_journal_digest") != expected_journal_digest:
        raise GoldenReferenceError("golden_reference_fixture_journal_digest_changed")
    for fold_index, (trace, entry) in enumerate(zip(traces, entries, strict=True)):
        if not isinstance(trace, Mapping):
            raise GoldenReferenceError("golden_reference_fixture_fold_invalid")
        test_issue = trace.get("test_issue")
        checkpoint_digests = entry.get("checkpoint_digests")
        probes = trace.get("probes")
        target = trace.get("target_vector")
        expected_test_issue = 901 + fold_index
        if (
            trace.get("fold_index") != fold_index
            or test_issue != expected_test_issue
            or trace.get("train_start_issue") != 1
            or trace.get("train_end_issue") != test_issue - 1
            or not _is_lower_hex_digest(trace.get("train_feature_view_digest"))
            or not _is_lower_hex_digest(trace.get("blind_feature_view_digest"))
            or entry.get("fold_index") != fold_index
            or entry.get("test_issue") != test_issue
            or entry.get("probe_order") != list(PROBES)
            or entry.get("schema_version")
            != "dehps-m4-p2-strict-prior-checkpoint-journal-entry.v1"
            or entry.get("target_access") != "forbidden_before_this_persisted_entry"
            or not isinstance(checkpoint_digests, Mapping)
            or set(checkpoint_digests) != set(PROBES)
            or not isinstance(probes, Mapping)
            or set(probes) != set(PROBES)
            or not isinstance(target, list)
            or len(target) != 33
            or any(value not in (0, 1) for value in target)
            or sum(target) != 6
            or trace.get("target_digest")
            != canonical_digest(
                target,
                domain="dehps.m4-p2.formal-fold-target.v1",
            )
        ):
            raise GoldenReferenceError(
                f"golden_reference_fixture_fold_invalid:{fold_index}"
            )
        for probe_id in PROBES:
            probe = probes[probe_id]
            probabilities = (
                probe.get("probabilities") if isinstance(probe, Mapping) else None
            )
            state = probe.get("probe_state") if isinstance(probe, Mapping) else None
            metric = probe.get("issue_metric") if isinstance(probe, Mapping) else None
            if (
                not _is_lower_hex_digest(checkpoint_digests.get(probe_id))
                or not isinstance(probe, Mapping)
                or probe.get("prediction_checkpoint_digest")
                != checkpoint_digests[probe_id]
                or not _is_lower_hex_digest(probe.get("settlement_digest"))
                or not isinstance(probabilities, list)
                or len(probabilities) != 33
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, Real)
                    or not math.isfinite(float(value))
                    for value in probabilities
                )
                or not _validate_probe_state(
                    state,
                    probe_id=probe_id,
                    training_end_issue=(
                        test_issue - 1
                        if not periodic or probe_id == "EMPIRICAL_BASELINE"
                        else 900 + fold_index - fold_index % 64
                    ),
                )
                or not _validate_issue_metric(
                    metric,
                    target=target,
                    probabilities=probabilities,
                    test_issue=test_issue,
                )
            ):
                raise GoldenReferenceError(
                    f"golden_reference_fixture_probe_invalid:{fold_index}:{probe_id}"
                )
            checkpoint_identity = {
                "dataset_digest": result["dataset_digest"],
                "scale_id": replicate.cell.scale_id,
                "scenario_id": replicate.cell.scenario_id,
                "replicate_index": replicate.replicate_index,
                "probe_id": probe_id,
                "train_start_issue": 1,
                "train_end_issue": test_issue - 1,
                "test_issue": test_issue,
                "probe_state_digest": state["state_digest"],
                "probabilities": probabilities,
                "probability_order": "red_numbers_1_to_33",
                "target_access": "forbidden_before_this_checkpoint",
                "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
                "git_commit": FIXTURE_GIT_COMMIT,
            }
            expected_checkpoint = canonical_digest(
                checkpoint_identity,
                domain="dehps.m4-p2.formal-prediction-checkpoint.v1",
            )
            expected_settlement = canonical_digest(
                {
                    "prediction_checkpoint_digest": expected_checkpoint,
                    "target_digest": trace["target_digest"],
                    "metric_kernel_digest": METRIC_KERNEL_DIGEST,
                    "PE1_bits_per_issue": metric[
                        "observed_log_loss_gain_bits_per_issue"
                    ],
                },
                domain="dehps.m4-p2.formal-fold-settlement.v1",
            )
            if (
                checkpoint_digests[probe_id] != expected_checkpoint
                or probe["settlement_digest"] != expected_settlement
            ):
                raise GoldenReferenceError(
                    f"golden_reference_fixture_digest_binding_invalid:"
                    f"{fold_index}:{probe_id}"
                )


def _validate_boundary_snapshots(
    boundary_snapshots: Sequence[Mapping[str, Any]],
) -> None:
    expected = {
        (
            identity["scale_id"],
            identity["mechanism"],
            identity["fold_position"],
        ): identity
        for identity in golden_boundary_identity_contract()
    }
    snapshot_keys = {
        "scale_id",
        "scenario_id",
        "mechanism",
        "signal_strength",
        "replicate_index",
        "replicate_digest",
        "dataset_digest",
        "fold_position",
        "fold_index",
        "train_start_issue",
        "train_end_issue",
        "test_issue",
        "train_feature_view_digest",
        "blind_feature_view_digest",
        "train_feature_view_payload_digest",
        "blind_feature_view_payload_digest",
    }
    actual: set[tuple[object, object, object]] = set()
    for snapshot in boundary_snapshots:
        key = (
            snapshot.get("scale_id"),
            snapshot.get("mechanism"),
            snapshot.get("fold_position"),
        )
        actual.add(key)
        expected_identity = expected.get(key)
        if (
            set(snapshot) != snapshot_keys
            or expected_identity is None
            or any(
                snapshot.get(field) != expected_identity[field]
                for field in expected_identity
            )
            or any(
                not _is_lower_hex_digest(snapshot.get(key))
                for key in (
                    "replicate_digest",
                    "dataset_digest",
                    "train_feature_view_digest",
                    "blind_feature_view_digest",
                    "train_feature_view_payload_digest",
                    "blind_feature_view_payload_digest",
                )
            )
        ):
            raise GoldenReferenceError("golden_reference_boundary_snapshot_invalid")
    if actual != set(expected) or len(boundary_snapshots) != len(expected):
        raise GoldenReferenceError("golden_reference_boundary_snapshot_set_changed")


def build_golden_fixture_artifact(
    *,
    plan_digest: str,
    executor_fingerprint_digest: str,
    golden_source_integrity_identity: Mapping[str, Any],
    replicate: AnalysisReplicate,
    evaluation: PythonReferenceEvaluation,
    boundary_snapshots: Sequence[Mapping[str, Any]] = (),
    parent_digests: Sequence[str] = (),
) -> dict[str, Any]:
    if (
        not _is_lower_hex_digest(plan_digest)
        or not _is_lower_hex_digest(executor_fingerprint_digest)
        or any(not _is_lower_hex_digest(value) for value in parent_digests)
    ):
        raise GoldenReferenceError("golden_reference_fixture_parent_invalid")
    golden_source_identity = _validated_golden_source_identity(
        golden_source_integrity_identity
    )
    _validate_fixture_evaluation(replicate=replicate, evaluation=evaluation)
    _validate_boundary_snapshots(boundary_snapshots)
    raw = {
        "schema_version": GOLDEN_REFERENCE_SCHEMA,
        "artifact_type": "Phase0GoldenReferenceFixture.v1",
        "artifact_digest": "",
        "benchmark_plan_digest": plan_digest,
        "executor_fingerprint_digest": executor_fingerprint_digest,
        "golden_source_integrity_identity": golden_source_identity,
        "exact_replay_scope": "same_canonical_executor_fingerprint_only",
        "float_encoding": FLOAT64_ENCODING,
        "fixture_input": {
            "scale_id": replicate.cell.scale_id,
            "scenario_id": replicate.cell.scenario_id,
            "replicate_index": replicate.replicate_index,
            "parent_execution_id": replicate.parent_execution_id,
            "power_replicate_seed_decimal": str(replicate.power_replicate_seed),
            "power_replicate_seed_digest": replicate.power_replicate_seed_digest,
            "evaluation_dataset_seed_decimal": str(replicate.evaluation_dataset_seed),
            "evaluation_dataset_seed_digest": (
                replicate.evaluation_dataset_seed_digest
            ),
        },
        "replicate_result": dict(evaluation.result_payload),
        "fold_traces": [dict(item) for item in evaluation.fold_traces],
        "boundary_snapshots": [dict(item) for item in boundary_snapshots],
        "checkpoint_journal_utf8": evaluation.checkpoint_journal_bytes.decode("utf-8"),
        "checkpoint_journal_bytes_sha256": journal_bytes_sha256(
            evaluation.checkpoint_journal_bytes
        ),
        "oracle_kind": "immutable_registered_golden_fixture",
        "immutable_golden_fixture_is_oracle": True,
        "acceleration_boundary_independent": True,
        "acceleration_boundary_independence_scope": ACCELERATION_BOUNDARY_SCOPE,
        "oracle_construction_process_isolated": False,
        "oracle_construction_fully_implementation_independent": False,
        "shared_frozen_components": list(SHARED_FROZEN_COMPONENTS),
        "independent_acceleration_boundary_components": list(
            ACCELERATION_BOUNDARY_COMPONENTS
        ),
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "production_action": "none",
        "parent_digests": sorted(
            {plan_digest, *parent_digests, *golden_source_identity.values()}
        ),
    }
    encoded = encode_float64_tree(raw)
    encoded["artifact_digest"] = canonical_digest(
        {key: value for key, value in encoded.items() if key != "artifact_digest"},
        domain="dehps.m4-p2-9.phase0-golden-fixture.v1",
    )
    assert_float64_tree(encoded)
    return encoded


def require_repaired_manifest(manifest_phase: object) -> None:
    if manifest_phase != "M4-P2.6.1":
        raise MeasurementValidationContractError(
            "golden_reference_requires_repaired_contract",
            "Phase 0 oracle is bound only to the repaired P2.6.1 contract",
        )
