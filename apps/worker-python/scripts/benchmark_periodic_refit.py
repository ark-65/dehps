from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

for variable in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[variable] = "1"

from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    RuntimeAuditObserver,
)
from dehps.research_os.information_theory.measurement_validation import (
    build_cells,
    build_replicate,
    load_periodic_refit_contract,
    load_repaired_measurement_validation_manifest,
)
from dehps.research_os.information_theory.measurement_validation import (
    reference as reference_module,
)
from dehps.research_os.information_theory.measurement_validation.reference import (
    ReferenceReplicateEvaluator,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    expanding_outer_folds,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / (
    "configs/research-os/" "m4-information-theory-p2-6-1-measurement-validation-v1.json"
)
POLICY_PATH = ROOT / (
    "configs/research-os/m4-information-theory-p2-6-3-periodic-refit-v1.json"
)
SYNTHETIC_PATH = ROOT / (
    "configs/research-os/" "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)
PREREGISTRATION_PATH = ROOT / (
    "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)
HARNESS_PATH = ROOT / (
    "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
)
RESAMPLING_PATH = ROOT / (
    "configs/research-os/m4-information-theory-p2-5-resampling-kernel-v1.json"
)
DEFAULT_OUTPUT = ROOT / "runtime/benchmarks/m4-p2-6-3-periodic-refit.json"
SCALES = ("HISTORICAL", "LONG")
POSITIONS = ("MIDPOINT", "TERMINAL")
BLOCK_SIZE = 64
WORKLOAD_FOLDS = {
    "FORWARD_61": 793_000,
    "HISTORICAL": 33_553_000,
    "LONG": 30_310_000,
}
SCALE_REPLICATES = {
    "HISTORICAL": 13_000,
    "LONG": 5_000,
}
EXACT_RESAMPLING_CPU_SECONDS = {
    "HISTORICAL": 18.016678143,
    "LONG": 33.445434815,
}
FORWARD_EVERY_FOLD_CPU_SECONDS_PER_REPLICATE = 194.938


def _block_start(*, outer_fold_count: int, position: str) -> int:
    if position == "MIDPOINT":
        return (outer_fold_count // 2 // BLOCK_SIZE) * BLOCK_SIZE
    if position == "TERMINAL":
        return ((outer_fold_count - BLOCK_SIZE) // BLOCK_SIZE) * BLOCK_SIZE
    raise ValueError(f"unknown block position: {position}")


def _measure(
    *,
    scale_id: str,
    position: str,
    periodic: bool,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = load_repaired_measurement_validation_manifest(MANIFEST_PATH)
    synthetic = load_synthetic_run_manifest(SYNTHETIC_PATH)
    policy = load_periodic_refit_contract(POLICY_PATH)
    source_cell = next(
        cell
        for cell in build_cells(manifest, synthetic)
        if cell.scale_id == scale_id and cell.scenario_id == "NULL_UNIFORM"
    )
    start = _block_start(
        outer_fold_count=source_cell.outer_issue_count,
        position=position,
    )
    stop = min(start + BLOCK_SIZE, source_cell.outer_issue_count)
    block_length = stop - start
    cell = replace(source_cell, outer_issue_count=block_length)
    replicate = build_replicate(
        cell=cell,
        replicate_index=0,
        parent_execution_id="b" * 64,
    )
    observer = RuntimeAuditObserver(enabled=True)
    evaluator = ReferenceReplicateEvaluator.from_paths(
        manifest=manifest,
        synthetic=synthetic,
        preregistration_path=PREREGISTRATION_PATH,
        walk_forward_harness_path=HARNESS_PATH,
        resampling_path=RESAMPLING_PATH,
        truth_by_scenario={},
        git_commit="b" * 40,
        output_dir=output_dir,
        periodic_refit_contract=policy if periodic else None,
        audit_observer=observer,
    )
    learned_fit_count = 0
    original_prepare = reference_module.prepare_probe
    original_folds = reference_module.expanding_outer_folds

    def count_prepare(*args: Any, **kwargs: Any) -> Any:
        nonlocal learned_fit_count
        learned_fit_count += 1
        return original_prepare(*args, **kwargs)

    def selected_folds(dataset: Any) -> tuple[Any, ...]:
        return tuple(expanding_outer_folds(dataset)[start:stop])

    reference_module.prepare_probe = count_prepare
    reference_module.expanding_outer_folds = selected_folds
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        evaluator.evaluate(replicate)
    finally:
        cpu_seconds = time.process_time() - cpu_started
        wall_seconds = time.perf_counter() - wall_started
        reference_module.prepare_probe = original_prepare
        reference_module.expanding_outer_folds = original_folds
    return {
        "scale_id": scale_id,
        "position": position,
        "path": "periodic_refit_64" if periodic else "every_fold_refit",
        "source_outer_fold_count": source_cell.outer_issue_count,
        "block_start_fold_index": start,
        "block_stop_fold_index_exclusive": stop,
        "block_fold_count": block_length,
        "learned_probe_fit_count": learned_fit_count,
        "cpu_seconds": cpu_seconds,
        "wall_seconds": wall_seconds,
        "phase_wall_seconds": {
            name: elapsed / 1_000_000_000
            for name, elapsed in sorted(observer.phase_wall_ns.items())
        },
    }


def _mean_phase(
    midpoint: dict[str, Any],
    terminal: dict[str, Any],
    phase: str,
) -> float:
    return (
        float(midpoint["phase_wall_seconds"].get(phase, 0.0))
        + float(terminal["phase_wall_seconds"].get(phase, 0.0))
    ) / 2.0


def run_benchmark(
    *,
    frozen_every_fold_measurements: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    measurements: list[dict[str, Any]] = []
    if frozen_every_fold_measurements is not None:
        expected = {
            (scale_id, position) for scale_id in SCALES for position in POSITIONS
        }
        actual = {
            (str(item.get("scale_id")), str(item.get("position")))
            for item in frozen_every_fold_measurements
            if item.get("path") == "every_fold_refit"
            and item.get("learned_probe_fit_count")
            == item.get("block_fold_count", 0) * 3
            and int(item.get("block_fold_count", 0)) > 0
        }
        if actual != expected:
            raise ValueError("frozen every-fold benchmark coverage changed")
        measurements.extend(
            item
            for item in frozen_every_fold_measurements
            if item.get("path") == "every_fold_refit"
        )
    with tempfile.TemporaryDirectory(prefix="dehps-p263-benchmark-") as raw:
        temp_root = Path(raw)
        measurements.append(
            _measure(
                scale_id="FORWARD_61",
                position="MIDPOINT",
                periodic=True,
                output_dir=temp_root / "forward_61" / "periodic",
            )
        )
        for scale_id in SCALES:
            for position_index, position in enumerate(POSITIONS):
                if frozen_every_fold_measurements is not None:
                    paths = (True,)
                else:
                    paths = (False, True) if position_index % 2 == 0 else (True, False)
                for periodic in paths:
                    measurements.append(
                        _measure(
                            scale_id=scale_id,
                            position=position,
                            periodic=periodic,
                            output_dir=(
                                temp_root
                                / scale_id.lower()
                                / position.lower()
                                / ("periodic" if periodic else "every-fold")
                            ),
                        )
                    )
    by_key = {
        (item["scale_id"], item["position"], item["path"]): item
        for item in measurements
    }
    scale_estimates: dict[str, dict[str, float]] = {}
    total_every_fold_cpu = 0.0
    total_periodic_cpu = 0.0
    for scale_id in SCALES:
        midpoint_every = by_key[(scale_id, "MIDPOINT", "every_fold_refit")]
        terminal_every = by_key[(scale_id, "TERMINAL", "every_fold_refit")]
        midpoint_periodic = by_key[(scale_id, "MIDPOINT", "periodic_refit_64")]
        terminal_periodic = by_key[(scale_id, "TERMINAL", "periodic_refit_64")]
        every_seconds_per_fold = (
            midpoint_every["cpu_seconds"] / midpoint_every["block_fold_count"]
            + terminal_every["cpu_seconds"] / terminal_every["block_fold_count"]
        ) / 2.0
        outer_fold_count = int(midpoint_periodic["source_outer_fold_count"])
        replicate_count = SCALE_REPLICATES[scale_id]
        boundary_count = (outer_fold_count + BLOCK_SIZE - 1) // BLOCK_SIZE

        learned_fit_cpu = boundary_count * _mean_phase(
            midpoint_periodic,
            terminal_periodic,
            "estimator_calibrator_fit",
        )
        prediction_metric_cpu = (
            outer_fold_count
            * _mean_phase(
                midpoint_periodic,
                terminal_periodic,
                "prediction_metric",
            )
            / BLOCK_SIZE
        )
        checkpoint_cpu = (
            outer_fold_count
            * _mean_phase(
                midpoint_periodic,
                terminal_periodic,
                "checkpoint_artifact_persistence",
            )
            / BLOCK_SIZE
        )
        feature_cache_cpu = 1.25 * max(
            float(midpoint_periodic["phase_wall_seconds"].get("feature_cache", 0.0)),
            float(terminal_periodic["phase_wall_seconds"].get("feature_cache", 0.0)),
        )
        dataset_cpu = max(
            float(
                midpoint_periodic["phase_wall_seconds"].get("dataset_generation", 0.0)
            ),
            float(
                terminal_periodic["phase_wall_seconds"].get("dataset_generation", 0.0)
            ),
        )
        fold_construction_cpu = max(
            float(
                midpoint_periodic["phase_wall_seconds"].get("fold_construction", 0.0)
            ),
            float(
                terminal_periodic["phase_wall_seconds"].get("fold_construction", 0.0)
            ),
        )
        periodic_cpu_per_replicate = (
            learned_fit_cpu
            + prediction_metric_cpu
            + checkpoint_cpu
            + feature_cache_cpu
            + dataset_cpu
            + fold_construction_cpu
            + EXACT_RESAMPLING_CPU_SECONDS[scale_id]
        )
        fold_count = WORKLOAD_FOLDS[scale_id]
        scale_estimates[scale_id] = {
            "midpoint_terminal_mean_every_fold_cpu_seconds_per_fold": (
                every_seconds_per_fold
            ),
            "periodic_cpu_seconds_per_replicate": periodic_cpu_per_replicate,
            "periodic_learned_fit_cpu_seconds_per_replicate": learned_fit_cpu,
            "periodic_prediction_metric_cpu_seconds_per_replicate": (
                prediction_metric_cpu
            ),
            "periodic_checkpoint_cpu_seconds_per_replicate": checkpoint_cpu,
            "periodic_feature_cache_cpu_seconds_per_replicate": feature_cache_cpu,
            "periodic_dataset_cpu_seconds_per_replicate": dataset_cpu,
            "periodic_fold_construction_cpu_seconds_per_replicate": (
                fold_construction_cpu
            ),
            "periodic_exact_resampling_cpu_seconds_per_replicate": (
                EXACT_RESAMPLING_CPU_SECONDS[scale_id]
            ),
            "outer_fold_count_per_replicate": float(outer_fold_count),
            "refit_boundary_count_per_replicate": float(boundary_count),
            "replicate_count": float(replicate_count),
            "workload_fold_count": float(fold_count),
        }
        total_every_fold_cpu += every_seconds_per_fold * fold_count
        total_periodic_cpu += periodic_cpu_per_replicate * replicate_count
    forward_every_fold_cpu = FORWARD_EVERY_FOLD_CPU_SECONDS_PER_REPLICATE * 13_000
    forward_periodic_cpu_seconds_per_replicate = float(
        by_key[("FORWARD_61", "MIDPOINT", "periodic_refit_64")]["cpu_seconds"]
    )
    forward_periodic_cpu = forward_periodic_cpu_seconds_per_replicate * 13_000
    total_every_fold_cpu += forward_every_fold_cpu
    total_periodic_cpu += forward_periodic_cpu
    weighted_speedup = total_every_fold_cpu / total_periodic_cpu
    forecast_days = total_periodic_cpu / 22.0 / 86_400.0 / 0.85
    return {
        "schema_version": "dehps-m4-p2-periodic-refit-benchmark.v2",
        "result_payloads_read": False,
        "worker_count": 22,
        "capacity_efficiency_discount": 0.85,
        "measurements": measurements,
        "scale_estimates": scale_estimates,
        "weighted_speedup": weighted_speedup,
        "forward_61_every_fold_cpu_seconds_per_replicate": (
            FORWARD_EVERY_FOLD_CPU_SECONDS_PER_REPLICATE
        ),
        "forward_61_periodic_cpu_seconds_per_replicate": (
            forward_periodic_cpu_seconds_per_replicate
        ),
        "total_every_fold_cpu_seconds": total_every_fold_cpu,
        "total_periodic_cpu_seconds": total_periodic_cpu,
        "single_host_forecast_days": forecast_days,
        "acceptance": {
            "weighted_speedup_min": 8.0,
            "single_host_forecast_days_max": 12.0,
            "passed": weighted_speedup >= 8.0 and forecast_days <= 12.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reuse-every-fold", type=Path)
    args = parser.parse_args()
    frozen_measurements = None
    if args.reuse_every_fold is not None:
        previous = json.loads(args.reuse_every_fold.read_text(encoding="utf-8"))
        frozen_measurements = previous.get("measurements")
        if not isinstance(frozen_measurements, list):
            raise ValueError("reused benchmark measurements are missing")
    payload = run_benchmark(
        frozen_every_fold_measurements=frozen_measurements,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
