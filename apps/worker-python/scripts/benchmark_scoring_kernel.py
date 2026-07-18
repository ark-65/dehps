from __future__ import annotations

import argparse
import cProfile
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import platform
import pstats
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
    _components_for_matrix,
    _config_weight_matrix,
    _rank_targets_from_scores,
    _target_scores,
    _top_indices,
    build_ranked_universe,
    is_excluded_red_combination,
)
from dehps.scoring_kernel import (
    KernelRequest,
    KernelWorkspace,
    WeightMatrix,
    candidate_store_from_matrix,
    numbers_mask,
    pack_window_state,
    target_lex_id,
)
from dehps.scoring_kernel.numba_backend import NumbaCpuBackend
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend, component_tile
from dehps.storage.postgres_store import load_history_with_dates
from scripts.run_weight_grid_search import DEFAULT_GRID


DEFAULT_CHUNKS = (65_536, 131_072, 262_144, 524_288)


def _reference_score_matrix(matrix, stats, configs) -> np.ndarray:
    """Independent benchmark oracle; never imported by application code."""

    components = _components_for_matrix(matrix, stats)
    return np.round(components @ _config_weight_matrix(configs).T, 8)
DEFAULT_WORKERS = (1, 2, 4, 8, 16)
DEFAULT_OUTPUT = ROOT_DIR / "runtime/benchmarks/scoring-kernel-strict-v1.json"


def _digest_result(result) -> str:
    digest = sha256()
    for value in (
        result.target_scores,
        result.exact_ranks,
        result.top_candidate_ids,
        result.top_scores,
        result.red5_candidate_ids,
        result.red5_scores,
        result.red5_ranks,
    ):
        digest.update(np.ascontiguousarray(value).view(np.uint8))
    return digest.hexdigest()


def _swap_kib() -> int:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmSwap:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def _system_memory_kib() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def _request(
    *,
    store,
    target_numbers: tuple[int, ...],
    target_scores: np.ndarray,
    top_k: int,
    chunk_size: int,
    worker_count: int,
    window_id: int,
    target_excluded: bool,
) -> KernelRequest:
    return KernelRequest(
        target_scores=target_scores,
        target_lex_id=target_lex_id(store, target_numbers),
        target_mask=numbers_mask(target_numbers),
        top_k=top_k,
        chunk_size=chunk_size,
        worker_count=worker_count,
        exact_rank=True,
        red5=True,
        target_excluded=target_excluded,
        window_id=window_id,
    )


def _run_backend(backend, store, state, weights, request, *, prepared=None):
    prepared = prepared or backend.prepare(store)
    result = backend.score_rank(
        prepared,
        state,
        weights,
        request,
        KernelWorkspace(),
    )
    row = dict(result.telemetry)
    row["average_logical_cores"] = (
        float(row["cpu_time"]) / float(row["wall_time"])
        if row["wall_time"]
        else 0.0
    )
    row["peak_rss_mib"] = float(row["peak_rss_kib"]) / 1024
    row["swap_kib"] = _swap_kib()
    row["result_digest"] = _digest_result(result)
    return result, row


def _legacy_red5(matrix, scores: np.ndarray, target_numbers: tuple[int, ...]):
    ids = np.arange(len(matrix), dtype=np.int64)
    red5_ids = np.flatnonzero(
        matrix.number_presence[:, list(target_numbers)].sum(axis=1) == 5
    )
    best_ids = []
    best_scores = []
    best_ranks = []
    for config_index in range(scores.shape[1]):
        order = np.lexsort((red5_ids, -scores[red5_ids, config_index]))
        best_id = int(red5_ids[int(order[0])])
        best_score = float(scores[best_id, config_index])
        best_ids.append(best_id)
        best_scores.append(best_score)
        best_ranks.append(
            int(
                (scores[:, config_index] > best_score).sum()
                + (
                    (scores[:, config_index] == best_score) & (ids < best_id)
                ).sum()
                + 1
            )
        )
    return (
        np.array(best_ids, dtype=np.int64),
        np.array(best_scores, dtype=np.float64),
        np.array(best_ranks, dtype=np.int64),
    )


def verify_real_windows(history, *, window_count: int, top_k: int) -> list[dict]:
    matrix = build_ranked_universe()
    store = candidate_store_from_matrix(matrix)
    configs = tuple(DEFAULT_GRID)
    weights = WeightMatrix(np.ascontiguousarray(_config_weight_matrix(configs)))
    rows: list[dict] = []
    start = max(1, len(history) - window_count)
    for target_index in range(start, len(history)):
        target = history[target_index]
        target_numbers = history_numbers(target)
        stats = train_frequency_stats(
            history[:target_index], target_draw_date=history_draw_date(target)
        )
        target_scores = np.ascontiguousarray(
            _target_scores(target_numbers, stats, configs), dtype=np.float64
        )
        legacy_scores = _reference_score_matrix(matrix, stats, configs)
        legacy_ranks = np.array(
            [
                rank
                for rank, _ in _rank_targets_from_scores(
                    matrix=matrix,
                    scores=legacy_scores,
                    target_numbers=target_numbers,
                    target_scores=tuple(float(value) for value in target_scores),
                    target_excluded=is_excluded_red_combination(target_numbers),
                )
            ],
            dtype=np.int64,
        )
        legacy_top_ids = np.stack(
            [
                _top_indices(legacy_scores[:, index], matrix, top_k)
                for index in range(len(configs))
            ]
        )
        legacy_top_scores = np.stack(
            [
                legacy_scores[legacy_top_ids[index], index]
                for index in range(len(configs))
            ]
        )
        legacy_red_ids, legacy_red_scores, legacy_red_ranks = _legacy_red5(
            matrix, legacy_scores, target_numbers
        )

        state = pack_window_state(stats)
        components_exact = True
        for component_start in range(0, len(matrix), 262_144):
            component_end = min(component_start + 262_144, len(matrix))
            components_exact = components_exact and np.array_equal(
                _components_for_matrix(
                    matrix, stats, start=component_start, end=component_end
                ),
                component_tile(store, state, component_start, component_end),
            )
        request = _request(
            store=store,
            target_numbers=target_numbers,
            target_scores=target_scores,
            top_k=top_k,
            chunk_size=262_144,
            worker_count=8,
            window_id=target_index,
            target_excluded=is_excluded_red_combination(target_numbers),
        )
        backend_rows = []
        for backend in (NumpyReferenceBackend(), NumbaCpuBackend()):
            result, telemetry = _run_backend(
                backend, store, state, weights, request
            )
            exact = bool(
                np.array_equal(result.target_scores, target_scores)
                and np.array_equal(result.exact_ranks, legacy_ranks)
                and np.array_equal(result.top_candidate_ids, legacy_top_ids)
                and np.array_equal(result.top_scores, legacy_top_scores)
                and np.array_equal(result.red5_candidate_ids, legacy_red_ids)
                and np.array_equal(result.red5_scores, legacy_red_scores)
                and np.array_equal(result.red5_ranks, legacy_red_ranks)
            )
            backend_rows.append(
                {
                    "backend": backend.name,
                    "strict_exact": exact,
                    "telemetry": telemetry,
                }
            )
        rows.append(
            {
                "issue": history_issue(target),
                "window_id": target_index,
                "candidate_count": len(matrix),
                "component_cells_exact": bool(components_exact),
                "backends": backend_rows,
            }
        )
        del legacy_scores
    return rows


def benchmark_full_legal(
    history,
    *,
    window_count: int,
    chunks: tuple[int, ...],
    workers: tuple[int, ...],
    top_k: int,
):
    build_started = time.perf_counter()
    matrix = build_ranked_universe(
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    build_seconds = time.perf_counter() - build_started
    store = candidate_store_from_matrix(matrix)
    configs = tuple(DEFAULT_GRID)
    weights = WeightMatrix(np.ascontiguousarray(_config_weight_matrix(configs)))
    start = max(1, len(history) - window_count)
    windows = []
    for target_index in range(start, len(history)):
        target = history[target_index]
        target_numbers = history_numbers(target)
        stats = train_frequency_stats(
            history[:target_index], target_draw_date=history_draw_date(target)
        )
        windows.append(
            (
                target_index,
                history_issue(target),
                target_numbers,
                pack_window_state(stats),
                np.ascontiguousarray(
                    _target_scores(target_numbers, stats, configs), dtype=np.float64
                ),
            )
        )

    # Compile only the real fused tile signature; compilation is excluded from steady-state rows.
    numba_backend = NumbaCpuBackend()
    numpy_backend = NumpyReferenceBackend()
    numpy_prepared = numpy_backend.prepare(store)
    numba_prepared = numba_backend.prepare(store)
    first_window = windows[0]
    first_lex = target_lex_id(store, first_window[2])
    numba_backend._tile(
        store,
        first_window[3],
        weights.values,
        0,
        min(1_024, len(store)),
        first_window[4],
        np.full(weights.config_count, first_lex, dtype=np.int64),
        True,
        numbers_mask(first_window[2]),
        True,
        KernelWorkspace(),
    )

    measurements: list[dict] = []
    oracle_digests: dict[int, str] = {}
    for target_index, issue, target_numbers, state, target_scores in windows:
        oracle_request = _request(
            store=store,
            target_numbers=target_numbers,
            target_scores=target_scores,
            top_k=top_k,
            chunk_size=262_144,
            worker_count=1,
            window_id=target_index,
            target_excluded=False,
        )
        oracle, _ = _run_backend(
            numpy_backend,
            store,
            state,
            weights,
            oracle_request,
            prepared=numpy_prepared,
        )
        oracle_digests[target_index] = _digest_result(oracle)

        for chunk_size in chunks:
            request = _request(
                store=store,
                target_numbers=target_numbers,
                target_scores=target_scores,
                top_k=top_k,
                chunk_size=chunk_size,
                worker_count=1,
                window_id=target_index,
                target_excluded=False,
            )
            result, telemetry = _run_backend(
                numpy_backend,
                store,
                state,
                weights,
                request,
                prepared=numpy_prepared,
            )
            telemetry.update(
                {
                    "issue": issue,
                    "strict_exact": _digest_result(result)
                    == oracle_digests[target_index],
                }
            )
            measurements.append(telemetry)

        for worker_count in workers:
            for chunk_size in chunks:
                request = _request(
                    store=store,
                    target_numbers=target_numbers,
                    target_scores=target_scores,
                    top_k=top_k,
                    chunk_size=chunk_size,
                    worker_count=worker_count,
                    window_id=target_index,
                    target_excluded=False,
                )
                result, telemetry = _run_backend(
                    numba_backend,
                    store,
                    state,
                    weights,
                    request,
                    prepared=numba_prepared,
                )
                telemetry.update(
                    {
                        "issue": issue,
                        "strict_exact": _digest_result(result)
                        == oracle_digests[target_index],
                    }
                )
                measurements.append(telemetry)

    profile = cProfile.Profile()
    target_index, issue, target_numbers, state, target_scores = windows[-1]
    profile_request = _request(
        store=store,
        target_numbers=target_numbers,
        target_scores=target_scores,
        top_k=top_k,
        chunk_size=262_144,
        worker_count=min(8, max(workers)),
        window_id=target_index,
        target_excluded=False,
    )
    profile.enable()
    profile_result, profile_row = _run_backend(
        numba_backend,
        store,
        state,
        weights,
        profile_request,
        prepared=numba_prepared,
    )
    profile.disable()
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(30)
    profile_row.update(
        {
            "issue": issue,
            "strict_exact": _digest_result(profile_result)
            == oracle_digests[target_index],
        }
    )
    return {
        "candidate_count": len(store),
        "source_count": int(matrix.cache_info["source_count"]),
        "excluded_count": int(matrix.cache_info["excluded_count"]),
        "build_seconds": build_seconds,
        "measurements": measurements,
        "profile_measurement": profile_row,
        "profile_top_30": stream.getvalue(),
    }


def render_markdown(payload: dict) -> str:
    benchmark = payload["benchmark"]
    rows = benchmark["measurements"]
    header = (
        "| Backend | Threads | Chunk | Issue | Wall s | CPU s | Avg cores | "
        "Cells/s | Peak RSS MiB | Exact |\n"
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    body = "\n".join(
        "| {backend} | {worker_count} | {chunk_size} | {issue} | {wall_time:.6f} | "
        "{cpu_time:.6f} | {average_logical_cores:.2f} | {cells_per_second:.0f} | "
        "{peak_rss_mib:.1f} | {strict_exact} |".format(**row)
        for row in rows
    )
    equivalence = "\n".join(
        f"- `{row['issue']}`: components={row['component_cells_exact']}, "
        + ", ".join(
            f"{backend['backend']}={backend['strict_exact']}"
            for backend in row["backends"]
        )
        for row in payload["real_history_equivalence"]
    )
    return f"""# Scoring Kernel strict_v1 benchmark

- Generated: `{payload['generated_at']}`
- Host: `{payload['machine']['platform']}`
- Logical CPUs: {payload['machine']['logical_cpus']}
- Full legal candidates: {benchmark['candidate_count']}
- Configs: {payload['config_count']}
- Windows: {payload['window_count']}
- Full-store build: {benchmark['build_seconds']:.3f}s

## Real-history strict equivalence

{equivalence}

## Measurements

{header}
{body}

## cProfile Top 30

```text
{benchmark['profile_top_30'].rstrip()}
```
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark strict_v1 scoring kernels")
    parser.add_argument("--windows", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=1_000)
    parser.add_argument(
        "--chunks",
        default=",".join(str(value) for value in DEFAULT_CHUNKS),
    )
    parser.add_argument(
        "--workers",
        default=",".join(str(value) for value in DEFAULT_WORKERS),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = tuple(int(value) for value in args.chunks.split(",") if value)
    workers = tuple(int(value) for value in args.workers.split(",") if value)
    if args.windows < 1 or args.top_k < 1 or not chunks or not workers:
        raise ValueError("windows, top-k, chunks, and workers must be positive")
    with get_connection() as conn:
        history = load_history_with_dates(conn)
    payload = {
        "contract_version": "dehps-scoring-strict-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "logical_cpus": os.cpu_count(),
            "memory_total_kib": _system_memory_kib(),
        },
        "history_latest_issue": history_issue(history[-1]),
        "window_count": args.windows,
        "config_count": len(DEFAULT_GRID),
        "chunks": list(chunks),
        "workers": list(workers),
        "real_history_equivalence": verify_real_windows(
            history, window_count=args.windows, top_k=args.top_k
        ),
        "benchmark": benchmark_full_legal(
            history,
            window_count=args.windows,
            chunks=chunks,
            workers=workers,
            top_k=args.top_k,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(payload))
    print(args.output)
    print(markdown_path)


if __name__ == "__main__":
    main()
