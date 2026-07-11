from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    FrequencyRankerConfig,
    _components_for_matrix,
    _config_weight_matrix,
    _rank_targets_from_scores,
    _target_scores,
    build_ranked_universe,
    is_excluded_red_combination,
    train_frequency_stats,
)
from dehps.storage.postgres_store import load_history_until_with_dates


PROTOCOL = "dehps-opencl-score-equivalence-v1"
DEFAULT_OUTPUT_PATH = (
    ROOT_DIR
    / "data/output/optimization/compute-probe/opencl-score-probe-latest.json"
)
DEFAULT_SYSTEM_PYTHON_PATH = Path("/usr/lib/python3/dist-packages")
OPENCL_SOURCE = r"""
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
__kernel void score(
    __global const double *components,
    __global const double *weights,
    __global double *output,
    const int component_count,
    const int config_count)
{
    const int row = get_global_id(0);
    const int config = get_global_id(1);
    double value = 0.0;
    for (int component = 0; component < component_count; ++component) {
        value += components[row * component_count + component]
               * weights[config * component_count + component];
    }
    output[row * config_count + config] = value;
}
"""


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_pyopencl() -> Any:
    try:
        import pyopencl as cl  # type: ignore[import-not-found]

        return cl
    except ModuleNotFoundError:
        configured = os.getenv("DEHPS_ACCELERATOR_PYTHONPATH", "")
        candidates = [Path(item) for item in configured.split(os.pathsep) if item]
        if DEFAULT_SYSTEM_PYTHON_PATH not in candidates:
            candidates.append(DEFAULT_SYSTEM_PYTHON_PATH)
        for candidate in candidates:
            if candidate.exists() and str(candidate) not in sys.path:
                sys.path.append(str(candidate))
        import pyopencl as cl  # type: ignore[import-not-found]

        return cl


def probe_configs(*, count: int, seed: int) -> tuple[FrequencyRankerConfig, ...]:
    if count < 1:
        raise ValueError("config count must be positive")
    rng = np.random.default_rng(seed)
    baseline = FrequencyRankerConfig()
    configs: list[FrequencyRankerConfig] = []
    for _ in range(count):
        updates: dict[str, float] = {}
        for field in CONFIG_WEIGHT_FIELDS:
            value = float(getattr(baseline, field))
            if value or rng.random() < 0.35:
                updates[field] = round(max(0.0, value + rng.normal(0, 0.08)), 6)
        configs.append(replace(baseline, **updates))
    return tuple(configs)


def top_set_match_count(
    cpu_scores: np.ndarray,
    gpu_scores: np.ndarray,
    *,
    top_n: int,
) -> int:
    if cpu_scores.shape != gpu_scores.shape:
        return 0
    limit = min(max(1, top_n), cpu_scores.shape[0])
    matches = 0
    for config_index in range(cpu_scores.shape[1]):
        cpu_top = np.argpartition(cpu_scores[:, config_index], -limit)[-limit:]
        gpu_top = np.argpartition(gpu_scores[:, config_index], -limit)[-limit:]
        matches += int(np.array_equal(np.sort(cpu_top), np.sort(gpu_top)))
    return matches


def acceptance_summary(
    *,
    rounded_score_matrix_exact: bool,
    top_set_match_count: int,
    config_count: int,
    target_ranks_equal: bool,
    full_end_to_end_speedup: float,
    min_speedup: float,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not rounded_score_matrix_exact:
        blockers.append("rounded_score_matrix_not_exact")
    if top_set_match_count != config_count:
        blockers.append("top_candidate_sets_changed")
    if not target_ranks_equal:
        blockers.append("target_ranks_changed")
    if full_end_to_end_speedup < min_speedup:
        blockers.append("insufficient_full_end_to_end_speedup")
    return {
        "status": "accepted" if not blockers else "rejected",
        "accepted_for_training": not blockers,
        "minimum_full_end_to_end_speedup": min_speedup,
        "blockers": blockers,
        "selection_changed": False,
        "promotion_allowed": False,
    }


def run_probe(
    *,
    as_of_issue: str | None,
    config_count: int,
    top_n: int,
    seed: int,
    min_speedup: float,
) -> dict[str, Any]:
    cl = load_pyopencl()
    with get_connection() as conn:
        history = load_history_until_with_dates(conn, as_of_issue)
    if len(history) < 2:
        raise ValueError("at least two history rows are required")
    target_issue, target_date, target_numbers = history[-1]
    stats = train_frequency_stats(history[:-1], target_draw_date=target_date)
    matrix = build_ranked_universe()
    configs = probe_configs(count=config_count, seed=seed)

    started = time.perf_counter()
    components = np.ascontiguousarray(_components_for_matrix(matrix, stats))
    component_seconds = time.perf_counter() - started
    weights = np.ascontiguousarray(_config_weight_matrix(configs))

    started = time.perf_counter()
    cpu_scores = np.round(components @ weights.T, 8)
    cpu_matmul_seconds = time.perf_counter() - started

    platforms = cl.get_platforms()
    devices = [
        device
        for platform in platforms
        for device in platform.get_devices(device_type=cl.device_type.GPU)
    ]
    if not devices:
        raise RuntimeError("no OpenCL GPU device is available")
    device = devices[0]
    context = cl.Context([device])
    queue = cl.CommandQueue(
        context,
        properties=cl.command_queue_properties.PROFILING_ENABLE,
    )
    build_started = time.perf_counter()
    program = cl.Program(context, OPENCL_SOURCE).build(options=["-cl-opt-disable"])
    build_seconds = time.perf_counter() - build_started

    flags = cl.mem_flags
    gpu_raw_scores = np.empty_like(cpu_scores)
    gpu_started = time.perf_counter()
    component_buffer = cl.Buffer(
        context,
        flags.READ_ONLY | flags.COPY_HOST_PTR,
        hostbuf=components,
    )
    weight_buffer = cl.Buffer(
        context,
        flags.READ_ONLY | flags.COPY_HOST_PTR,
        hostbuf=weights,
    )
    output_buffer = cl.Buffer(context, flags.WRITE_ONLY, gpu_raw_scores.nbytes)
    event = program.score(
        queue,
        (len(matrix), len(configs)),
        None,
        component_buffer,
        weight_buffer,
        output_buffer,
        np.int32(components.shape[1]),
        np.int32(len(configs)),
    )
    event.wait()
    cl.enqueue_copy(queue, gpu_raw_scores, output_buffer).wait()
    gpu_end_to_end_seconds = time.perf_counter() - gpu_started
    gpu_kernel_seconds = (event.profile.end - event.profile.start) / 1e9
    gpu_scores = np.round(gpu_raw_scores, 8)

    differences = np.abs(cpu_scores - gpu_scores)
    rounded_score_matrix_exact = bool(np.array_equal(cpu_scores, gpu_scores))
    changed_cell_count = int(np.count_nonzero(cpu_scores != gpu_scores))
    matching_top_sets = top_set_match_count(cpu_scores, gpu_scores, top_n=top_n)
    target = tuple(int(number) for number in target_numbers)
    target_scores = _target_scores(target, stats, configs)
    rank_arguments = {
        "matrix": matrix,
        "target_numbers": target,
        "target_scores": target_scores,
        "target_excluded": is_excluded_red_combination(target),
    }
    cpu_ranks = _rank_targets_from_scores(scores=cpu_scores, **rank_arguments)
    gpu_ranks = _rank_targets_from_scores(scores=gpu_scores, **rank_arguments)
    target_ranks_equal = cpu_ranks == gpu_ranks
    full_cpu_seconds = component_seconds + cpu_matmul_seconds
    full_gpu_seconds = component_seconds + gpu_end_to_end_seconds
    full_speedup = full_cpu_seconds / full_gpu_seconds
    acceptance = acceptance_summary(
        rounded_score_matrix_exact=rounded_score_matrix_exact,
        top_set_match_count=matching_top_sets,
        config_count=len(configs),
        target_ranks_equal=target_ranks_equal,
        full_end_to_end_speedup=full_speedup,
        min_speedup=min_speedup,
    )

    return {
        "protocol": PROTOCOL,
        "generated_at": utc_now_text(),
        "status": "completed",
        "scope": {
            "as_of_issue": target_issue,
            "history_row_count": len(history),
            "ranked_universe_size": len(matrix),
            "component_count": int(components.shape[1]),
            "config_count": len(configs),
            "top_n": top_n,
            "seed": seed,
            "dtype": str(components.dtype),
            "score_round_digits": 8,
            "config_source": "deterministic_control_perturbations_not_model_selection",
        },
        "backend": {
            "name": "pyopencl",
            "version": cl.VERSION_TEXT,
            "platform": device.platform.name.strip(),
            "device": device.name.strip(),
            "driver": device.driver_version,
            "kernel_options": ["-cl-opt-disable", "FP_CONTRACT_OFF"],
        },
        "timing_seconds": {
            "component_cpu": round(component_seconds, 6),
            "cpu_matmul_and_round": round(cpu_matmul_seconds, 6),
            "gpu_build": round(build_seconds, 6),
            "gpu_kernel": round(gpu_kernel_seconds, 6),
            "gpu_transfer_kernel_copy_and_round": round(gpu_end_to_end_seconds, 6),
            "full_cpu_score": round(full_cpu_seconds, 6),
            "full_gpu_score": round(full_gpu_seconds, 6),
            "full_end_to_end_speedup": round(full_speedup, 6),
        },
        "equivalence": {
            "rounded_score_matrix_exact": rounded_score_matrix_exact,
            "rounded_changed_cell_count": changed_cell_count,
            "rounded_max_abs_difference": float(differences.max()),
            "top_set_match_count": matching_top_sets,
            "top_set_config_count": len(configs),
            "target_ranks_equal": target_ranks_equal,
            "cpu_target_ranks": cpu_ranks,
            "gpu_target_ranks": gpu_ranks,
        },
        "acceptance": acceptance,
        "interpretation": (
            "Operational accelerator evidence only. The GPU backend must preserve rounded scores, "
            "Top-N sets, and target ranks and must improve full scoring wall time before training use."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe OpenCL score equivalence and throughput")
    parser.add_argument("--as-of-issue")
    parser.add_argument("--configs", type=int, default=28)
    parser.add_argument("--top-n", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20_260_711)
    parser.add_argument("--min-speedup", type=float, default=1.05)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_probe(
        as_of_issue=args.as_of_issue,
        config_count=args.configs,
        top_n=args.top_n,
        seed=args.seed,
        min_speedup=args.min_speedup,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(args.output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "backend": payload["backend"],
                "timing_seconds": payload["timing_seconds"],
                "equivalence": payload["equivalence"],
                "acceptance": payload["acceptance"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
