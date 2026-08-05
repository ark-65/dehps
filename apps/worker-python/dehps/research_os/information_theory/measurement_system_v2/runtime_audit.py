from __future__ import annotations

import json
import platform
import re
import resource
import time
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_validation.golden_reference import (
    ACCELERATION_BOUNDARY_COMPONENTS,
    SHARED_FROZEN_COMPONENTS,
)
from dehps.research_os.information_theory.measurement_validation.source_integrity import (
    SourceIntegrityError,
    encode_float64_tree,
    float64_tree_digest,
    validate_source_integrity_contract,
)

RUNTIME_AUDIT_PLAN_PATH = Path(
    "configs/research-os/m4-p2-9-measurement-runtime-audit-plan-v1.1.5.json"
)
UNAVAILABLE = "UNAVAILABLE"
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_REQUIRED_EXECUTOR_FINGERPRINT_DIGEST = (
    "e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32"
)
_EXECUTOR_FINGERPRINT_DIMENSIONS = (
    "python_implementation_version_cache_tag_byteorder",
    "CPython_build_ABI_and_binary_sha256",
    (
        "exact_numerical_runtime_packages_versions_joblib_llvmlite_narwhals_"
        "numba_numpy_orjson_scipy_scikit_learn_threadpoolctl"
    ),
    "distribution_RECORD_sha256_for_nine_exact_numerical_runtime_packages",
    "installed_tree_digest_for_nine_exact_numerical_runtime_packages_excluding_pyc",
    "critical_numeric_ML_JIT_native_extension_cluster_sha256",
    "LLVM_version_triples_host_cpu_and_features",
    "Numba_codegen_configuration",
    "NUMBA_LLVMLITE_environment_unset",
    "sklearn_config_and_joblib_active_backend_effective_n_jobs",
    "JOBLIB_LOKY_SKLEARN_environment_unset",
    "numeric_environment_exactly_canonical_thread_environment",
    "linux_machine_libc",
    "loaded_libc_libm_libstdcxx_libgcc_binary_sha256",
    "numpy_blas_host_simd_identity",
    "OMP_OPENBLAS_MKL_NUMEXPR_thread_environment",
    "PYTHONHASHSEED_zero_at_process_start",
    "runtime_hash_secret_probe",
    "threadpoolctl_runtime_pool_identity_and_num_threads",
    "threadpool_binary_sha256",
)
_EXECUTION_POLICY = {
    "while_p2_6_1_running": "SINGLE_WORKER_CORRECTNESS_SMOKE_ONLY",
    "formal_benchmark": "AFTER_M4_RUNTIME_SLOT_P2_6_1_RELEASED",
    "worker_count": 1,
    "reference_evaluator_is_oracle": False,
    "immutable_golden_fixture_is_oracle": True,
    "oracle_construction_fully_implementation_independent": False,
    "acceleration_boundary_independent": True,
    "acceleration_boundary_independence_scope": (
        "literal_behavior_path_and_fresh_import_closure"
    ),
    "oracle_construction_process_isolated": False,
    "exact_replay_scope": "same_canonical_executor_fingerprint_only",
    "cross_executor_policy": "requires_new_reviewed_fixture_before_exact_claim",
    "optimization_backend_modification_allowed": False,
    "measured_workload": "production_like_trace_capture_disabled",
    "correctness_replay": "out_of_band_trace_capture_enabled",
    "benchmark_attempt_policy": "fresh_attempt_scoped_workdirs_no_journal_reuse",
}
_OBSERVED_PHASES = (
    "dataset_generation",
    "fold_construction",
    "feature_cache",
    "estimator_calibrator_fit",
    "prediction_metric",
    "bootstrap",
    "permutation",
    "checkpoint_artifact_persistence",
)
_METRICS = (
    "folds_per_second",
    "fits_per_second",
    "resamples_per_second",
    "wall_time_seconds",
    "process_cpu_time_seconds",
    "process_cpu_utilization_percent",
    "process_lifetime_peak_rss_bytes",
    "process_io_read_bytes",
    "process_io_write_bytes",
    "host_iowait_ticks_unattributed",
    "artifact_write_latency_ms_p50",
    "artifact_write_latency_ms_p95",
    "artifact_write_latency_ms_max",
)
_METRIC_ATTRIBUTION = {
    "process_lifetime_peak_rss_bytes": (
        "PROCESS_LIFETIME_HIGH_WATER_MARK_NOT_AUDIT_WORKLOAD_ATTRIBUTABLE"
    ),
    "host_iowait_ticks_unattributed": "HOST_LEVEL_NOT_PROCESS_ATTRIBUTABLE",
}
_REQUIRED_ARTIFACTS = (
    "BenchmarkPlanArtifact",
    "RuntimeObservationArtifact",
    "RuntimeBenchmarkAttemptArtifact",
    "EquivalenceAttestationArtifact",
    "SourceIntegrityAttestationArtifact",
)
_EQUIVALENCE_CONTRACT = {
    "immutable_golden_fixture_payload": "EXACT",
    "replicate_payload": "EXACT",
    "child_artifact_set": "EXACT",
    "child_artifact_digests": "EXACT",
    "boundary_full_feature_view_payloads": "EXACT_CANONICAL_PAYLOAD_DIGEST",
    "measured_result_payload_float64_tree": "EXACT",
    "measured_checkpoint_journal_bytes": "EXACT_UTF8_LF",
    "measured_to_correctness_replay": "EXACT_BEFORE_ATTESTATION",
    "float_bits": "EXACT_BINARY64",
    "checkpoint_journal_bytes": "EXACT_UTF8_LF",
    "timing_values": "ENVIRONMENTAL_NOT_REPLAY_EQUAL",
}
_ORACLE_CONTRACT = {
    "effective_oracle": "registered_replay_verified_Phase0GoldenReferenceFixture.v1",
    "shared_frozen_components": list(SHARED_FROZEN_COMPONENTS),
    "independent_components": list(ACCELERATION_BOUNDARY_COMPONENTS),
    "canonical_executor_fingerprint": {
        "required_dimensions": list(_EXECUTOR_FINGERPRINT_DIMENSIONS),
        "required_thread_value": "1",
        "worker_count": 1,
        "required_fingerprint_digest": _REQUIRED_EXECUTOR_FINGERPRINT_DIGEST,
    },
    "superseded_policy": "v1.0_reference_evaluator_is_oracle_true",
}
_PLAN_FIELDS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "plan_key",
    "semantic_version",
    "status",
    "supersedes_artifact_digest",
    "lane",
    "agent_authority",
    "evidence_progress_increment",
    "source_measurement_manifest_digest",
    "execution_policy",
    "oracle_contract",
    "source_integrity_contract",
    "observed_phases",
    "metrics",
    "metric_attribution",
    "required_artifacts",
    "equivalence_contract",
    "missing_proc_metric",
    "host_iowait_attribution",
    "production_action",
    "promotion_gate_opened",
}


class RuntimeAuditError(RuntimeError):
    pass


class Evaluator(Protocol):
    def evaluate(self, replicate: Any) -> Mapping[str, Any]: ...


def load_runtime_audit_plan(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeAuditError(f"runtime_audit_plan_invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeAuditError("runtime_audit_plan_invalid: root must be an object")
    if (
        set(payload) != _PLAN_FIELDS
        or payload.get("schema_version")
        != "dehps-m4-p2-9-measurement-runtime-audit-plan.v1"
        or payload.get("artifact_type") != "measurement_runtime_benchmark_plan"
        or payload.get("plan_key") != "M4-P2.9_MEASUREMENT_RUNTIME_AUDIT"
        or payload.get("status") != "FROZEN_SOURCE_INTEGRATION_PENDING"
        or payload.get("lane") != "maintenance"
        or payload.get("agent_authority") != "engineering"
        or payload.get("evidence_progress_increment") != 0
        or payload.get("promotion_gate_opened") is not False
        or payload.get("semantic_version") != "1.1.5"
        or payload.get("supersedes_artifact_digest")
        != "4d0669386fc32b27b5345995bdaf5e902aaa63109e73472804fd6b6ba06fcf15"
        or payload.get("source_measurement_manifest_digest")
        != "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
    ):
        raise RuntimeAuditError("runtime_audit_plan_invalid: governance changed")
    execution_policy = payload.get("execution_policy")
    oracle_contract = payload.get("oracle_contract")
    fingerprint_contract = (
        oracle_contract.get("canonical_executor_fingerprint")
        if isinstance(oracle_contract, dict)
        else None
    )
    equivalence_contract = payload.get("equivalence_contract")
    if (
        execution_policy != _EXECUTION_POLICY
        or oracle_contract != _ORACLE_CONTRACT
        or not isinstance(fingerprint_contract, dict)
        or fingerprint_contract.get("required_dimensions")
        != list(_EXECUTOR_FINGERPRINT_DIMENSIONS)
        or fingerprint_contract.get("required_thread_value") != "1"
        or fingerprint_contract.get("worker_count") != 1
        or _DIGEST_PATTERN.fullmatch(
            str(fingerprint_contract.get("required_fingerprint_digest") or "")
        )
        is None
        or fingerprint_contract.get("required_fingerprint_digest")
        != _REQUIRED_EXECUTOR_FINGERPRINT_DIGEST
        or payload.get("observed_phases") != list(_OBSERVED_PHASES)
        or payload.get("metrics") != list(_METRICS)
        or payload.get("metric_attribution") != _METRIC_ATTRIBUTION
        or payload.get("required_artifacts") != list(_REQUIRED_ARTIFACTS)
        or equivalence_contract != _EQUIVALENCE_CONTRACT
        or payload.get("missing_proc_metric") != "UNAVAILABLE"
        or payload.get("host_iowait_attribution")
        != "HOST_LEVEL_NOT_PROCESS_ATTRIBUTABLE"
        or payload.get("production_action") != "none"
        or payload.get("promotion_gate_opened") is not False
    ):
        raise RuntimeAuditError("runtime_audit_plan_invalid: oracle policy changed")
    try:
        validate_source_integrity_contract(payload.get("source_integrity_contract"))
    except SourceIntegrityError as exc:
        raise RuntimeAuditError(f"runtime_audit_plan_invalid: {exc}") from exc
    digest = str(payload.get("artifact_digest") or "")
    if len(digest) != 64 or config_digest(payload) != digest:
        raise RuntimeAuditError("runtime_audit_plan_invalid: digest changed")
    return payload


@dataclass
class RuntimeAuditObserver:
    enabled: bool = False
    clock_ns: Any = time.perf_counter_ns
    cpu_clock_ns: Any = time.process_time_ns
    phase_wall_ns: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    phase_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    artifact_write_latencies_ns: list[int] = field(default_factory=list)
    folds: int = 0
    fits: int = 0
    resamples: int = 0

    def __post_init__(self) -> None:
        self._started_wall_ns = self.clock_ns() if self.enabled else 0
        self._started_cpu_ns = self.cpu_clock_ns() if self.enabled else 0
        self._started_io = _read_process_io() if self.enabled else None
        self._started_iowait = _read_host_iowait_ticks() if self.enabled else None
        self._stopped_wall_ns: int | None = None
        self._stopped_cpu_ns: int | None = None
        self._stopped_io: dict[str, int] | None = None
        self._stopped_iowait: int | None = None
        self._stopped_peak_rss_bytes: int | None = None

    def _require_collecting(self) -> None:
        if self._stopped_wall_ns is not None:
            raise RuntimeAuditError("runtime audit observer is already stopped")

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        self._require_collecting()
        started = self.clock_ns()
        try:
            yield
        finally:
            elapsed = max(0, self.clock_ns() - started)
            self.phase_wall_ns[name] += elapsed
            self.phase_counts[name] += 1
            if name == "checkpoint_artifact_persistence":
                self.artifact_write_latencies_ns.append(elapsed)

    def count_fold(self, count: int = 1) -> None:
        if self.enabled:
            self._require_collecting()
            self.folds += count

    def count_fit(self, count: int = 1) -> None:
        if self.enabled:
            self._require_collecting()
            self.fits += count

    def count_resample(self, count: int = 1) -> None:
        if self.enabled:
            self._require_collecting()
            self.resamples += count

    def stop(self) -> None:
        if not self.enabled:
            raise RuntimeAuditError("runtime audit observer is disabled")
        self._require_collecting()
        self._stopped_wall_ns = self.clock_ns()
        self._stopped_cpu_ns = self.cpu_clock_ns()
        self._stopped_io = _read_process_io()
        self._stopped_iowait = _read_host_iowait_ticks()
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        self._stopped_peak_rss_bytes = (
            peak_rss * 1024 if platform.system() != "Darwin" else peak_rss
        )

    def observation(
        self,
        *,
        plan_digest: str,
        execution_id: str,
        git_commit: str,
        executor_fingerprint_digest_before: str,
        executor_fingerprint_digest_after: str,
        benchmark_attempt_id: str,
        measured_result_float64_tree_digest: str,
        measured_checkpoint_journal_sha256: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeAuditError("runtime audit observer is disabled")
        if (
            self._stopped_wall_ns is None
            or self._stopped_cpu_ns is None
            or self._stopped_peak_rss_bytes is None
        ):
            raise RuntimeAuditError("runtime audit observer must be stopped")
        wall_ns = max(1, self._stopped_wall_ns - self._started_wall_ns)
        cpu_ns = max(0, self._stopped_cpu_ns - self._started_cpu_ns)
        wall_seconds = wall_ns / 1_000_000_000
        cpu_seconds = cpu_ns / 1_000_000_000
        io_read, io_write = _io_deltas(self._started_io, self._stopped_io)
        iowait = _delta_or_unavailable(self._started_iowait, self._stopped_iowait)
        write_ms = [item / 1_000_000 for item in self.artifact_write_latencies_ns]
        payload: dict[str, Any] = {
            "schema_version": "dehps-m4-p2-9-runtime-observation.v1",
            "artifact_type": "RuntimeObservationArtifact",
            "artifact_digest": "",
            "benchmark_plan_digest": plan_digest,
            "execution_id": execution_id,
            "git_commit": git_commit,
            "executor_fingerprint_digest_before": (executor_fingerprint_digest_before),
            "executor_fingerprint_digest_after": (executor_fingerprint_digest_after),
            "executor_fingerprint_stable": (
                executor_fingerprint_digest_before == executor_fingerprint_digest_after
            ),
            "benchmark_attempt_id": benchmark_attempt_id,
            "workload_kind": "production_like_trace_capture_disabled",
            "trace_capture_enabled": False,
            "fresh_workdir": True,
            "journal_reused": False,
            "measured_result_float64_tree_digest": (
                measured_result_float64_tree_digest
            ),
            "measured_checkpoint_journal_sha256": (measured_checkpoint_journal_sha256),
            "environmental_observation": True,
            "replay_timing_equality_required": False,
            "worker_count": 1,
            "fold_count": self.folds,
            "fit_count": self.fits,
            "resample_count": self.resamples,
            "folds_per_second": self.folds / wall_seconds,
            "fits_per_second": self.fits / wall_seconds,
            "resamples_per_second": self.resamples / wall_seconds,
            "wall_time_seconds": wall_seconds,
            "process_cpu_time_seconds": cpu_seconds,
            "process_cpu_utilization_percent": 100.0 * cpu_seconds / wall_seconds,
            "process_lifetime_peak_rss_bytes": self._stopped_peak_rss_bytes,
            "process_lifetime_peak_rss_attribution": (
                "PROCESS_LIFETIME_HIGH_WATER_MARK_NOT_AUDIT_WORKLOAD_ATTRIBUTABLE"
            ),
            "process_io_read_bytes": io_read,
            "process_io_write_bytes": io_write,
            "host_iowait_ticks_unattributed": iowait,
            "host_iowait_attribution": "HOST_LEVEL_NOT_PROCESS_ATTRIBUTABLE",
            "artifact_write_latency_ms_p50": _percentile(write_ms, 0.50),
            "artifact_write_latency_ms_p95": _percentile(write_ms, 0.95),
            "artifact_write_latency_ms_max": max(write_ms) if write_ms else UNAVAILABLE,
            "phase_wall_time_seconds": {
                key: value / 1_000_000_000
                for key, value in sorted(self.phase_wall_ns.items())
            },
            "phase_invocation_counts": dict(sorted(self.phase_counts.items())),
            "missing_metric_policy": UNAVAILABLE,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "production_action": "none",
            "promotion_gate_opened": False,
            "parent_digests": [plan_digest],
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.m4.p2-9.runtime-observation.v1",
        )
        return payload


class AuditedEvaluator:
    def __init__(self, evaluator: Evaluator, observer: RuntimeAuditObserver) -> None:
        self.evaluator = evaluator
        self.observer = observer

    def evaluate(self, replicate: Any) -> Mapping[str, Any]:
        return self.evaluator.evaluate(replicate)


def build_benchmark_plan_artifact(plan: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(plan)
    payload["artifact_type"] = "BenchmarkPlanArtifact"
    payload["source_plan_digest"] = plan["artifact_digest"]
    payload["parent_digests"] = [plan["artifact_digest"]]
    payload["artifact_digest"] = ""
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2-9.benchmark-plan-artifact.v1",
    )
    return payload


def build_runtime_benchmark_attempt_artifact(
    *,
    benchmark_plan_digest: str,
    observation: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    benchmark_attempt_id: str,
    benchmark_attempt_path: str,
    measured_workdir_path: str,
    correctness_replay_workdir_path: str,
    measured_result_payload: Mapping[str, Any],
    measured_checkpoint_journal_bytes: bytes,
) -> dict[str, Any]:
    try:
        journal_text = measured_checkpoint_journal_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeAuditError(
            "runtime_audit_attempt_invalid: journal is not UTF-8"
        ) from exc
    encoded_result = encode_float64_tree(dict(measured_result_payload))
    result_digest = float64_tree_digest(
        dict(measured_result_payload),
        domain="dehps.m4.p2-9.measured-result-float64-tree.v1",
    )
    journal_sha = sha256(measured_checkpoint_journal_bytes).hexdigest()
    if (
        observation.get("artifact_type") != "RuntimeObservationArtifact"
        or observation.get("benchmark_plan_digest") != benchmark_plan_digest
        or observation.get("execution_id") != execution_id
        or observation.get("git_commit") != git_commit
        or observation.get("benchmark_attempt_id") != benchmark_attempt_id
        or observation.get("workload_kind") != "production_like_trace_capture_disabled"
        or observation.get("trace_capture_enabled") is not False
        or observation.get("fresh_workdir") is not True
        or observation.get("journal_reused") is not False
        or observation.get("measured_result_float64_tree_digest") != result_digest
        or observation.get("measured_checkpoint_journal_sha256") != journal_sha
        or measured_result_payload.get("actual_outer_fold_count") != 61
        or measured_result_payload.get("checkpoint_journal_entry_count") != 61
        or not isinstance(measured_result_payload.get("checkpoint_journal_digest"), str)
        or not isinstance(measured_result_payload.get("checkpoint_journal_path"), str)
    ):
        raise RuntimeAuditError("runtime_audit_attempt_invalid: provenance changed")
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-9-runtime-benchmark-attempt.v1",
        "artifact_type": "RuntimeBenchmarkAttemptArtifact",
        "artifact_digest": "",
        "benchmark_plan_digest": benchmark_plan_digest,
        "runtime_observation_artifact_digest": observation["artifact_digest"],
        "execution_id": execution_id,
        "git_commit": git_commit,
        "benchmark_attempt_id": benchmark_attempt_id,
        "benchmark_attempt_path": benchmark_attempt_path,
        "measured_workdir_path": measured_workdir_path,
        "correctness_replay_workdir_path": correctness_replay_workdir_path,
        "workload_kind": "production_like_trace_capture_disabled",
        "trace_capture_enabled": False,
        "fresh_workdir": True,
        "journal_reused": False,
        "measured_result_payload": dict(measured_result_payload),
        "measured_result_float64_tree": encoded_result,
        "measured_result_float64_tree_digest": result_digest,
        "measured_checkpoint_journal_utf8": journal_text,
        "measured_checkpoint_journal_sha256": journal_sha,
        "measured_checkpoint_journal_logical_digest": measured_result_payload[
            "checkpoint_journal_digest"
        ],
        "measured_checkpoint_journal_entry_count": measured_result_payload[
            "checkpoint_journal_entry_count"
        ],
        "measured_checkpoint_journal_relative_path": measured_result_payload[
            "checkpoint_journal_path"
        ],
        "measured_fold_count": observation["fold_count"],
        "measured_fit_count": observation["fit_count"],
        "measured_resample_count": observation["resample_count"],
        "executor_fingerprint_digest_before": observation[
            "executor_fingerprint_digest_before"
        ],
        "executor_fingerprint_digest_after": observation[
            "executor_fingerprint_digest_after"
        ],
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "production_action": "none",
        "parent_digests": [
            benchmark_plan_digest,
            observation["artifact_digest"],
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2-9.runtime-benchmark-attempt.v1",
    )
    return payload


def validate_runtime_benchmark_attempt_artifact(
    payload: Mapping[str, Any],
    *,
    benchmark_plan_digest: str,
    observation: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> None:
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    result = payload.get("measured_result_payload")
    journal_text = payload.get("measured_checkpoint_journal_utf8")
    if not isinstance(result, Mapping) or not isinstance(journal_text, str):
        raise RuntimeAuditError("runtime_audit_attempt_invalid: payload missing")
    encoded_result = encode_float64_tree(dict(result))
    result_digest = float64_tree_digest(
        dict(result),
        domain="dehps.m4.p2-9.measured-result-float64-tree.v1",
    )
    journal_bytes = journal_text.encode("utf-8")
    journal_sha = sha256(journal_bytes).hexdigest()
    expected_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "benchmark_plan_digest",
        "runtime_observation_artifact_digest",
        "execution_id",
        "git_commit",
        "benchmark_attempt_id",
        "benchmark_attempt_path",
        "measured_workdir_path",
        "correctness_replay_workdir_path",
        "workload_kind",
        "trace_capture_enabled",
        "fresh_workdir",
        "journal_reused",
        "measured_result_payload",
        "measured_result_float64_tree",
        "measured_result_float64_tree_digest",
        "measured_checkpoint_journal_utf8",
        "measured_checkpoint_journal_sha256",
        "measured_checkpoint_journal_logical_digest",
        "measured_checkpoint_journal_entry_count",
        "measured_checkpoint_journal_relative_path",
        "measured_fold_count",
        "measured_fit_count",
        "measured_resample_count",
        "executor_fingerprint_digest_before",
        "executor_fingerprint_digest_after",
        "evidence_created",
        "evidence_progress_increment",
        "production_action",
        "parent_digests",
    }
    if (
        set(payload) != expected_fields
        or digest
        != canonical_digest(
            identity,
            domain="dehps.m4.p2-9.runtime-benchmark-attempt.v1",
        )
        or payload.get("schema_version") != "dehps-m4-p2-9-runtime-benchmark-attempt.v1"
        or payload.get("artifact_type") != "RuntimeBenchmarkAttemptArtifact"
        or payload.get("benchmark_plan_digest") != benchmark_plan_digest
        or payload.get("runtime_observation_artifact_digest")
        != observation.get("artifact_digest")
        or payload.get("execution_id") != execution_id
        or payload.get("git_commit") != git_commit
        or payload.get("benchmark_attempt_id")
        != observation.get("benchmark_attempt_id")
        or payload.get("workload_kind") != "production_like_trace_capture_disabled"
        or payload.get("trace_capture_enabled") is not False
        or payload.get("fresh_workdir") is not True
        or payload.get("journal_reused") is not False
        or payload.get("measured_result_float64_tree") != encoded_result
        or payload.get("measured_result_float64_tree_digest") != result_digest
        or payload.get("measured_result_float64_tree_digest")
        != observation.get("measured_result_float64_tree_digest")
        or payload.get("measured_checkpoint_journal_sha256") != journal_sha
        or payload.get("measured_checkpoint_journal_sha256")
        != observation.get("measured_checkpoint_journal_sha256")
        or payload.get("measured_checkpoint_journal_logical_digest")
        != result.get("checkpoint_journal_digest")
        or payload.get("measured_checkpoint_journal_entry_count") != 61
        or payload.get("measured_checkpoint_journal_entry_count")
        != result.get("checkpoint_journal_entry_count")
        or payload.get("measured_checkpoint_journal_relative_path")
        != result.get("checkpoint_journal_path")
        or payload.get("measured_fold_count") != 61
        or payload.get("measured_fit_count") != 244
        or payload.get("measured_resample_count") != 4000
        or payload.get("executor_fingerprint_digest_before")
        != observation.get("executor_fingerprint_digest_before")
        or payload.get("executor_fingerprint_digest_after")
        != observation.get("executor_fingerprint_digest_after")
        or payload.get("evidence_created") is not False
        or payload.get("evidence_progress_increment") != 0
        or payload.get("production_action") != "none"
        or payload.get("parent_digests")
        != [benchmark_plan_digest, observation.get("artifact_digest")]
    ):
        raise RuntimeAuditError("runtime_audit_attempt_invalid: identity changed")


def build_equivalence_attestation(
    *,
    plan_digest: str,
    reference_payload: Mapping[str, Any],
    audited_payload: Mapping[str, Any],
    reference_child_artifacts: Sequence[Mapping[str, Any]],
    audited_child_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if dict(reference_payload) != dict(audited_payload):
        raise RuntimeAuditError(
            "runtime_audit_equivalence_failed: replicate payload changed"
        )
    reference_children = _child_identity_set(reference_child_artifacts)
    audited_children = _child_identity_set(audited_child_artifacts)
    if reference_children != audited_children:
        raise RuntimeAuditError(
            "runtime_audit_equivalence_failed: child artifacts changed"
        )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-9-equivalence-attestation.v1",
        "artifact_type": "EquivalenceAttestationArtifact",
        "artifact_digest": "",
        "benchmark_plan_digest": plan_digest,
        "status": "EXACT_OUTPUT_EQUIVALENCE_VERIFIED",
        "replicate_payload_digest": canonical_digest(
            dict(reference_payload),
            domain="dehps.m4.p2-9.reference-replicate-payload.v1",
        ),
        "child_artifact_set_digest": canonical_digest(
            reference_children,
            domain="dehps.m4.p2-9.reference-child-artifact-set.v1",
        ),
        "replicate_payload_exact": True,
        "child_artifact_set_exact": True,
        "child_artifact_digests_exact": True,
        "timing_values_equal_required": False,
        "reference_evaluator_is_oracle": False,
        "immutable_golden_fixture_is_oracle": True,
        "acceleration_boundary_independent": True,
        "oracle_construction_fully_implementation_independent": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "production_action": "none",
        "promotion_gate_opened": False,
        "parent_digests": [plan_digest],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2-9.equivalence-attestation.v1",
    )
    return payload


def _child_identity_set(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str]]:
    identities = sorted(
        (
            str(item.get("artifact_type") or ""),
            str(item.get("artifact_digest") or ""),
        )
        for item in artifacts
    )
    if any(len(digest) != 64 for _, digest in identities):
        raise RuntimeAuditError(
            "runtime_audit_equivalence_failed: child digest missing"
        )
    return identities


def _read_process_io(path: Path = Path("/proc/self/io")) -> dict[str, int] | None:
    try:
        values = {
            key.rstrip(":"): int(value)
            for key, value in (
                line.split(maxsplit=1)
                for line in path.read_text(encoding="utf-8").splitlines()
            )
        }
    except (OSError, ValueError):
        return None
    if "read_bytes" not in values or "write_bytes" not in values:
        return None
    return values


def _read_host_iowait_ticks(path: Path = Path("/proc/stat")) -> int | None:
    try:
        cpu = next(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("cpu ")
        )
        fields = cpu.split()
        return int(fields[5])
    except (OSError, ValueError, StopIteration, IndexError):
        return None


def _io_deltas(
    before: Mapping[str, int] | None,
    after: Mapping[str, int] | None,
) -> tuple[int | str, int | str]:
    if before is None or after is None:
        return UNAVAILABLE, UNAVAILABLE
    return (
        max(0, after["read_bytes"] - before["read_bytes"]),
        max(0, after["write_bytes"] - before["write_bytes"]),
    )


def _delta_or_unavailable(before: int | None, after: int | None) -> int | str:
    if before is None or after is None:
        return UNAVAILABLE
    return max(0, after - before)


def _percentile(values: Sequence[float], quantile: float) -> float | str:
    if not values:
        return UNAVAILABLE
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.5)))
    return ordered[index]
