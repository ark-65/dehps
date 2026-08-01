from __future__ import annotations

import json
import platform
import resource
import time
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

RUNTIME_AUDIT_PLAN_PATH = Path(
    "configs/research-os/m4-p2-9-measurement-runtime-audit-plan-v1.json"
)
UNAVAILABLE = "UNAVAILABLE"


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
        payload.get("schema_version")
        != "dehps-m4-p2-9-measurement-runtime-audit-plan.v1"
        or payload.get("artifact_type") != "measurement_runtime_benchmark_plan"
        or payload.get("lane") != "maintenance"
        or payload.get("agent_authority") != "engineering"
        or payload.get("evidence_progress_increment") != 0
        or payload.get("promotion_gate_opened") is not False
    ):
        raise RuntimeAuditError("runtime_audit_plan_invalid: governance changed")
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

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
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
            self.folds += count

    def count_fit(self, count: int = 1) -> None:
        if self.enabled:
            self.fits += count

    def count_resample(self, count: int = 1) -> None:
        if self.enabled:
            self.resamples += count

    def observation(
        self,
        *,
        plan_digest: str,
        execution_id: str,
        git_commit: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeAuditError("runtime audit observer is disabled")
        wall_ns = max(1, self.clock_ns() - self._started_wall_ns)
        cpu_ns = max(0, self.cpu_clock_ns() - self._started_cpu_ns)
        wall_seconds = wall_ns / 1_000_000_000
        cpu_seconds = cpu_ns / 1_000_000_000
        ending_io = _read_process_io()
        ending_iowait = _read_host_iowait_ticks()
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_bytes = peak_rss * 1024 if platform.system() != "Darwin" else peak_rss
        io_read, io_write = _io_deltas(self._started_io, ending_io)
        iowait = _delta_or_unavailable(self._started_iowait, ending_iowait)
        write_ms = [item / 1_000_000 for item in self.artifact_write_latencies_ns]
        payload: dict[str, Any] = {
            "schema_version": "dehps-m4-p2-9-runtime-observation.v1",
            "artifact_type": "RuntimeObservationArtifact",
            "artifact_digest": "",
            "benchmark_plan_digest": plan_digest,
            "execution_id": execution_id,
            "git_commit": git_commit,
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
            "peak_rss_bytes": peak_rss_bytes,
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
    payload["artifact_digest"] = ""
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2-9.benchmark-plan-artifact.v1",
    )
    return payload


def build_equivalence_attestation(
    *,
    plan_digest: str,
    reference_payload: Mapping[str, Any],
    audited_payload: Mapping[str, Any],
    reference_child_artifacts: Sequence[Mapping[str, Any]],
    audited_child_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if dict(reference_payload) != dict(audited_payload):
        raise RuntimeAuditError("runtime_audit_equivalence_failed: replicate payload changed")
    reference_children = _child_identity_set(reference_child_artifacts)
    audited_children = _child_identity_set(audited_child_artifacts)
    if reference_children != audited_children:
        raise RuntimeAuditError("runtime_audit_equivalence_failed: child artifacts changed")
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
        "reference_evaluator_is_oracle": True,
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
        raise RuntimeAuditError("runtime_audit_equivalence_failed: child digest missing")
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
            line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("cpu ")
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
