from __future__ import annotations

import numpy as np

from dehps.experiments.ranking_disagreement.models import (
    FROZEN_RANKER_KEYS,
    RankMatrix,
    RankerOutput,
    array_hash,
    normalize_ranker_key,
    stable_hash,
)


def build_rank_matrix(outputs: tuple[RankerOutput, ...]) -> RankMatrix:
    if len(outputs) != len(FROZEN_RANKER_KEYS):
        raise ValueError("rank matrix requires exactly the frozen Round 24 ranker outputs")
    outputs_by_key = {normalize_ranker_key(output.ranker_key): output for output in outputs}
    if tuple(outputs_by_key) != FROZEN_RANKER_KEYS:
        missing = sorted(set(FROZEN_RANKER_KEYS).difference(outputs_by_key))
        extra = sorted(set(outputs_by_key).difference(FROZEN_RANKER_KEYS))
        raise ValueError(f"rank matrix ranker mismatch; missing={missing}, extra={extra}")
    ordered = tuple(outputs_by_key[key] for key in FROZEN_RANKER_KEYS)
    validate_ranker_outputs(ordered)
    values = np.column_stack([output.ranks for output in ordered]).astype(np.int32, copy=False)
    fingerprint = stable_hash(
        {
            "schema": "rank-matrix-v1",
            "combination_ids": array_hash(ordered[0].combination_ids),
            "ranker_keys": FROZEN_RANKER_KEYS,
            "values": array_hash(values),
            "as_of_issue": ordered[0].as_of_issue,
            "history_fingerprint": ordered[0].history_fingerprint,
            "legal_universe_fingerprint": ordered[0].legal_universe_fingerprint,
        }
    )
    matrix = RankMatrix(
        combination_ids=ordered[0].combination_ids.copy(),
        ranker_keys=FROZEN_RANKER_KEYS,
        values=values,
        as_of_issue=ordered[0].as_of_issue,
        history_fingerprint=ordered[0].history_fingerprint,
        legal_universe_fingerprint=ordered[0].legal_universe_fingerprint,
        fingerprint=fingerprint,
    )
    validate_rank_matrix(matrix)
    return matrix


def validate_ranker_outputs(outputs: tuple[RankerOutput, ...]) -> None:
    first = outputs[0]
    expected_ids = first.combination_ids
    for output in outputs:
        if output.as_of_issue != first.as_of_issue:
            raise ValueError("ranker outputs use different as_of_issue values")
        if output.history_fingerprint != first.history_fingerprint:
            raise ValueError("ranker outputs use different history fingerprints")
        if output.legal_universe_fingerprint != first.legal_universe_fingerprint:
            raise ValueError("ranker outputs use different legal-universe fingerprints")
        if not np.array_equal(output.combination_ids, expected_ids):
            raise ValueError("ranker outputs have different combination ordering")
        _validate_rank_vector(output.ranks, expected_ids.shape[0], label=output.ranker_key)


def validate_rank_matrix(matrix: RankMatrix) -> None:
    if matrix.ranker_keys != FROZEN_RANKER_KEYS:
        raise ValueError("rank matrix ranker order differs from frozen Round 24 order")
    if matrix.values.ndim != 2 or matrix.values.shape[1] != len(FROZEN_RANKER_KEYS):
        raise ValueError("rank matrix values must be an N x 3 array")
    if matrix.values.shape[0] != matrix.combination_ids.shape[0]:
        raise ValueError("rank matrix row count must match combination_ids")
    if not np.array_equal(matrix.combination_ids, np.arange(1, matrix.combination_ids.shape[0] + 1)):
        raise ValueError("rank matrix combination ids must be stable, contiguous, and ordered")
    for index, key in enumerate(matrix.ranker_keys):
        _validate_rank_vector(matrix.values[:, index], matrix.values.shape[0], label=key)
    if not matrix.fingerprint:
        raise ValueError("rank matrix fingerprint is required")


def _validate_rank_vector(ranks: np.ndarray, count: int, *, label: str) -> None:
    if ranks.shape != (count,):
        raise ValueError(f"{label} rank vector has wrong shape")
    if not np.issubdtype(ranks.dtype, np.integer):
        raise ValueError(f"{label} ranks must be integers")
    if int(ranks.min()) != 1 or int(ranks.max()) != count:
        raise ValueError(f"{label} ranks must cover 1..N without future or missing entries")
    if np.unique(ranks).shape[0] != count:
        raise ValueError(f"{label} ranks contain duplicates")
