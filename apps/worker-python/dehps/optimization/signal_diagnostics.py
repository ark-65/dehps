from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import candidate_rank
from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    HistoryDraw,
    history_draw_date,
    history_issue,
    history_numbers,
)
from dehps.optimization.control_experiments import TrainMode, target_indexes
from dehps.optimization.feature_ablation import FEATURE_FAMILIES
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    RankedUniverseMatrix,
    compile_score_config_grid_artifact,
    fingerprint_history,
)
from dehps.seven_red.domain import SIX_RED_UNIVERSE


SIGNAL_DIAGNOSTIC_PROTOCOL = "dehps-signal-gradient-diagnostics.v1"
PERMUTATION_PROTOCOL = "candidate-level-dynamic-contribution-permutation.v1"
RANKING_TIE_POLICY = "score_desc_then_full_legal_lex_id_asc"
DECILE_POLICY = "ten_equal_rank_position_bins_decile_10_is_highest"
DEFAULT_RANDOM_SEEDS = (
    "01" * 32,
    "12" * 32,
    "23" * 32,
    "34" * 32,
    "45" * 32,
    "56" * 32,
    "67" * 32,
    "78" * 32,
)
GUARDRAIL = (
    "Diagnostic only. Score gradients, ablation deltas, ranking similarities, and "
    "bootstrap intervals do not authorize a weight change, winner, strategy "
    "promotion, production mutation, or betting claim."
)

STATIC_STRUCTURE_FIELDS = (
    "structural_weight",
    "qian_kun_pattern_weight",
    "first_last_sum_weight",
    "zone_ratio_weight",
    "big_small_ratio_weight",
    "parity_ratio_weight",
    "prime_composite_weight",
    "mod012_weight",
    "tail_distribution_weight",
    "sum_tail_weight",
)
RECENT_FREQUENCY_FIELDS = FEATURE_FAMILIES["frequency"]
OMISSION_INTERVAL_FIELDS = FEATURE_FAMILIES["omission"]
COOCCURRENCE_ADJACENCY_FIELDS = (
    "previous_consecutive_weight",
    "previous_overlap_weight",
    "recent_neighbor_weight",
    "lagged_consecutive_weight",
    "consecutive_trend_weight",
    "repeat_trend_weight",
)
DYNAMIC_FIELDS = tuple(
    field for field in CONFIG_WEIGHT_FIELDS if field not in STATIC_STRUCTURE_FIELDS
)
MINIMAL_LINEAR_WEIGHTS = {
    "structural_weight": 0.4,
    "frequency_weight": 0.3,
    "omission_weight": 0.25,
    "previous_consecutive_weight": 0.05,
}


class SignalDiagnosticError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise SignalDiagnosticError(message)


def _keep_only(
    base: FrequencyRankerConfig,
    fields: Sequence[str],
) -> FrequencyRankerConfig:
    keep = set(fields)
    return replace(
        base,
        **{
            field: float(getattr(base, field)) if field in keep else 0.0
            for field in CONFIG_WEIGHT_FIELDS
        },
    )


def _without(
    base: FrequencyRankerConfig,
    fields: Sequence[str],
) -> FrequencyRankerConfig:
    return replace(base, **{field: 0.0 for field in fields})


def diagnostic_config_manifest(
    base: FrequencyRankerConfig,
) -> tuple[tuple[str, FrequencyRankerConfig, dict[str, Any]], ...]:
    minimal = replace(
        base,
        **{
            field: float(MINIMAL_LINEAR_WEIGHTS.get(field, 0.0))
            for field in CONFIG_WEIGHT_FIELDS
        },
    )
    rows = (
        (
            "full_model",
            base,
            {"operation": "unchanged", "fields": list(CONFIG_WEIGHT_FIELDS)},
        ),
        (
            "static_structure_only",
            _keep_only(base, STATIC_STRUCTURE_FIELDS),
            {"operation": "keep_only", "fields": list(STATIC_STRUCTURE_FIELDS)},
        ),
        (
            "recent_frequency_only",
            _keep_only(base, RECENT_FREQUENCY_FIELDS),
            {"operation": "keep_only", "fields": list(RECENT_FREQUENCY_FIELDS)},
        ),
        (
            "omission_interval_only",
            _keep_only(base, OMISSION_INTERVAL_FIELDS),
            {"operation": "keep_only", "fields": list(OMISSION_INTERVAL_FIELDS)},
        ),
        (
            "without_cooccurrence_adjacency",
            _without(base, COOCCURRENCE_ADJACENCY_FIELDS),
            {
                "operation": "zero_only",
                "fields": list(COOCCURRENCE_ADJACENCY_FIELDS),
                "mapping_note": (
                    "FrequencyRankerConfig has no explicit cooccurrence weight; "
                    "these are the existing adjacency, overlap, neighbor, and repeat fields."
                ),
            },
        ),
        (
            "without_all_dynamic",
            _without(base, DYNAMIC_FIELDS),
            {"operation": "zero_only", "fields": list(DYNAMIC_FIELDS)},
        ),
        (
            "fixed_minimal_linear",
            minimal,
            {
                "operation": "fixed_weights",
                "fields": dict(MINIMAL_LINEAR_WEIGHTS),
            },
        ),
    )
    return rows


def validate_diagnostic_manifest(
    rows: Sequence[tuple[str, FrequencyRankerConfig, Mapping[str, Any]]],
) -> None:
    labels = [row[0] for row in rows]
    if len(labels) != len(set(labels)):
        _fail("diagnostic arm labels must be unique")
    required = {
        "full_model",
        "static_structure_only",
        "recent_frequency_only",
        "omission_interval_only",
        "without_cooccurrence_adjacency",
        "without_all_dynamic",
        "fixed_minimal_linear",
    }
    if set(labels) != required:
        _fail("diagnostic arm manifest is incomplete")
    for _label, config, _metadata in rows:
        values = asdict(config)
        if set(CONFIG_WEIGHT_FIELDS) - set(values):
            _fail("diagnostic config is missing a scoring weight")
        if not all(math.isfinite(float(values[field])) for field in CONFIG_WEIGHT_FIELDS):
            _fail("diagnostic config contains a non-finite weight")


def _seed_int(seed_digest: str, *parts: str) -> int:
    if (
        len(seed_digest) != 64
        or any(character not in "0123456789abcdef" for character in seed_digest)
    ):
        _fail("seed digest must be lowercase sha256 hex")
    payload = "\x00".join((seed_digest, *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def permute_dynamic_contribution(
    *,
    full_scores: np.ndarray,
    static_scores: np.ndarray,
    seed_digest: str,
    target_issue: str,
) -> tuple[np.ndarray, str]:
    if (
        full_scores.ndim != 1
        or static_scores.ndim != 1
        or full_scores.shape != static_scores.shape
    ):
        _fail("full and static score vectors must have one identical shape")
    rng = np.random.default_rng(
        _seed_int(seed_digest, target_issue, PERMUTATION_PROTOCOL)
    )
    permutation = rng.permutation(len(full_scores))
    dynamic = full_scores - static_scores
    result = np.ascontiguousarray(static_scores + dynamic[permutation])
    result.setflags(write=False)
    digest = canonical_digest(
        {
            "protocol": PERMUTATION_PROTOCOL,
            "seed_digest": seed_digest,
            "target_issue": target_issue,
            "candidate_count": len(result),
            "permutation_sha256": hashlib.sha256(
                permutation.astype("<i8", copy=False).tobytes()
            ).hexdigest(),
        },
        domain="dehps.signal-diagnostic.dynamic-permutation.v1",
    )
    return result, digest


def _rank_order(scores: np.ndarray) -> np.ndarray:
    if scores.ndim != 1 or not np.isfinite(scores).all():
        _fail("score vector must be finite and one-dimensional")
    lex_ids = np.arange(len(scores), dtype=np.int64)
    return np.lexsort((lex_ids, -scores))


def _rank_positions(order: np.ndarray) -> np.ndarray:
    positions = np.empty(len(order), dtype=np.int32)
    positions[order] = np.arange(len(order), dtype=np.int32)
    return positions


def _score_gaps(scores: np.ndarray, order: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for cutoff in (10, 100, 10_000):
        if len(order) < cutoff:
            result[f"top_{cutoff}"] = None
            continue
        cutoff_score = float(scores[order[cutoff - 1]])
        next_score = (
            float(scores[order[cutoff]]) if len(order) > cutoff else cutoff_score
        )
        result[f"top_{cutoff}"] = {
            "best_minus_cutoff": round(float(scores[order[0]]) - cutoff_score, 12),
            "boundary_gap": round(cutoff_score - next_score, 12),
            "cutoff_score": cutoff_score,
        }
    return result


def _decile_rows(
    *,
    order: np.ndarray,
    overlaps: np.ndarray,
) -> list[dict[str, Any]]:
    chunks = np.array_split(order, 10)
    rows = []
    for high_index, ids in enumerate(chunks):
        decile = 10 - high_index
        values = overlaps[ids]
        rows.append(
            {
                "decile": decile,
                "candidate_count": int(len(ids)),
                "mean_future_red_match": round(float(values.mean()), 12),
                "red3_plus_rate": round(float((values >= 3).mean()), 12),
                "red4_plus_rate": round(float((values >= 4).mean()), 12),
                "red5_plus_rate": round(float((values >= 5).mean()), 12),
                "red6_rate": round(float((values == 6).mean()), 12),
            }
        )
    return sorted(rows, key=lambda row: int(row["decile"]))


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    x = np.asarray(left, dtype=np.float64)
    y = np.asarray(right, dtype=np.float64)
    if len(x) < 2 or float(x.std()) == 0.0 or float(y.std()) == 0.0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _monotonicity(deciles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(deciles, key=lambda row: int(row["decile"]))
    values = [float(row["mean_future_red_match"]) for row in ordered]
    deltas = [right - left for left, right in zip(values, values[1:])]
    return {
        "adjacent_non_decreasing_count": sum(delta >= 0 for delta in deltas),
        "adjacent_strict_increase_count": sum(delta > 0 for delta in deltas),
        "adjacent_pair_count": len(deltas),
        "decile_index_pearson": round(
            _pearson(list(range(1, len(values) + 1)), values),
            12,
        ),
        "lowest_to_highest_delta": round(values[-1] - values[0], 12),
        "strictly_monotonic": all(delta > 0 for delta in deltas),
    }


def _settle_top_ids(
    numbers: np.ndarray,
    ids: Sequence[int],
    actual: Sequence[int],
) -> dict[str, Any]:
    actual_set = set(int(value) for value in actual)
    counts = [
        len(actual_set & set(int(value) for value in numbers[int(row_id)]))
        for row_id in ids
    ]
    return {
        "ticket_count": len(counts),
        "best_matched_red_count": max(counts, default=0),
        "red3_plus_ticket_count": sum(value >= 3 for value in counts),
        "red4_plus_ticket_count": sum(value >= 4 for value in counts),
        "red5_plus_ticket_count": sum(value >= 5 for value in counts),
        "red6_ticket_count": sum(value == 6 for value in counts),
        "hit_histogram": [counts.count(index) for index in range(7)],
    }


def _random_control_rows(
    *,
    scores: np.ndarray,
    order: np.ndarray,
    numbers: np.ndarray,
    actual: Sequence[int],
    target_issue: str,
    seed_digests: Sequence[str],
    pool_size: int,
) -> list[dict[str, Any]]:
    pool = np.ascontiguousarray(
        order[: min(pool_size, len(order))],
        dtype=np.int64,
    )
    pool_digest = hashlib.sha256(
        pool.astype("<i8", copy=False).tobytes()
    ).hexdigest()
    universe_identity = f"full_legal_six_red:{len(scores)}"
    rows = []
    for seed in seed_digests:
        rng_pool = np.random.default_rng(
            _seed_int(
                seed,
                target_issue,
                "matched_score_pool",
                pool_digest,
            )
        )
        rng_uniform = np.random.default_rng(
            _seed_int(
                seed,
                target_issue,
                "uniform_legal",
                universe_identity,
            )
        )
        matched = rng_pool.choice(pool, size=70, replace=False)
        uniform = rng_uniform.choice(len(scores), size=70, replace=False)
        rows.extend(
            (
                {
                    "control_kind": "matched_score_pool",
                    "seed_digest": seed,
                    "source_pool_sequence_digest": pool_digest,
                    "universe_identity": universe_identity,
                    **_settle_top_ids(numbers, matched, actual),
                },
                {
                    "control_kind": "uniform_legal",
                    "seed_digest": seed,
                    "source_pool_sequence_digest": None,
                    "universe_identity": universe_identity,
                    **_settle_top_ids(numbers, uniform, actual),
                },
            )
        )
    return rows


def score_vector_diagnostics(
    *,
    label: str,
    scores: np.ndarray,
    ranked_universe: RankedUniverseMatrix,
    actual: Sequence[int],
    target_issue: str,
    seed_digests: Sequence[str],
    random_pool_size: int = 10_000,
) -> tuple[dict[str, Any], np.ndarray]:
    if len(ranked_universe) != SIX_RED_UNIVERSE.cardinality:
        _fail("score-gradient diagnostics require the full legal six-red universe")
    if scores.shape != (len(ranked_universe),):
        _fail("score vector does not match the full legal universe")
    actual_tuple = tuple(int(value) for value in actual)
    actual_id = candidate_rank(actual_tuple, universe=SIX_RED_UNIVERSE)
    if tuple(int(value) for value in ranked_universe.numbers[actual_id]) != actual_tuple:
        _fail("full legal universe is not in canonical lexicographic order")
    order = _rank_order(scores)
    positions = _rank_positions(order)
    actual_rank = int(positions[actual_id]) + 1
    overlaps = ranked_universe.number_presence[:, actual_tuple].sum(
        axis=1,
        dtype=np.int16,
    )
    deciles = _decile_rows(order=order, overlaps=overlaps)
    controls = _random_control_rows(
        scores=scores,
        order=order,
        numbers=ranked_universe.numbers,
        actual=actual_tuple,
        target_issue=target_issue,
        seed_digests=seed_digests,
        pool_size=random_pool_size,
    )
    unique_count = int(len(np.unique(scores)))
    return (
        {
            "label": label,
            "score_variance": float(np.var(scores)),
            "score_unique_value_count": unique_count,
            "score_unique_value_ratio": float(unique_count / len(scores)),
            "score_gaps": _score_gaps(scores, order),
            "actual_score": float(scores[actual_id]),
            "actual_rank": actual_rank,
            "actual_rank_fraction": actual_rank / len(scores),
            "actual_score_decile": max(
                1,
                10 - min(9, ((actual_rank - 1) * 10 // len(scores))),
            ),
            "score_deciles": deciles,
            "monotonicity": _monotonicity(deciles),
            "top70": _settle_top_ids(
                ranked_universe.numbers,
                order[:70],
                actual_tuple,
            ),
            "random_controls": controls,
        },
        positions,
    )


def _sampled_kendall_tau(
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    *,
    seed_digest: str,
    target_issue: str,
    comparison_label: str,
    pair_count: int = 50_000,
) -> float:
    rng = np.random.default_rng(
        _seed_int(seed_digest, target_issue, comparison_label, "kendall_pairs")
    )
    left_ids = rng.integers(0, len(left_positions), size=pair_count)
    right_ids = rng.integers(0, len(left_positions), size=pair_count)
    distinct = left_ids != right_ids
    left_delta = left_positions[left_ids[distinct]].astype(np.int64) - left_positions[
        right_ids[distinct]
    ].astype(np.int64)
    right_delta = right_positions[left_ids[distinct]].astype(np.int64) - right_positions[
        right_ids[distinct]
    ].astype(np.int64)
    products = np.sign(left_delta) * np.sign(right_delta)
    return float(products.mean()) if len(products) else 0.0


def ranking_similarity(
    *,
    reference_positions: np.ndarray,
    candidate_positions: np.ndarray,
    seed_digest: str,
    target_issue: str,
    comparison_label: str,
) -> dict[str, Any]:
    if reference_positions.shape != candidate_positions.shape:
        _fail("ranking position vectors must have one identical shape")
    count = len(reference_positions)
    delta = reference_positions.astype(np.int64) - candidate_positions.astype(
        np.int64
    )
    spearman = 1.0 - 6.0 * float(np.dot(delta, delta)) / (
        count * (count * count - 1)
    )
    reference_order = np.argsort(reference_positions)
    candidate_order = np.argsort(candidate_positions)
    jaccard = {}
    for cutoff in (10, 100, 10_000):
        left = set(int(value) for value in reference_order[:cutoff])
        right = set(int(value) for value in candidate_order[:cutoff])
        jaccard[f"top_{cutoff}"] = len(left & right) / len(left | right)
    return {
        "spearman_full_universe": round(spearman, 12),
        "kendall_tau_pair_sample": round(
            _sampled_kendall_tau(
                reference_positions,
                candidate_positions,
                seed_digest=seed_digest,
                target_issue=target_issue,
                comparison_label=comparison_label,
            ),
            12,
        ),
        "kendall_pair_count": 50_000,
        "topk_jaccard": jaccard,
    }


def circular_block_bootstrap(
    values: Sequence[float],
    *,
    seed_digest: str,
    label: str,
    block_length: int = 5,
    resamples: int = 2_000,
) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if len(array) == 0:
        _fail("bootstrap values must be non-empty")
    if block_length < 1 or resamples < 1:
        _fail("bootstrap block length and resamples must be positive")
    series_identity_digest = canonical_digest(
        {
            "values": [float(value) for value in array],
            "block_length": block_length,
            "resamples": resamples,
        },
        domain="dehps.signal-diagnostic.circular-block-series.v1",
    )
    rng = np.random.default_rng(
        _seed_int(
            seed_digest,
            series_identity_digest,
            "circular_block_bootstrap",
        )
    )
    block_count = math.ceil(len(array) / block_length)
    means = np.empty(resamples, dtype=np.float64)
    offsets = np.arange(block_length)
    for index in range(resamples):
        starts = rng.integers(0, len(array), size=block_count)
        ids = ((starts[:, None] + offsets) % len(array)).reshape(-1)[: len(array)]
        means[index] = float(array[ids].mean())
    lower, upper = np.quantile(means, (0.025, 0.975))
    return {
        "method": "circular_block_bootstrap",
        "sample_count": len(array),
        "block_length": block_length,
        "resamples": resamples,
        "seed_digest": seed_digest,
        "series_identity_digest": series_identity_digest,
        "mean": float(array.mean()),
        "interval_95": [float(lower), float(upper)],
    }


def _control_mean(rows: Sequence[Mapping[str, Any]], kind: str) -> float:
    values = [
        float(row["best_matched_red_count"])
        for row in rows
        if row["control_kind"] == kind
    ]
    return mean(values)


def _aggregate_targets(
    target_rows: Sequence[Mapping[str, Any]],
    *,
    seed_digest: str,
    bootstrap_resamples: int,
) -> dict[str, Any]:
    labels = tuple(target_rows[0]["arms"])
    full_best = [
        float(row["arms"]["full_model"]["top70"]["best_matched_red_count"])
        for row in target_rows
    ]
    result: dict[str, Any] = {}
    for label in labels:
        arm_rows = [row["arms"][label] for row in target_rows]
        top70_best = [
            float(row["top70"]["best_matched_red_count"]) for row in arm_rows
        ]
        matched = [
            _control_mean(row["random_controls"], "matched_score_pool")
            for row in arm_rows
        ]
        uniform = [
            _control_mean(row["random_controls"], "uniform_legal")
            for row in arm_rows
        ]
        result[label] = {
            "target_count": len(target_rows),
            "mean_actual_rank_fraction": mean(
                float(row["actual_rank_fraction"]) for row in arm_rows
            ),
            "mean_actual_score_decile": mean(
                float(row["actual_score_decile"]) for row in arm_rows
            ),
            "mean_top70_best_match": mean(top70_best),
            "mean_matched_random_best_match": mean(matched),
            "mean_uniform_random_best_match": mean(uniform),
            "paired_top70_minus_full": circular_block_bootstrap(
                [
                    candidate - baseline
                    for candidate, baseline in zip(top70_best, full_best, strict=True)
                ],
                seed_digest=seed_digest,
                label=f"{label}:top70_minus_full",
                resamples=bootstrap_resamples,
            ),
            "paired_top70_minus_matched_random": circular_block_bootstrap(
                [
                    candidate - baseline
                    for candidate, baseline in zip(top70_best, matched, strict=True)
                ],
                seed_digest=seed_digest,
                label=f"{label}:top70_minus_matched",
                resamples=bootstrap_resamples,
            ),
            "paired_top70_minus_uniform_random": circular_block_bootstrap(
                [
                    candidate - baseline
                    for candidate, baseline in zip(top70_best, uniform, strict=True)
                ],
                seed_digest=seed_digest,
                label=f"{label}:top70_minus_uniform",
                resamples=bootstrap_resamples,
            ),
            "mean_decile_future_red_match": [
                {
                    "decile": decile,
                    "mean_future_red_match": mean(
                        float(row["score_deciles"][decile - 1]["mean_future_red_match"])
                        for row in arm_rows
                    ),
                }
                for decile in range(1, 11)
            ],
            "mean_monotonic_adjacent_non_decreasing": mean(
                float(row["monotonicity"]["adjacent_non_decreasing_count"])
                for row in arm_rows
            ),
        }
    return result


def run_signal_diagnostics(
    *,
    history: list[HistoryDraw],
    base_config: FrequencyRankerConfig,
    ranked_universe: RankedUniverseMatrix,
    train_mode: TrainMode,
    train_window: int,
    eval_window: int = 60,
    seed_digests: Sequence[str] = DEFAULT_RANDOM_SEEDS,
    random_pool_size: int = 10_000,
    bootstrap_resamples: int = 2_000,
) -> dict[str, Any]:
    if len(ranked_universe) != SIX_RED_UNIVERSE.cardinality:
        _fail("run requires the full legal six-red universe")
    manifest = diagnostic_config_manifest(base_config)
    validate_diagnostic_manifest(manifest)
    if not seed_digests:
        _fail("at least one explicit random seed digest is required")
    for seed in seed_digests:
        _seed_int(seed, "validation")
    indexes = list(
        target_indexes(
            history_len=len(history),
            train_window=train_window,
            eval_window=eval_window,
        )
    )
    config_rows = [(label, config) for label, config, _metadata in manifest]
    target_rows: list[dict[str, Any]] = []
    for target_index in indexes:
        train_start = (
            0 if train_mode == "expanding" else max(0, target_index - train_window)
        )
        train_history = history[train_start:target_index]
        target = history[target_index]
        artifact = compile_score_config_grid_artifact(
            train_history=train_history,
            configs=tuple(config for _label, config in config_rows),
            ranked_universe=ranked_universe,
            target_draw_date=history_draw_date(target),
            target_issue=history_issue(target),
        )
        score_vectors = {
            label: artifact.scores[:, index]
            for index, (label, _config) in enumerate(config_rows)
        }
        permuted, permutation_digest = permute_dynamic_contribution(
            full_scores=score_vectors["full_model"],
            static_scores=score_vectors["static_structure_only"],
            seed_digest=seed_digests[0],
            target_issue=history_issue(target),
        )
        score_vectors["permuted_dynamic_features"] = permuted
        arms: dict[str, Any] = {}
        positions: dict[str, np.ndarray] = {}
        for label, scores in score_vectors.items():
            arms[label], positions[label] = score_vector_diagnostics(
                label=label,
                scores=scores,
                ranked_universe=ranked_universe,
                actual=history_numbers(target),
                target_issue=history_issue(target),
                seed_digests=seed_digests,
                random_pool_size=random_pool_size,
            )
        for label in arms:
            arms[label]["similarity_vs_full_model"] = (
                {
                    "spearman_full_universe": 1.0,
                    "kendall_tau_pair_sample": 1.0,
                    "kendall_pair_count": 50_000,
                    "topk_jaccard": {
                        "top_10": 1.0,
                        "top_100": 1.0,
                        "top_10000": 1.0,
                    },
                }
                if label == "full_model"
                else ranking_similarity(
                    reference_positions=positions["full_model"],
                    candidate_positions=positions[label],
                    seed_digest=seed_digests[0],
                    target_issue=history_issue(target),
                    comparison_label=label,
                )
            )
        target_rows.append(
            {
                "issue": history_issue(target),
                "draw_date": (
                    history_draw_date(target).isoformat()
                    if history_draw_date(target)
                    else None
                ),
                "actual_red_numbers": list(history_numbers(target)),
                "train_latest_issue": history_issue(train_history[-1]),
                "leakage_passed": int(history_issue(train_history[-1]))
                < int(history_issue(target)),
                "full_score_artifact_digest": artifact.artifact_digest,
                "dynamic_permutation_digest": permutation_digest,
                "arms": arms,
            }
        )
    if not target_rows or not all(row["leakage_passed"] for row in target_rows):
        _fail("target chronology is incomplete or contaminated")
    protocol = {
        "protocol": SIGNAL_DIAGNOSTIC_PROTOCOL,
        "status": "diagnostic_only",
        "promotion_allowed": False,
        "as_of_issue": history_issue(history[-1]),
        "history_fingerprint": fingerprint_history(history),
        "train_mode": train_mode,
        "train_window": train_window,
        "eval_window": len(indexes),
        "target_issues": [history_issue(history[index]) for index in indexes],
        "universe_size": len(ranked_universe),
        "universe_contract": "full_legal_six_red",
        "ranking_tie_policy": RANKING_TIE_POLICY,
        "decile_policy": DECILE_POLICY,
        "random_pool_size": random_pool_size,
        "random_seed_digests": list(seed_digests),
        "bootstrap_resamples": bootstrap_resamples,
        "guardrail": GUARDRAIL,
    }
    payload = {
        "protocol": protocol,
        "manifest": [
            {
                "label": label,
                "config": asdict(config),
                "operation": metadata,
                "config_digest": canonical_digest(
                    asdict(config),
                    domain="dehps.signal-diagnostic.config.v1",
                ),
            }
            for label, config, metadata in manifest
        ]
        + [
            {
                "label": "permuted_dynamic_features",
                "config": None,
                "operation": {
                    "protocol": PERMUTATION_PROTOCOL,
                    "base": "static_structure_only",
                    "permuted_contribution": "full_model_minus_static_structure_only",
                },
                "config_digest": None,
            }
        ],
        "targets": target_rows,
        "aggregate": _aggregate_targets(
            target_rows,
            seed_digest=seed_digests[0],
            bootstrap_resamples=bootstrap_resamples,
        ),
        "winner": None,
        "research_decision": None,
        "production_action": "none",
    }
    digest = canonical_digest(
        payload,
        domain="dehps.signal-diagnostic.snapshot.v1",
    )
    return {**payload, "snapshot_digest": digest}


def bind_signal_diagnostic_context(
    payload: Mapping[str, Any],
    *,
    base_config_metadata: Mapping[str, Any],
    history_scope: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        key: value
        for key, value in payload.items()
        if key != "snapshot_digest"
    }
    body["execution_context"] = {
        "base_config_metadata": dict(base_config_metadata),
        "history_scope": dict(history_scope),
    }
    digest = canonical_digest(
        body,
        domain="dehps.signal-diagnostic.snapshot.v1",
    )
    return {**body, "snapshot_digest": digest}


def render_signal_diagnostic_report(payload: Mapping[str, Any]) -> str:
    protocol = payload["protocol"]
    rows = []
    for label, aggregate in payload["aggregate"].items():
        interval = aggregate["paired_top70_minus_matched_random"]["interval_95"]
        deciles = aggregate["mean_decile_future_red_match"]
        gradient = float(deciles[-1]["mean_future_red_match"]) - float(
            deciles[0]["mean_future_red_match"]
        )
        rows.append(
            f"| {label} | {aggregate['mean_actual_rank_fraction']:.6f} | "
            f"{aggregate['mean_top70_best_match']:.4f} | "
            f"{aggregate['paired_top70_minus_matched_random']['mean']:+.4f} "
            f"[{interval[0]:+.4f}, {interval[1]:+.4f}] | "
            f"{gradient:+.6f} |"
        )
    return "\n".join(
        (
            "# DEHPS common-window signal diagnostics",
            "",
            f"- snapshot: `{payload['snapshot_digest']}`",
            f"- status: `{protocol['status']}`",
            f"- promotion allowed: `{str(protocol['promotion_allowed']).lower()}`",
            f"- as-of issue: `{protocol['as_of_issue']}`",
            f"- target count: `{protocol['eval_window']}`",
            f"- legal universe: `{protocol['universe_size']}`",
            f"- ranking ties: `{protocol['ranking_tie_policy']}`",
            "",
            "| arm | mean actual rank fraction | mean Top70 best red | Top70 − matched random (95% block bootstrap) | decile 10 − decile 1 mean red |",
            "|---|---:|---:|---:|---:|",
            *rows,
            "",
            "No winner or research decision is produced. Score geometry and ticket-set "
            "geometry are reported separately.",
            "",
            GUARDRAIL,
            "",
        )
    )


def write_signal_diagnostic_artifacts(
    payload: Mapping[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    digest = str(payload["snapshot_digest"])
    body = {key: value for key, value in payload.items() if key != "snapshot_digest"}
    expected = canonical_digest(
        body,
        domain="dehps.signal-diagnostic.snapshot.v1",
    )
    if digest != expected:
        _fail("signal diagnostic snapshot digest does not cover the payload")
    json_path = output_dir / f"signal-diagnostics-{digest}.json"
    report_path = output_dir / f"signal-diagnostics-{digest}.md"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    report = render_signal_diagnostic_report(payload)
    for path, content in ((json_path, encoded), (report_path, report)):
        if path.exists() and path.read_text(encoding="utf-8") != content:
            _fail(f"digest-addressed artifact content mismatch: {path}")
        if not path.exists():
            atomic_write_text(path, content)
    return json_path, report_path


__all__ = [
    "COOCCURRENCE_ADJACENCY_FIELDS",
    "DECILE_POLICY",
    "DEFAULT_RANDOM_SEEDS",
    "DYNAMIC_FIELDS",
    "GUARDRAIL",
    "MINIMAL_LINEAR_WEIGHTS",
    "OMISSION_INTERVAL_FIELDS",
    "PERMUTATION_PROTOCOL",
    "RECENT_FREQUENCY_FIELDS",
    "SIGNAL_DIAGNOSTIC_PROTOCOL",
    "STATIC_STRUCTURE_FIELDS",
    "SignalDiagnosticError",
    "circular_block_bootstrap",
    "bind_signal_diagnostic_context",
    "diagnostic_config_manifest",
    "permute_dynamic_contribution",
    "ranking_similarity",
    "render_signal_diagnostic_report",
    "run_signal_diagnostics",
    "score_vector_diagnostics",
    "validate_diagnostic_manifest",
    "write_signal_diagnostic_artifacts",
]
