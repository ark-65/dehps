from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import time

import numpy as np

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import (
    history_draw_date,
    history_issue,
    history_numbers,
    train_frequency_stats,
)
from dehps.optimization.walk_forward import (
    _config_weight_matrix,
    _target_scores,
    build_ranked_universe,
)
from dehps.scoring_kernel import (
    KernelPlanner,
    KernelRequest,
    KernelWorkspace,
    WeightMatrix,
    candidate_store_from_matrix,
    numbers_mask,
    target_lex_id,
)
from dehps.scoring_kernel.runtime_input import RuntimeInputCompiler
from dehps.source_version import resolve_git_commit
from dehps.storage.postgres_store import load_history_with_dates
from scripts.run_weight_grid_search import DEFAULT_GRID


DEFAULT_OUTPUT = ROOT_DIR / "runtime/benchmarks/opencl-feature-abi-v1.json"
RESULT_FIELDS = (
    "target_scores",
    "exact_ranks",
    "top_candidate_ids",
    "top_scores",
    "red5_candidate_ids",
    "red5_scores",
    "red5_ranks",
)


def _digest_result(result) -> str:
    digest = sha256()
    for field in RESULT_FIELDS:
        value = np.ascontiguousarray(getattr(result, field))
        digest.update(field.encode("ascii"))
        digest.update(value.view(np.uint8))
    return digest.hexdigest()


def _swap_kib() -> int:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmSwap:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def _run(planner, verified_runtime, weights, request):
    prepare_started = time.perf_counter()
    prepared = planner.prepare_feature_abi(
        verified_runtime,
        code_commit=resolve_git_commit(),
    )
    prepare_seconds = time.perf_counter() - prepare_started
    result = planner.score_rank_feature_abi(
        prepared,
        weights,
        request,
        KernelWorkspace(),
    )
    return result, {
        "backend": result.backend,
        "prepare_seconds": prepare_seconds,
        "result_digest": _digest_result(result),
        "telemetry": dict(result.telemetry),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark OpenCL against the Feature ABI NumPy oracle",
    )
    parser.add_argument("--tile-size", type=int, default=262_144)
    parser.add_argument("--top-k", type=int, default=10_000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.tile_size < 1 or args.top_k < 1 or args.workers < 1:
        raise ValueError("tile-size, top-k, and workers must be positive")

    with get_connection() as conn:
        history = load_history_with_dates(conn)
    if len(history) < 2:
        raise ValueError("benchmark requires at least two history rows")
    train_history = history[:-1]
    target = history[-1]
    target_numbers = history_numbers(target)
    configs = tuple(DEFAULT_GRID)

    stage_started = time.perf_counter()
    matrix = build_ranked_universe(
        use_cache=True,
        include_hard_filter_exclusions=True,
    )
    candidate_build_seconds = time.perf_counter() - stage_started

    stage_started = time.perf_counter()
    store = candidate_store_from_matrix(matrix)
    candidate_abi_seconds = time.perf_counter() - stage_started
    stats = train_frequency_stats(
        train_history,
        target_draw_date=history_draw_date(target),
    )
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix(configs), dtype=np.float64)
    )
    target_scores = np.ascontiguousarray(
        _target_scores(target_numbers, stats, configs),
        dtype=np.float64,
    )
    request = KernelRequest(
        target_scores=target_scores,
        target_lex_id=target_lex_id(store, target_numbers),
        target_mask=numbers_mask(target_numbers),
        top_k=args.top_k,
        chunk_size=args.tile_size,
        worker_count=args.workers,
        exact_rank=True,
        red5=True,
        window_id=len(train_history),
    )

    stage_started = time.perf_counter()
    runtime_inputs = RuntimeInputCompiler().compile_effective_history(
        history=train_history,
        candidate_store=store,
        tile_size=args.tile_size,
        target_draw_date=history_draw_date(target),
        target_issue=history_issue(target),
        source="opencl_feature_abi_v1_benchmark",
    )
    runtime_compile_seconds = time.perf_counter() - stage_started

    reference, reference_row = _run(
        KernelPlanner("numpy_reference"),
        runtime_inputs.verified_runtime,
        weights,
        request,
    )
    opencl, opencl_row = _run(
        KernelPlanner("opencl_gpu"),
        runtime_inputs.verified_runtime,
        weights,
        request,
    )
    field_exact = {
        field: bool(
            np.array_equal(getattr(reference, field), getattr(opencl, field))
        )
        for field in RESULT_FIELDS
    }
    payload = {
        "benchmark": "opencl_feature_abi_backend.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "machine": platform.platform(),
        "history_latest_issue": history_issue(history[-1]),
        "target_issue": history_issue(target),
        "candidate_count": len(store),
        "config_count": len(configs),
        "tile_size": args.tile_size,
        "top_k": args.top_k,
        "workers": args.workers,
        "stages": {
            "candidate_build_seconds": candidate_build_seconds,
            "candidate_abi_seconds": candidate_abi_seconds,
            "runtime_compile_seconds": runtime_compile_seconds,
        },
        "reference": reference_row,
        "opencl": opencl_row,
        "field_exact": field_exact,
        "strict_exact": all(field_exact.values()),
        "swap_kib": _swap_kib(),
        "verified_runtime_id": runtime_inputs.verified_runtime.verified_runtime_id,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["strict_exact"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
