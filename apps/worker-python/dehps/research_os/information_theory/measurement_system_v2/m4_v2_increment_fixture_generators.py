from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from statistics import NormalDist
from typing import Any, Final

import numpy as np

from .m4_v2_legal_fixed_cardinality import (
    evaluate_overlap_tilt,
    fixed_cardinality_marginals,
    legal_state_log_probability,
    overlap_coefficient_masses,
    solve_fixed_cardinality_maximum_entropy,
    solve_overlap_theta,
)

TEMPORAL_BRANCH_ID: Final = "TEMPORAL_MARGINAL_INCREMENT"
JOINT_BRANCH_ID: Final = "JOINT_RESIDUAL_INCREMENT"
SYNTHETIC_CELL_COUNT: Final = 14
REPLICATES_PER_CELL: Final = 512
MINIMUM_TRAINING_ISSUES: Final = 900
BOOTSTRAP_CHILD_COUNT: Final = 511
BOOTSTRAP_BLOCK_LENGTHS: Final = (3, 5, 8, 13)
PRIMARY_BOOTSTRAP_BLOCK_LENGTH: Final = 5
NUMBER_COUNT: Final = 33
DRAW_SIZE: Final = 6
LEGAL_COMBINATION_COUNT: Final = comb(NUMBER_COUNT, DRAW_SIZE)
UNIFORM_MARGINAL: Final = DRAW_SIZE / NUMBER_COUNT
LEXICOGRAPHIC_HALF_BOUNDARY: Final = (4, 7, 8, 20, 23, 30)
T1_PARTITION: Final = 2_875_258
IS4_WEIGHTS: Final = tuple(
    float(value)
    for value in (
        Fraction(219, 221),
        Fraction(-1, 1),
        Fraction(1, 1),
        Fraction(-1, 1),
        Fraction(1, 1),
        Fraction(-219, 221),
        Fraction(1, 1),
    )
)
LOCAL_TARGETS: Final = (0.001, 0.01, 0.05)
TEMPORAL_LOCAL_FIXTURE_ID: Final = "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT"
JOINT_LOCAL_FIXTURE_ID: Final = "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT"
NULL_FIXTURE_ID: Final = "NULL_UNIFORM_LEGAL_SIX_OF_33"
M1_FIXTURE_ID: Final = "V2_M1_GROUP_ODDS_2_STATIONARY"
T1_FIXTURE_ID: Final = "V2_T1_OVERLAP_ODDS_2_MARKOV"
J1_FIXTURE_ID: Final = "V2_J1_HISTORY_IS4_LAMBDA_HALF"

_HORIZONS: Final = {
    "FORWARD_61": (961, 61),
    "HISTORICAL_2581": (3481, 2581),
}
_TEMPORAL_BOOTSTRAP_DOMAIN: Final = (
    "M4_V2_TEMPORAL_MARGINAL_INCREMENT_MEASUREMENT_HEALTH_V1"
)
_JOINT_CHILD_SEED_DOMAIN: Final = (
    "dehps.m4.v2.joint-residual-increment.seed-child.v1"
)


class IncrementFixtureError(ValueError):
    pass


@dataclass(frozen=True)
class SyntheticCell:
    cell_index: int
    cell_id: str
    fixture_id: str
    horizon_id: str
    sequence_issue_count: int
    evaluation_issue_count: int
    analytic_target_bits_per_issue: float


@dataclass(frozen=True)
class SyntheticSequence:
    """One deterministic registered synthetic sequence and its generator truth.

    ``true_marginals`` is present when the frozen generator has a useful
    per-evaluation conditional marginal oracle.  ``oracle_endpoint_values`` is
    the score against the exact uniform parent for the branch-local positive
    controls and zero for the frozen negative controls.  The accepted runner
    still fits its preregistered estimator; neither array is a fitted result.
    """

    cell: SyntheticCell
    replicate_index: int
    sequence_seed_full_sha256: str
    draws: np.ndarray
    true_marginals: np.ndarray | None
    oracle_endpoint_values: np.ndarray
    local_parameter: float | None


@dataclass(frozen=True)
class IncrementSequenceScores:
    branch_id: str
    evaluation_range: tuple[int, int]
    prediction_owner_material: tuple[dict[str, Any], ...]
    score_owner_material: tuple[dict[str, Any], ...]
    score_values: tuple[float, ...]
    prediction_checkpoint_chain_digest: str
    score_row_chain_digest: str


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise IncrementFixtureError("increment_fixture_canonical_json_invalid") from exc


def _domain_digest(value: Any, *, domain: str) -> str:
    return hashlib.sha256(f"{domain}\x00{_canonical_json(value)}".encode()).hexdigest()


def _branch(branch_id: str) -> str:
    if branch_id not in {TEMPORAL_BRANCH_ID, JOINT_BRANCH_ID}:
        raise IncrementFixtureError("increment_fixture_branch_invalid")
    return branch_id


def _cell_kind_and_fixture_or_target(cell_id: str, fixture_id: str) -> tuple[str, str]:
    if cell_id.startswith("BASE:"):
        return "BASE", fixture_id
    pieces = cell_id.split(":")
    if len(pieces) != 3 or pieces[0] != "LOCAL" or pieces[1] not in {
        "0.001",
        "0.01",
        "0.05",
    }:
        raise IncrementFixtureError("increment_fixture_cell_invalid")
    return "LOCAL", pieces[1]


def child_seed_full_sha256(
    root_seed_full_sha256: str,
    *,
    branch_id: str,
    cell_index: int,
    cell_id: str,
    fixture_id: str,
    horizon_id: str,
    replicate_index: int,
) -> str:
    if (
        not _is_digest(root_seed_full_sha256)
        or not (0 <= cell_index < SYNTHETIC_CELL_COUNT)
        or not (0 <= replicate_index < REPLICATES_PER_CELL)
    ):
        raise IncrementFixtureError("increment_fixture_coordinate_invalid")
    if branch_id == TEMPORAL_BRANCH_ID:
        material = {
            "domain": _TEMPORAL_BOOTSTRAP_DOMAIN,
            "root_seed_full_sha256": root_seed_full_sha256,
            "coordinate_type": "SEQUENCE",
            "cell_index": cell_index,
            "cell_id": cell_id,
            "replicate_index": replicate_index,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    elif branch_id == JOINT_BRANCH_ID:
        cell_kind, fixture_or_target = _cell_kind_and_fixture_or_target(
            cell_id, fixture_id
        )
        material = {
            "domain": _JOINT_CHILD_SEED_DOMAIN,
            "root_seed_full_sha256": root_seed_full_sha256,
            "branch_id": branch_id,
            "stage": "SYNTHETIC_SEQUENCE",
            "cell_kind_or_null": cell_kind,
            "fixture_or_target_id_or_null": fixture_or_target,
            "horizon_id_or_null": horizon_id,
            "replicate_index_or_null": replicate_index,
            "block_length_or_null": None,
            "scheme_id_or_null": None,
            "child_index": 0,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    else:
        raise IncrementFixtureError("increment_fixture_branch_invalid")
    return hashlib.sha256(encoded).hexdigest()


def synthetic_bootstrap_child_seed_full_sha256(
    root_seed_full_sha256: str,
    *,
    branch_id: str,
    cell_index: int,
    cell_id: str,
    fixture_id: str,
    horizon_id: str,
    replicate_index: int,
    block_length: int,
    bootstrap_child_index: int,
) -> str:
    if (
        not _is_digest(root_seed_full_sha256)
        or not (0 <= cell_index < SYNTHETIC_CELL_COUNT)
        or not (0 <= replicate_index < REPLICATES_PER_CELL)
        or block_length not in BOOTSTRAP_BLOCK_LENGTHS
        or not (0 <= bootstrap_child_index < BOOTSTRAP_CHILD_COUNT)
    ):
        raise IncrementFixtureError("increment_fixture_bootstrap_coordinate_invalid")
    if branch_id == TEMPORAL_BRANCH_ID:
        material = {
            "domain": _TEMPORAL_BOOTSTRAP_DOMAIN,
            "root_seed_full_sha256": root_seed_full_sha256,
            "coordinate_type": "BOOTSTRAP",
            "cell_index": cell_index,
            "cell_id": cell_id,
            "replicate_index": replicate_index,
            "block_length": block_length,
            "bootstrap_child_index": bootstrap_child_index,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    elif branch_id == JOINT_BRANCH_ID:
        cell_kind, fixture_or_target = _cell_kind_and_fixture_or_target(
            cell_id, fixture_id
        )
        material = {
            "domain": _JOINT_CHILD_SEED_DOMAIN,
            "root_seed_full_sha256": root_seed_full_sha256,
            "branch_id": branch_id,
            "stage": "SYNTHETIC_BOOTSTRAP",
            "cell_kind_or_null": cell_kind,
            "fixture_or_target_id_or_null": fixture_or_target,
            "horizon_id_or_null": horizon_id,
            "replicate_index_or_null": replicate_index,
            "block_length_or_null": block_length,
            "scheme_id_or_null": None,
            "child_index": bootstrap_child_index,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    else:
        raise IncrementFixtureError("increment_fixture_branch_invalid")
    return hashlib.sha256(encoded).hexdigest()


def historical_resample_child_seed_full_sha256(
    root_seed_full_sha256: str,
    *,
    branch_id: str,
    scheme_index: int,
    scheme_id: str,
    historical_child_index: int,
) -> str:
    if (
        not _is_digest(root_seed_full_sha256)
        or not (0 <= scheme_index < 8)
        or not (0 <= historical_child_index < 2000)
        or not scheme_id
    ):
        raise IncrementFixtureError("increment_fixture_historical_coordinate_invalid")
    if branch_id == TEMPORAL_BRANCH_ID:
        material = {
            "domain": "M4_V2_TEMPORAL_MARGINAL_INCREMENT_HISTORICAL_INFERENCE_V1",
            "root_seed_full_sha256": root_seed_full_sha256,
            "coordinate_type": "HISTORICAL_BOOTSTRAP",
            "scheme_index": scheme_index,
            "scheme_id": scheme_id,
            "historical_child_index": historical_child_index,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    elif branch_id == JOINT_BRANCH_ID:
        material = {
            "domain": _JOINT_CHILD_SEED_DOMAIN,
            "root_seed_full_sha256": root_seed_full_sha256,
            "branch_id": branch_id,
            "stage": "HISTORICAL_RESAMPLE",
            "cell_kind_or_null": None,
            "fixture_or_target_id_or_null": None,
            "horizon_id_or_null": None,
            "replicate_index_or_null": None,
            "block_length_or_null": None,
            "scheme_id_or_null": scheme_id,
            "child_index": historical_child_index,
        }
        encoded = json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    else:
        raise IncrementFixtureError("increment_fixture_branch_invalid")
    return hashlib.sha256(encoded).hexdigest()


def historical_resample_mean(
    values: Sequence[float], *, scheme_id: str, child_seed_full_sha256: str
) -> float:
    """Return one frozen Request479/481 historical resample mean."""

    data = _checked_values(values)
    block_length = _historical_scheme_block_length(scheme_id)
    rng = pcg64dxsm_generator(child_seed_full_sha256)
    size = int(data.size)
    indices: list[int] = []
    if scheme_id.startswith("MOVING_BLOCK_NONCIRCULAR_LENGTH_"):
        if block_length > size:
            raise IncrementFixtureError("increment_fixture_historical_block_invalid")
        while len(indices) < size:
            start = int(rng.integers(0, size - block_length + 1))
            indices.extend(range(start, start + block_length))
    elif scheme_id.startswith("STATIONARY_EXPECTED_LENGTH_"):
        current = int(rng.integers(0, size))
        for position in range(size):
            if position == 0 or float(rng.random()) < 1.0 / block_length:
                current = int(rng.integers(0, size))
            else:
                current = (current + 1) % size
            indices.append(current)
    else:
        raise IncrementFixtureError("increment_fixture_historical_scheme_invalid")
    return neumaier_mean(data[indices[:size]])


def historical_resample_owner_data(
    values: Sequence[float],
    *,
    branch_id: str,
    root_seed_full_sha256: str,
    scheme_index: int,
    scheme_id: str,
    child_count: int = 2000,
) -> dict[str, Any]:
    if child_count != 2000:
        raise IncrementFixtureError("increment_fixture_historical_child_count_invalid")
    means: list[str] = []
    seeds: list[str] = []
    for child_index in range(child_count):
        seed = historical_resample_child_seed_full_sha256(
            root_seed_full_sha256,
            branch_id=branch_id,
            scheme_index=scheme_index,
            scheme_id=scheme_id,
            historical_child_index=child_index,
        )
        seeds.append(seed)
        means.append(
            historical_resample_mean(
                values, scheme_id=scheme_id, child_seed_full_sha256=seed
            ).hex()
        )
    prefix = "temporal" if _branch(branch_id) == TEMPORAL_BRANCH_ID else "joint"
    owner = {
        "scheme_index": scheme_index,
        "scheme_id": scheme_id,
        "block_length": _historical_scheme_block_length(scheme_id),
        "ordered_child_mean_float_hex": means,
        "ordered_child_seed_full_sha256": seeds,
    }
    owner["child_mean_chain_digest"] = _domain_digest(
        {
            "scheme_id": scheme_id,
            "block_length": owner["block_length"],
            "ordered_child_mean_float_hex": means,
        },
        domain=f"dehps.m4.v2.{prefix}.historical-sensitivity-child-mean-chain.v2",
    )
    return owner


def build_historical_sensitivity_summary(
    values: Sequence[float],
    *,
    branch_id: str,
    root_seed_full_sha256: str,
    scheme_index: int,
    scheme_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one exact 2000-child historical sensitivity summary and owner."""

    owner = historical_resample_owner_data(
        values,
        branch_id=branch_id,
        root_seed_full_sha256=root_seed_full_sha256,
        scheme_index=scheme_index,
        scheme_id=scheme_id,
    )
    means = np.asarray(
        [float.fromhex(value) for value in owner["ordered_child_mean_float_hex"]],
        dtype=np.float64,
    )
    alpha = 0.05 / 3.0
    lower, upper, equivalence_upper = np.quantile(
        means, [alpha / 2.0, 1.0 - alpha / 2.0, 1.0 - alpha], method="linear"
    )
    standard_error = float(np.std(means, ddof=1))
    if not math.isfinite(standard_error) or standard_error <= 0.0:
        raise IncrementFixtureError("increment_fixture_historical_inference_invalid")
    summary = {
        "scheme_id": scheme_id,
        "block_length": owner["block_length"],
        "resample_count": 2000,
        "child_mean_chain_digest": owner["child_mean_chain_digest"],
        "effect_interval_bits_per_issue": [float(lower), float(upper)],
        "equivalence_upper_bound_bits_per_issue": float(equivalence_upper),
        "bootstrap_standard_error": standard_error,
        "decision_credit": scheme_id
        == "MOVING_BLOCK_NONCIRCULAR_LENGTH_5_PRIMARY",
    }
    return summary, owner


def pcg64dxsm_generator(child_seed_sha256: str) -> np.random.Generator:
    if not _is_digest(child_seed_sha256):
        raise IncrementFixtureError("increment_fixture_child_seed_invalid")
    seed_word = int(child_seed_sha256[0:16], 16)
    return np.random.Generator(np.random.PCG64DXSM(np.uint64(seed_word)))


def iter_health_coordinates() -> Iterator[tuple[int, int]]:
    for cell_index in range(SYNTHETIC_CELL_COUNT):
        for replicate_index in range(REPLICATES_PER_CELL):
            yield cell_index, replicate_index


def synthetic_cells(branch_id: str) -> tuple[SyntheticCell, ...]:
    branch = _branch(branch_id)
    positive_fixture = T1_FIXTURE_ID if branch == TEMPORAL_BRANCH_ID else J1_FIXTURE_ID
    negative_fixtures = (
        NULL_FIXTURE_ID,
        M1_FIXTURE_ID,
        J1_FIXTURE_ID if branch == TEMPORAL_BRANCH_ID else T1_FIXTURE_ID,
    )
    local_fixture = (
        TEMPORAL_LOCAL_FIXTURE_ID
        if branch == TEMPORAL_BRANCH_ID
        else JOINT_LOCAL_FIXTURE_ID
    )
    specifications: list[tuple[str, str, float]] = [
        (positive_fixture, "BASE", _fixture_truth(branch, positive_fixture)),
        *((fixture, "BASE", 0.0) for fixture in negative_fixtures),
        *((local_fixture, f"LOCAL:{target}", target) for target in LOCAL_TARGETS),
    ]
    cells: list[SyntheticCell] = []
    for fixture_id, kind, target in specifications:
        for horizon_id, (sequence_count, evaluation_count) in _HORIZONS.items():
            if kind == "BASE":
                cell_id = f"BASE:{fixture_id}:{horizon_id}"
            else:
                cell_id = f"{kind}:{horizon_id}"
            cells.append(
                SyntheticCell(
                    cell_index=len(cells),
                    cell_id=cell_id,
                    fixture_id=fixture_id,
                    horizon_id=horizon_id,
                    sequence_issue_count=sequence_count,
                    evaluation_issue_count=evaluation_count,
                    analytic_target_bits_per_issue=target,
                )
            )
    if len(cells) != SYNTHETIC_CELL_COUNT:
        raise IncrementFixtureError("increment_fixture_cell_count_invalid")
    return tuple(cells)


def generate_registered_synthetic_sequence(
    *,
    branch_id: str,
    root_seed_full_sha256: str,
    cell_index: int,
    replicate_index: int,
) -> SyntheticSequence:
    cells = synthetic_cells(branch_id)
    if not (0 <= cell_index < len(cells)) or not (
        0 <= replicate_index < REPLICATES_PER_CELL
    ):
        raise IncrementFixtureError("increment_fixture_coordinate_invalid")
    cell = cells[cell_index]
    seed_digest = child_seed_full_sha256(
        root_seed_full_sha256,
        branch_id=branch_id,
        cell_index=cell.cell_index,
        cell_id=cell.cell_id,
        fixture_id=cell.fixture_id,
        horizon_id=cell.horizon_id,
        replicate_index=replicate_index,
    )
    rng = pcg64dxsm_generator(seed_digest)
    local_parameter: float | None = None
    if cell.fixture_id == T1_FIXTURE_ID:
        draws, true_marginals = _generate_overlap_markov(
            cell.sequence_issue_count,
            cell.evaluation_issue_count,
            math.log(2.0),
            rng,
            lexicographic_initial=False,
        )
    elif cell.fixture_id == J1_FIXTURE_ID:
        draws = _generate_is4_markov(
            cell.sequence_issue_count, 0.5, rng, lexicographic_initial=False
        )
        true_marginals = _uniform_truth(cell.evaluation_issue_count)
    elif cell.fixture_id == M1_FIXTURE_ID:
        draws = _generate_group_iid(cell.sequence_issue_count, 2.0, rng)
        true_marginals = _group_truth(cell.evaluation_issue_count, 2.0)
    elif cell.fixture_id == NULL_FIXTURE_ID:
        draws = _generate_group_iid(cell.sequence_issue_count, 1.0, rng)
        true_marginals = _uniform_truth(cell.evaluation_issue_count)
    elif cell.fixture_id == TEMPORAL_LOCAL_FIXTURE_ID:
        local_parameter = solve_temporal_local_theta(
            cell.analytic_target_bits_per_issue
        )
        draws, true_marginals = _generate_overlap_markov(
            cell.sequence_issue_count,
            cell.evaluation_issue_count,
            local_parameter,
            rng,
            lexicographic_initial=True,
        )
    elif cell.fixture_id == JOINT_LOCAL_FIXTURE_ID:
        local_parameter = solve_joint_local_eta(cell.analytic_target_bits_per_issue)
        draws = _generate_is4_markov(
            cell.sequence_issue_count,
            local_parameter,
            rng,
            lexicographic_initial=True,
        )
        true_marginals = _uniform_truth(cell.evaluation_issue_count)
    else:
        raise IncrementFixtureError("increment_fixture_unknown_fixture")
    evaluation_draws = draws[MINIMUM_TRAINING_ISSUES:]
    if branch_id == TEMPORAL_BRANCH_ID and cell.fixture_id in {
        T1_FIXTURE_ID,
        TEMPORAL_LOCAL_FIXTURE_ID,
    }:
        if true_marginals is None:
            raise IncrementFixtureError("increment_fixture_truth_missing")
        oracle = binary_composite_log_score_difference(
            evaluation_draws,
            candidate_marginals=true_marginals,
            baseline_marginals=_uniform_truth(cell.evaluation_issue_count),
        )
    elif branch_id == JOINT_BRANCH_ID and cell.fixture_id in {
        J1_FIXTURE_ID,
        JOINT_LOCAL_FIXTURE_ID,
    }:
        eta = 0.5 if cell.fixture_id == J1_FIXTURE_ID else local_parameter
        if eta is None:
            raise IncrementFixtureError("increment_fixture_local_parameter_missing")
        oracle = is4_log_score_difference(draws, eta=eta)[
            MINIMUM_TRAINING_ISSUES - 1 :
        ]
    else:
        oracle = np.zeros(cell.evaluation_issue_count, dtype=np.float64)
    if oracle.shape != (cell.evaluation_issue_count,) or not np.all(
        np.isfinite(oracle)
    ):
        raise IncrementFixtureError("increment_fixture_oracle_score_invalid")
    return SyntheticSequence(
        cell=cell,
        replicate_index=replicate_index,
        sequence_seed_full_sha256=seed_digest,
        draws=draws,
        true_marginals=true_marginals,
        oracle_endpoint_values=oracle,
        local_parameter=local_parameter,
    )


def build_temporal_registered_sequence_coordinate(
    *,
    sequence: SyntheticSequence,
    fixture_source_digest: str,
    health_contract_digest: str,
    seed_contract_digest: str,
    synthetic_root_seed_full_sha256: str,
    replicate_index: int,
) -> dict[str, Any]:
    """Bind Request479's generated seed to its exact Temporal event owner."""

    if not all(
        _is_digest(value)
        for value in (
            fixture_source_digest,
            health_contract_digest,
            seed_contract_digest,
            synthetic_root_seed_full_sha256,
            sequence.sequence_seed_full_sha256,
        )
    ) or not 0 <= replicate_index < REPLICATES_PER_CELL:
        raise IncrementFixtureError("increment_fixture_coordinate_owner_invalid")
    coordinate = {
        "branch_id": TEMPORAL_BRANCH_ID,
        "fixture_source_digest": fixture_source_digest,
        "health_contract_digest": health_contract_digest,
        "seed_contract_digest": seed_contract_digest,
        "synthetic_root_seed_full_sha256": synthetic_root_seed_full_sha256,
        "cell_index": sequence.cell.cell_index,
        "cell_id": sequence.cell.cell_id,
        "fixture_id": sequence.cell.fixture_id,
        "horizon_id": sequence.cell.horizon_id,
        "sequence_issue_count": sequence.cell.sequence_issue_count,
        "replicate_index": replicate_index,
        "sequence_seed_full_sha256": sequence.sequence_seed_full_sha256,
    }
    coordinate["coordinate_digest"] = _domain_digest(
        coordinate,
        domain=(
            "dehps.m4.v2.temporal.synthetic-warmup.sequence-coordinate.v1"
        ),
    )
    return coordinate


def binary_composite_log_score_difference(
    draws: np.ndarray,
    *,
    candidate_marginals: np.ndarray,
    baseline_marginals: np.ndarray,
) -> np.ndarray:
    checked_draws = _checked_draws(draws)
    rows = checked_draws.shape[0]
    candidate = _checked_marginal_rows(candidate_marginals, rows=rows)
    baseline = _checked_marginal_rows(baseline_marginals, rows=rows)
    outcomes = np.zeros((rows, NUMBER_COUNT), dtype=np.float64)
    outcomes[
        np.repeat(np.arange(rows), DRAW_SIZE),
        checked_draws.astype(np.int64).ravel() - 1,
    ] = 1.0
    result = np.sum(
        outcomes * np.log2(candidate / baseline)
        + (1.0 - outcomes) * np.log2((1.0 - candidate) / (1.0 - baseline)),
        axis=1,
    )
    if not np.all(np.isfinite(result)):
        raise IncrementFixtureError("increment_fixture_score_nonfinite")
    return result


def score_expanding_marginal_sequence(
    draws: np.ndarray,
    *,
    evaluation_issue_count: int,
    true_marginals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reproduce the frozen expanding singleton estimator without I/O.

    The returned tuple is ``(observed_scores, conditional_truth_scores,
    fitted_marginals)``.  Counts are strict-prior, the prior marginal is 2/11,
    and both score arrays are paired against the uniform six-of-33 marginal
    baseline exactly as in the frozen historical health implementation.
    """

    checked = _checked_draws(draws)
    if (
        isinstance(evaluation_issue_count, bool)
        or not isinstance(evaluation_issue_count, int)
        or evaluation_issue_count <= 0
        or checked.shape[0] - evaluation_issue_count != MINIMUM_TRAINING_ISSUES
    ):
        raise IncrementFixtureError("increment_fixture_training_boundary_invalid")
    truth = _checked_marginal_rows(
        true_marginals, rows=evaluation_issue_count
    )
    indicators = np.zeros((checked.shape[0], NUMBER_COUNT), dtype=np.uint8)
    indicators[
        np.repeat(np.arange(checked.shape[0]), DRAW_SIZE),
        checked.astype(np.int64).ravel() - 1,
    ] = 1
    cumulative = np.cumsum(indicators, axis=0, dtype=np.int64)
    counts_before = np.empty_like(cumulative)
    counts_before[0] = 0
    counts_before[1:] = cumulative[:-1]
    evaluated_counts = counts_before[MINIMUM_TRAINING_ISSUES:]
    prior_counts = np.arange(
        MINIMUM_TRAINING_ISSUES, checked.shape[0], dtype=np.float64
    )
    fitted = (evaluated_counts + UNIFORM_MARGINAL) / (
        prior_counts[:, None] + 1.0
    )
    _checked_marginal_rows(fitted, rows=evaluation_issue_count)
    baseline = _uniform_truth(evaluation_issue_count)
    observed = binary_composite_log_score_difference(
        checked[MINIMUM_TRAINING_ISSUES:],
        candidate_marginals=fitted,
        baseline_marginals=baseline,
    )
    log_selected = np.log2(fitted / baseline)
    log_unselected = np.log2((1.0 - fitted) / (1.0 - baseline))
    conditional_truth = np.sum(
        truth * log_selected + (1.0 - truth) * log_unselected,
        axis=1,
    )
    if not np.all(np.isfinite(conditional_truth)):
        raise IncrementFixtureError("increment_fixture_score_nonfinite")
    return observed, conditional_truth, fitted


def score_temporal_increment_sequence(
    draws: np.ndarray, *, evaluation_issue_count: int
) -> IncrementSequenceScores:
    """Fit and score the frozen Request479 temporal estimator, strict-prior.

    Warm-up transitions 2..900 use the registered theta-zero support model.
    Each target 901 onward fits the one shared theta from transitions 2..t-1,
    then constructs and scores the target without exposing its outcome first.
    """

    checked = _checked_scoring_sequence(draws, evaluation_issue_count)
    transition_rows = _temporal_transition_rows(checked)
    prediction_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    coefficient_rows: list[tuple[float, ...]] = []
    observed_overlaps: list[int] = []
    for transition in transition_rows:
        ordinal = int(transition["evaluation_ordinal"])
        if ordinal >= MINIMUM_TRAINING_ISSUES + 1:
            theta_solution = solve_overlap_theta(
                coefficient_rows, observed_overlaps, maximum_iterations=100
            )
            theta = theta_solution.theta
            target = evaluate_overlap_tilt(
                transition["base_weights"],
                transition["previous_state"],
                theta,
                transition["actual_state"],
            )
            baseline_log = legal_state_log_probability(
                transition["base_weights"],
                transition["actual_state"],
                partition=transition["base_partition"],
            )
            score = (target.actual_log_probability - baseline_log) / math.log(2.0)
            prediction = {
                "branch_id": TEMPORAL_BRANCH_ID,
                "evaluation_ordinal": ordinal,
                "strict_prior_last_included_ordinal": ordinal - 1,
                "q_m_weights_float_hex": [
                    float(value).hex() for value in transition["base_weights"]
                ],
                "q_m_partition_float_hex": float(
                    transition["base_partition"]
                ).hex(),
                "theta_float_hex": theta.hex(),
                "theta_training_transition_count": ordinal - 2,
                "theta_score_float_hex": theta_solution.score.hex(),
                "q_t_partition_float_hex": target.partition.hex(),
                "q_t_marginals_float_hex": [
                    float(value).hex() for value in target.marginals
                ],
            }
            _append_scored_owner(
                prediction_rows,
                score_rows,
                scores,
                prediction=prediction,
                score=score,
                actual_state=transition["actual_state"],
                branch_id=TEMPORAL_BRANCH_ID,
            )
        coefficient_rows.append(transition["coefficient_masses"])
        observed_overlaps.append(int(transition["observed_overlap"]))
    return _sequence_score_result(
        branch_id=TEMPORAL_BRANCH_ID,
        prediction_rows=prediction_rows,
        score_rows=score_rows,
        scores=scores,
    )


def score_joint_residual_sequence(
    draws: np.ndarray, *, evaluation_issue_count: int
) -> IncrementSequenceScores:
    """Fit and score the frozen Request481 residual estimator, strict-prior."""

    checked = _checked_scoring_sequence(draws, evaluation_issue_count)
    temporal_rows = _temporal_transition_rows(checked)
    overlap_rows: list[tuple[float, ...]] = []
    overlaps: list[int] = []
    prior_z: list[float] = []
    prediction_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for transition in temporal_rows:
        ordinal = int(transition["evaluation_ordinal"])
        if ordinal <= MINIMUM_TRAINING_ISSUES:
            theta = 0.0
            qbase_weights = transition["base_weights"]
        else:
            theta = solve_overlap_theta(
                overlap_rows, overlaps, maximum_iterations=100
            ).theta
            previous = frozenset(transition["previous_state"])
            multiplier = math.exp(theta)
            qbase_weights = tuple(
                weight * multiplier if index in previous else weight
                for index, weight in enumerate(transition["base_weights"])
            )
        projection = _is4_projected_direction(
            qbase_weights,
            history_sign=(
                -1.0
                if tuple(value + 1 for value in transition["previous_state"])
                <= LEXICOGRAPHIC_HALF_BOUNDARY
                else 1.0
            ),
            actual_state=transition["actual_state"],
        )
        if ordinal >= MINIMUM_TRAINING_ISSUES + 1:
            eta = _solve_eta_root(prior_z)
            factor = 1.0 + eta * projection["actual_z"]
            if factor <= 0.0:
                raise IncrementFixtureError("increment_fixture_joint_factor_invalid")
            score = math.log2(factor)
            prediction = {
                "branch_id": JOINT_BRANCH_ID,
                "evaluation_ordinal": ordinal,
                "strict_prior_last_included_ordinal": ordinal - 1,
                "q_base_weights_float_hex": [float(value).hex() for value in qbase_weights],
                "temporal_theta_float_hex": theta.hex(),
                "projection_coefficients_float_hex": [
                    float(value).hex() for value in projection["coefficients"]
                ],
                "projection_scale_float_hex": float(projection["scale"]).hex(),
                "eta_float_hex": eta.hex(),
                "eta_training_transition_count": ordinal - 2,
                "target_z_float_hex": float(projection["actual_z"]).hex(),
            }
            _append_scored_owner(
                prediction_rows,
                score_rows,
                scores,
                prediction=prediction,
                score=score,
                actual_state=transition["actual_state"],
                branch_id=JOINT_BRANCH_ID,
            )
        prior_z.append(float(projection["actual_z"]))
        overlap_rows.append(transition["coefficient_masses"])
        overlaps.append(int(transition["observed_overlap"]))
    return _sequence_score_result(
        branch_id=JOINT_BRANCH_ID,
        prediction_rows=prediction_rows,
        score_rows=score_rows,
        scores=scores,
    )


def is4_log_score_difference(draws: np.ndarray, *, eta: float) -> np.ndarray:
    checked = _checked_draws(draws)
    if not 0.0 <= eta < 1.0 or not math.isfinite(eta):
        raise IncrementFixtureError("increment_fixture_eta_invalid")
    values = np.empty(checked.shape[0] - 1, dtype=np.float64)
    for index in range(1, checked.shape[0]):
        previous = tuple(int(value) for value in checked[index - 1])
        sign = -1.0 if previous <= LEXICOGRAPHIC_HALF_BOUNDARY else 1.0
        group_count = int(np.count_nonzero(checked[index] <= 16))
        ratio = 1.0 + sign * eta * IS4_WEIGHTS[group_count]
        if ratio <= 0.0 or not math.isfinite(ratio):
            raise IncrementFixtureError("increment_fixture_is4_probability_invalid")
        values[index - 1] = math.log2(ratio)
    return values


def circular_centered_mbb_indices(
    *, sample_size: int, block_length: int, child_seed_sha256: str
) -> tuple[int, ...]:
    if sample_size <= 0 or not 1 <= block_length <= sample_size:
        raise IncrementFixtureError("increment_fixture_mbb_shape_invalid")
    rng = pcg64dxsm_generator(child_seed_sha256)
    output: list[int] = []
    while len(output) < sample_size:
        start = int(rng.integers(0, sample_size))
        output.extend((start + offset) % sample_size for offset in range(block_length))
    return tuple(output[:sample_size])


def centered_circular_mbb_owner_data(
    values: Sequence[float],
    *,
    branch_id: str,
    root_seed_full_sha256: str,
    cell_index: int,
    cell_id: str,
    fixture_id: str,
    horizon_id: str,
    replicate_index: int,
    sequence_coordinate_digest: str,
) -> tuple[dict[str, Any], ...]:
    branch = _branch(branch_id)
    if not _is_digest(sequence_coordinate_digest):
        raise IncrementFixtureError("increment_fixture_sequence_coordinate_invalid")
    data = _checked_values(values)
    observed = neumaier_mean(data)
    centered = data - observed
    domain = (
        "dehps.m4.v2.temporal.synthetic-health.bootstrap-child-mean-chain.v2"
        if branch == TEMPORAL_BRANCH_ID
        else "dehps.m4.v2.joint.synthetic-health.bootstrap-child-mean-chain.v2"
    )
    rows: list[dict[str, Any]] = []
    for block_length in BOOTSTRAP_BLOCK_LENGTHS:
        if block_length > data.size:
            raise IncrementFixtureError("increment_fixture_mbb_shape_invalid")
        child_seeds: list[str] = []
        child_means: list[str] = []
        for child_index in range(BOOTSTRAP_CHILD_COUNT):
            seed = synthetic_bootstrap_child_seed_full_sha256(
                root_seed_full_sha256,
                branch_id=branch,
                cell_index=cell_index,
                cell_id=cell_id,
                fixture_id=fixture_id,
                horizon_id=horizon_id,
                replicate_index=replicate_index,
                block_length=block_length,
                bootstrap_child_index=child_index,
            )
            indices = circular_centered_mbb_indices(
                sample_size=int(data.size),
                block_length=block_length,
                child_seed_sha256=seed,
            )
            child_seeds.append(seed)
            child_means.append(neumaier_mean(centered[list(indices)]).hex())
        owner = {
            "sequence_coordinate_digest": sequence_coordinate_digest,
            "block_length": block_length,
            "ordered_child_mean_float_hex": child_means,
            "ordered_child_seed_full_sha256": child_seeds,
        }
        owner["child_mean_chain_digest"] = _domain_digest(owner, domain=domain)
        rows.append(owner)
    return tuple(rows)


def build_synthetic_health_replicate_evidence(
    values: Sequence[float],
    *,
    branch_id: str,
    root_seed_full_sha256: str,
    cell_index: int,
    cell_id: str,
    fixture_id: str,
    horizon_id: str,
    replicate_index: int,
    sequence_coordinate_digest: str,
    prediction_checkpoint_chain_digest: str,
    score_row_chain_digest: str,
    analytic_truth_bits_per_issue: float,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    branch = _branch(branch_id)
    if not (
        _is_digest(prediction_checkpoint_chain_digest)
        and _is_digest(score_row_chain_digest)
        and math.isfinite(analytic_truth_bits_per_issue)
    ):
        raise IncrementFixtureError("increment_fixture_replicate_owner_invalid")
    data = _checked_values(values)
    expected_count = _HORIZONS.get(horizon_id, (0, 0))[1]
    if data.size != expected_count:
        raise IncrementFixtureError("increment_fixture_evaluation_count_invalid")
    owners = centered_circular_mbb_owner_data(
        data,
        branch_id=branch,
        root_seed_full_sha256=root_seed_full_sha256,
        cell_index=cell_index,
        cell_id=cell_id,
        fixture_id=fixture_id,
        horizon_id=horizon_id,
        replicate_index=replicate_index,
        sequence_coordinate_digest=sequence_coordinate_digest,
    )
    primary = owners[BOOTSTRAP_BLOCK_LENGTHS.index(PRIMARY_BOOTSTRAP_BLOCK_LENGTH)]
    deviations = np.asarray(
        [float.fromhex(value) for value in primary["ordered_child_mean_float_hex"]],
        dtype=np.float64,
    )
    observed = neumaier_mean(data)
    q025, q975 = np.quantile(deviations, [0.025, 0.975], method="linear")
    standard_error = float(np.std(deviations, ddof=1))
    mde = (
        NormalDist().inv_cdf(0.95) + NormalDist().inv_cdf(0.8)
    ) * standard_error
    upper_tail_p = (1 + int(np.count_nonzero(deviations >= observed))) / (
        BOOTSTRAP_CHILD_COUNT + 1
    )
    if not (
        math.isfinite(standard_error)
        and standard_error > 0.0
        and math.isfinite(mde)
        and mde >= 0.0
    ):
        raise IncrementFixtureError("increment_fixture_mbb_inference_invalid")
    payload: dict[str, Any] = {
        "branch_id": branch,
        "sequence_coordinate_digest": sequence_coordinate_digest,
        "horizon_id": horizon_id,
        "evaluation_range": [MINIMUM_TRAINING_ISSUES + 1, MINIMUM_TRAINING_ISSUES + expected_count],
        "evaluation_count": expected_count,
        "prediction_checkpoint_chain_digest": prediction_checkpoint_chain_digest,
        "score_row_chain_digest": score_row_chain_digest,
        "observed_mean_float_hex": observed.hex(),
        "analytic_truth_float_hex": float(analytic_truth_bits_per_issue).hex(),
        "bias_float_hex": (observed - analytic_truth_bits_per_issue).hex(),
        "bootstrap_block_lengths": list(BOOTSTRAP_BLOCK_LENGTHS),
        "ordered_bootstrap_child_mean_chain_digests": [
            owner["child_mean_chain_digest"] for owner in owners
        ],
        "primary_detection": bool(observed > 0.0 and upper_tail_p <= 0.05),
        "primary_interval": {
            "lower_float_hex": float(observed - q975).hex(),
            "upper_float_hex": float(observed - q025).hex(),
        },
        "primary_standard_error_float_hex": standard_error.hex(),
        "primary_mde_float_hex": mde.hex(),
    }
    domain = (
        "dehps.m4.v2.temporal.synthetic-health.replicate-evidence.v2"
        if branch == TEMPORAL_BRANCH_ID
        else "dehps.m4.v2.joint.synthetic-health.replicate-evidence.v2"
    )
    payload["replicate_evidence_digest"] = _domain_digest(payload, domain=domain)
    return payload, owners


def build_synthetic_health_cell_summary(
    commitments: Sequence[Mapping[str, Any]],
    *,
    branch_id: str,
    cell: SyntheticCell,
) -> dict[str, Any]:
    if len(commitments) != REPLICATES_PER_CELL:
        raise IncrementFixtureError("increment_fixture_cell_replicate_count_invalid")
    digests: list[str] = []
    detections = 0
    biases: list[float] = []
    covered = 0
    mde_complete = True
    for commitment in commitments:
        digest = commitment.get("replicate_evidence_digest")
        if not _is_digest(digest):
            raise IncrementFixtureError("increment_fixture_replicate_owner_invalid")
        digests.append(digest)
        detections += int(commitment.get("primary_detection") is True)
        biases.append(float.fromhex(str(commitment.get("bias_float_hex"))))
        interval = commitment.get("primary_interval")
        if not isinstance(interval, Mapping):
            raise IncrementFixtureError("increment_fixture_replicate_owner_invalid")
        lower = float.fromhex(str(interval.get("lower_float_hex")))
        upper = float.fromhex(str(interval.get("upper_float_hex")))
        covered += int(lower <= cell.analytic_target_bits_per_issue <= upper)
        standard_error = float.fromhex(
            str(commitment.get("primary_standard_error_float_hex"))
        )
        mde = float.fromhex(str(commitment.get("primary_mde_float_hex")))
        mde_complete &= (
            math.isfinite(standard_error)
            and standard_error > 0.0
            and math.isfinite(mde)
            and mde >= 0.0
        )
    detection_rate = detections / REPLICATES_PER_CELL
    coverage_rate = covered / REPLICATES_PER_CELL
    mean_bias = abs(neumaier_mean(biases))
    wilson_upper = _wilson_upper(detections, REPLICATES_PER_CELL)
    common_pass = (
        mean_bias <= 0.0025
        and 0.925 <= coverage_rate <= 0.975
        and mde_complete
    )
    if cell.cell_index in {0, 1}:
        threshold_pass = common_pass and detection_rate >= 0.95
    elif 2 <= cell.cell_index <= 7:
        threshold_pass = (
            common_pass and detection_rate <= 0.075 and wilson_upper <= 0.09
        )
    elif cell.cell_index in {10, 11}:
        threshold_pass = common_pass and detection_rate >= 0.8
    elif cell.cell_index in {12, 13}:
        threshold_pass = common_pass and detection_rate >= 0.95
    else:
        threshold_pass = common_pass
    prefix = "temporal" if _branch(branch_id) == TEMPORAL_BRANCH_ID else "joint"
    coordinate_owner = {
        "branch_id": branch_id,
        "cell_index": cell.cell_index,
        "cell_id": cell.cell_id,
        "ordered_replicate_evidence_digests": digests,
    }
    coordinate_digest = _domain_digest(
        coordinate_owner,
        domain=f"dehps.m4.v2.{prefix}.synthetic-health.cell-coordinate-chain.v2",
    )
    summary: dict[str, Any] = {
        "cell_index": cell.cell_index,
        "cell_id": cell.cell_id,
        "scenario_id": cell.fixture_id,
        "truth_effect_bits_per_issue": cell.analytic_target_bits_per_issue,
        "horizon": cell.horizon_id,
        "replicate_count": REPLICATES_PER_CELL,
        "detection_count": detections,
        "detection_rate": detection_rate,
        "wilson_upper_95": wilson_upper,
        "mean_bias_bits_per_issue": mean_bias,
        "coverage_rate": coverage_rate,
        "mde_complete": bool(mde_complete),
        "threshold_pass": bool(threshold_pass),
        "coordinate_chain_digest": coordinate_digest,
    }
    summary["cell_summary_digest"] = _domain_digest(
        summary, domain=f"dehps.m4.v2.{prefix}.health-cell-summary.v2"
    )
    return summary


def neumaier_mean(values: Sequence[float] | np.ndarray) -> float:
    data = _checked_values(values)
    total = 0.0
    compensation = 0.0
    for raw in data:
        value = float(raw)
        updated = total + value
        if abs(total) >= abs(value):
            compensation += (total - updated) + value
        else:
            compensation += (value - updated) + total
        total = updated
    result = (total + compensation) / int(data.size)
    if not math.isfinite(result):
        raise IncrementFixtureError("increment_fixture_mean_nonfinite")
    return result


def solve_temporal_local_theta(target_bits_per_issue: float) -> float:
    target = _local_target(target_bits_per_issue)
    lower = 0.0
    upper = 8.0
    if temporal_overlap_truth_bits(upper) < target:
        raise IncrementFixtureError("increment_fixture_temporal_calibration_bracket")
    for _ in range(200):
        midpoint = (lower + upper) / 2.0
        value = temporal_overlap_truth_bits(midpoint)
        if abs(value - target) <= 1e-12:
            return midpoint
        if value < target:
            lower = midpoint
        else:
            upper = midpoint
        if upper - lower <= 1e-12:
            candidates = (lower, upper)
            return min(candidates, key=lambda item: (abs(temporal_overlap_truth_bits(item) - target), item))
    raise IncrementFixtureError("increment_fixture_temporal_calibration_failed")


def solve_joint_local_eta(target_bits_per_issue: float) -> float:
    target = _local_target(target_bits_per_issue)
    lower = 0.0
    upper = 1.0 - 2.0**-40
    if joint_is4_truth_bits(upper) < target:
        raise IncrementFixtureError("increment_fixture_joint_calibration_bracket")
    for _ in range(256):
        midpoint = (lower + upper) / 2.0
        value = joint_is4_truth_bits(midpoint)
        if abs(value - target) <= 1e-12:
            return midpoint
        if value < target:
            lower = midpoint
        else:
            upper = midpoint
        if upper - lower <= 1e-12:
            candidates = (lower, upper)
            return min(candidates, key=lambda item: (abs(joint_is4_truth_bits(item) - target), item))
    raise IncrementFixtureError("increment_fixture_joint_calibration_failed")


def temporal_overlap_truth_bits(theta: float) -> float:
    if not math.isfinite(theta) or theta < 0.0:
        raise IncrementFixtureError("increment_fixture_theta_invalid")
    masses = _overlap_masses(theta)
    expected_overlap = math.fsum(index * mass for index, mass in enumerate(masses))
    q_in = expected_overlap / 6.0
    q_out = (DRAW_SIZE - expected_overlap) / 27.0
    return _binary_composite_kl(q_in, q_out)


def joint_is4_truth_bits(eta: float) -> float:
    if not math.isfinite(eta) or not 0.0 <= eta < 1.0:
        raise IncrementFixtureError("increment_fixture_eta_invalid")
    base = _group_count_masses(1.0)
    total = 0.0
    for sign in (-1.0, 1.0):
        for mass, weight in zip(base, IS4_WEIGHTS, strict=True):
            ratio = 1.0 + sign * eta * weight
            if ratio <= 0.0:
                raise IncrementFixtureError("increment_fixture_is4_probability_invalid")
            total += 0.5 * float(mass) * ratio * math.log2(ratio)
    if not math.isfinite(total) or total < -1e-15:
        raise IncrementFixtureError("increment_fixture_joint_truth_invalid")
    return max(0.0, total)


def _fixture_truth(branch_id: str, fixture_id: str) -> float:
    if branch_id == TEMPORAL_BRANCH_ID and fixture_id == T1_FIXTURE_ID:
        return temporal_overlap_truth_bits(math.log(2.0))
    if branch_id == JOINT_BRANCH_ID and fixture_id == J1_FIXTURE_ID:
        return joint_is4_truth_bits(0.5)
    return 0.0


def _checked_scoring_sequence(
    draws: np.ndarray, evaluation_issue_count: int
) -> np.ndarray:
    checked = _checked_draws(draws)
    if (
        isinstance(evaluation_issue_count, bool)
        or not isinstance(evaluation_issue_count, int)
        or evaluation_issue_count <= 0
        or checked.shape[0] - evaluation_issue_count != MINIMUM_TRAINING_ISSUES
    ):
        raise IncrementFixtureError("increment_fixture_training_boundary_invalid")
    return checked


def _temporal_transition_rows(draws: np.ndarray) -> list[dict[str, Any]]:
    counts = np.zeros(NUMBER_COUNT, dtype=np.int64)
    counts[draws[0].astype(np.int64) - 1] += 1
    rows: list[dict[str, Any]] = []
    for ordinal in range(2, draws.shape[0] + 1):
        target_marginals = tuple(
            float(value) for value in (counts + UNIFORM_MARGINAL) / ordinal
        )
        solution = solve_fixed_cardinality_maximum_entropy(target_marginals)
        previous = tuple(int(value) - 1 for value in draws[ordinal - 2])
        actual = tuple(int(value) - 1 for value in draws[ordinal - 1])
        coefficients = overlap_coefficient_masses(solution.weights, previous)
        rows.append(
            {
                "evaluation_ordinal": ordinal,
                "base_weights": solution.weights,
                "base_partition": solution.partition,
                "previous_state": previous,
                "actual_state": actual,
                "coefficient_masses": coefficients,
                "observed_overlap": len(set(previous).intersection(actual)),
            }
        )
        counts[draws[ordinal - 1].astype(np.int64) - 1] += 1
    return rows


def _is4_projected_direction(
    weights: Sequence[float], *, history_sign: float, actual_state: Sequence[int]
) -> dict[str, Any]:
    w = tuple(float(value) for value in weights)
    marginals = np.asarray(fixed_cardinality_marginals(w), dtype=np.float64)
    pair = np.zeros((NUMBER_COUNT, NUMBER_COUNT), dtype=np.float64)
    np.fill_diagonal(pair, marginals)
    partition = _elementary(w, DRAW_SIZE)
    for left in range(NUMBER_COUNT):
        for right in range(left + 1, NUMBER_COUNT):
            remaining = w[:left] + w[left + 1 : right] + w[right + 1 :]
            value = w[left] * w[right] * _elementary(remaining, 4) / partition
            pair[left, right] = pair[right, left] = value
    feature_mean, feature_singletons = _feature_moments(w, history_sign, partition)
    gram = np.empty((33, 33), dtype=np.float64)
    gram[0, 0] = 1.0
    gram[0, 1:] = gram[1:, 0] = marginals[:32]
    gram[1:, 1:] = pair[:32, :32]
    rhs = np.concatenate(([feature_mean], feature_singletons[:32]))
    try:
        coefficients = np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError as exc:
        raise IncrementFixtureError("increment_fixture_joint_projection_failed") from exc
    if not np.all(np.isfinite(coefficients)):
        raise IncrementFixtureError("increment_fixture_joint_projection_failed")
    scale = _projection_scale(coefficients, history_sign)
    actual_k = sum(index < 16 for index in actual_state)
    projected = coefficients[0] + sum(
        coefficients[index + 1] for index in actual_state if index < 32
    )
    actual_z = (history_sign * IS4_WEIGHTS[actual_k] - projected) / scale
    return {
        "coefficients": tuple(float(value) for value in coefficients),
        "scale": scale,
        "actual_z": actual_z,
    }


def _feature_moments(
    weights: tuple[float, ...], history_sign: float, partition: float
) -> tuple[float, np.ndarray]:
    singleton = np.empty(NUMBER_COUNT, dtype=np.float64)
    total = 0.0
    for group_count in range(7):
        mass = (
            _elementary(weights[:16], group_count)
            * _elementary(weights[16:], 6 - group_count)
        )
        total += history_sign * IS4_WEIGHTS[group_count] * mass
    for held in range(NUMBER_COUNT):
        rest_a = weights[:16]
        rest_b = weights[16:]
        if held < 16:
            rest_a = weights[:held] + weights[held + 1 : 16]
        else:
            rest_b = weights[16:held] + weights[held + 1 :]
            if len(rest_b) != 16:
                raise IncrementFixtureError("increment_fixture_joint_projection_failed")
        value = 0.0
        for remainder_a in range(6):
            selected_a = remainder_a + int(held < 16)
            value += (
                history_sign
                * IS4_WEIGHTS[selected_a]
                * _elementary(rest_a, remainder_a)
                * _elementary(rest_b, 5 - remainder_a)
            )
        singleton[held] = weights[held] * value / partition
    return total / partition, singleton


def _elementary(weights: Sequence[float], degree: int) -> float:
    if degree < 0 or degree > len(weights):
        return 0.0
    values = [0.0] * (degree + 1)
    values[0] = 1.0
    for weight in weights:
        for index in range(degree, 0, -1):
            values[index] += values[index - 1] * float(weight)
    return values[degree]


def _projection_scale(coefficients: np.ndarray, history_sign: float) -> float:
    maximum = 0.0
    for count_a in range(7):
        count_b = 6 - count_a
        for choose_largest in (False, True):
            selected: list[float] = []
            for start, stop, count in ((0, 16, count_a), (16, 33, count_b)):
                candidates = [
                    (float(coefficients[index + 1]) if index < 32 else 0.0, index)
                    for index in range(start, stop)
                ]
                candidates.sort(key=lambda item: (item[0], item[1]))
                if choose_largest:
                    candidates = candidates[-count:] if count else []
                else:
                    candidates = candidates[:count]
                selected.extend(value for value, _ in candidates)
            residual = history_sign * IS4_WEIGHTS[count_a] - coefficients[0] - math.fsum(selected)
            maximum = max(maximum, abs(residual))
    if not math.isfinite(maximum) or maximum <= 0.0:
        raise IncrementFixtureError("increment_fixture_joint_projection_scale_invalid")
    return maximum


def _solve_eta_root(values: Sequence[float]) -> float:
    z = np.asarray(values, dtype=np.float64)
    if z.size == 0 or not np.all(np.isfinite(z)) or np.max(np.abs(z)) > 1.0 + 1e-10:
        raise IncrementFixtureError("increment_fixture_eta_observations_invalid")

    def score(eta: float) -> float:
        return math.fsum(float(value) / (1.0 + eta * float(value)) for value in z)

    if abs(score(0.0)) <= 1e-12:
        return 0.0
    lower = -1.0 + 1e-12
    upper = 1.0 - 1e-12
    left = score(lower)
    right = score(upper)
    if not (left > 0.0 > right):
        raise IncrementFixtureError("increment_fixture_eta_root_not_finite")
    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        current = score(midpoint)
        if abs(current) <= 1e-12 or upper - lower <= 1e-12:
            return round(midpoint, 12)
        if current > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    raise IncrementFixtureError("increment_fixture_eta_solver_not_converged")


def _append_scored_owner(
    prediction_rows: list[dict[str, Any]],
    score_rows: list[dict[str, Any]],
    scores: list[float],
    *,
    prediction: dict[str, Any],
    score: float,
    actual_state: Sequence[int],
    branch_id: str,
) -> None:
    prefix = "temporal" if branch_id == TEMPORAL_BRANCH_ID else "joint"
    prediction["prediction_checkpoint_digest"] = _domain_digest(
        prediction, domain=f"dehps.m4.v2.{prefix}.synthetic-health.prediction-checkpoint.v2"
    )
    outcome = {
        "evaluation_ordinal": prediction["evaluation_ordinal"],
        "selected_labels": [int(value) + 1 for value in actual_state],
    }
    score_row = {
        "evaluation_ordinal": prediction["evaluation_ordinal"],
        "prediction_checkpoint_digest": prediction["prediction_checkpoint_digest"],
        "settled_outcome_digest": _domain_digest(
            outcome, domain="dehps.m4.v2.synthetic-legal-outcome.v1"
        ),
        "score_float_hex": float(score).hex(),
    }
    score_row["score_row_digest"] = _domain_digest(
        score_row, domain=f"dehps.m4.v2.{prefix}.synthetic-health.score-row.v2"
    )
    prediction_rows.append(prediction)
    score_rows.append(score_row)
    scores.append(float(score))


def _sequence_score_result(
    *,
    branch_id: str,
    prediction_rows: list[dict[str, Any]],
    score_rows: list[dict[str, Any]],
    scores: list[float],
) -> IncrementSequenceScores:
    if not prediction_rows:
        raise IncrementFixtureError("increment_fixture_no_evaluation_rows")
    prefix = "temporal" if branch_id == TEMPORAL_BRANCH_ID else "joint"
    prediction_digests = [row["prediction_checkpoint_digest"] for row in prediction_rows]
    score_digests = [row["score_row_digest"] for row in score_rows]
    return IncrementSequenceScores(
        branch_id=branch_id,
        evaluation_range=(prediction_rows[0]["evaluation_ordinal"], prediction_rows[-1]["evaluation_ordinal"]),
        prediction_owner_material=tuple(prediction_rows),
        score_owner_material=tuple(score_rows),
        score_values=tuple(scores),
        prediction_checkpoint_chain_digest=_domain_digest(
            {"ordered_prediction_checkpoint_digests": prediction_digests},
            domain=f"dehps.m4.v2.{prefix}.synthetic-health.prediction-checkpoint-chain.v2",
        ),
        score_row_chain_digest=_domain_digest(
            {"ordered_score_row_digests": score_digests},
            domain=f"dehps.m4.v2.{prefix}.synthetic-health.score-chain.v2",
        ),
    )


def _local_target(value: float) -> float:
    if isinstance(value, bool) or value not in LOCAL_TARGETS:
        raise IncrementFixtureError("increment_fixture_local_target_invalid")
    return float(value)


def _historical_scheme_block_length(scheme_id: str) -> int:
    for length in (3, 5, 8, 13):
        if (
            scheme_id == f"MOVING_BLOCK_NONCIRCULAR_LENGTH_{length}_PRIMARY"
            or scheme_id
            == f"MOVING_BLOCK_NONCIRCULAR_LENGTH_{length}_SENSITIVITY"
            or scheme_id
            == f"STATIONARY_EXPECTED_LENGTH_{length}_SENSITIVITY"
        ):
            return length
    raise IncrementFixtureError("increment_fixture_historical_scheme_invalid")


def _wilson_upper(successes: int, total: int) -> float:
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return center + radius


def _overlap_masses(theta: float) -> np.ndarray:
    raw = np.asarray(
        [
            comb(6, overlap)
            * comb(27, DRAW_SIZE - overlap)
            * math.exp(theta * overlap)
            for overlap in range(DRAW_SIZE + 1)
        ],
        dtype=np.float64,
    )
    return _normalized_masses(raw)


def _generate_overlap_markov(
    issue_count: int,
    evaluation_count: int,
    theta: float,
    rng: np.random.Generator,
    *,
    lexicographic_initial: bool,
) -> tuple[np.ndarray, np.ndarray]:
    if issue_count - evaluation_count != MINIMUM_TRAINING_ISSUES:
        raise IncrementFixtureError("increment_fixture_training_boundary_invalid")
    draws = np.empty((issue_count, DRAW_SIZE), dtype=np.int8)
    draws[0] = (
        _uniform_legal_draw(rng)
        if lexicographic_initial
        else _generate_group_iid(1, 1.0, rng)[0]
    )
    truth = np.empty((evaluation_count, NUMBER_COUNT), dtype=np.float64)
    masses = _overlap_masses(theta)
    expected_overlap = float(np.dot(np.arange(7, dtype=np.float64), masses))
    q_in = expected_overlap / 6.0
    q_out = (DRAW_SIZE - expected_overlap) / 27.0
    numbers = np.arange(1, NUMBER_COUNT + 1, dtype=np.int8)
    for issue_index in range(1, issue_count):
        previous = draws[issue_index - 1]
        overlap = int(rng.choice(DRAW_SIZE + 1, p=masses))
        inside = (
            np.empty(0, dtype=np.int8)
            if overlap == 0
            else rng.choice(previous, size=overlap, replace=False)
        )
        mask = np.ones(NUMBER_COUNT, dtype=bool)
        mask[previous.astype(np.int64) - 1] = False
        outside_count = DRAW_SIZE - overlap
        outside = (
            np.empty(0, dtype=np.int8)
            if outside_count == 0
            else rng.choice(numbers[mask], size=outside_count, replace=False)
        )
        draws[issue_index] = np.sort(np.concatenate((inside, outside)))
        if issue_index >= MINIMUM_TRAINING_ISSUES:
            row = truth[issue_index - MINIMUM_TRAINING_ISSUES]
            row.fill(q_out)
            row[previous.astype(np.int64) - 1] = q_in
    _checked_draws(draws)
    return draws, truth


def _generate_is4_markov(
    issue_count: int,
    eta: float,
    rng: np.random.Generator,
    *,
    lexicographic_initial: bool,
) -> np.ndarray:
    if not 0.0 <= eta < 1.0 or not math.isfinite(eta):
        raise IncrementFixtureError("increment_fixture_eta_invalid")
    draws = np.empty((issue_count, DRAW_SIZE), dtype=np.int8)
    draws[0] = (
        _uniform_legal_draw(rng)
        if lexicographic_initial
        else _generate_group_iid(1, 1.0, rng)[0]
    )
    base = _group_count_masses(1.0)
    signed_rows = {
        sign: np.asarray(
            [
                base[index] * (1.0 + sign * eta * IS4_WEIGHTS[index])
                for index in range(DRAW_SIZE + 1)
            ],
            dtype=np.float64,
        )
        for sign in (-1, 1)
    }
    if any(
        np.any(row <= 0.0)
        or not np.all(np.isfinite(row))
        or abs(float(np.sum(row)) - 1.0) > 1e-14
        for row in signed_rows.values()
    ):
        raise IncrementFixtureError("increment_fixture_is4_probability_invalid")
    group_a = np.arange(1, 17, dtype=np.int8)
    group_b = np.arange(17, 34, dtype=np.int8)
    for issue_index in range(1, issue_count):
        previous = tuple(int(value) for value in draws[issue_index - 1])
        sign = -1 if previous <= LEXICOGRAPHIC_HALF_BOUNDARY else 1
        group_count = int(rng.choice(DRAW_SIZE + 1, p=signed_rows[sign]))
        left = (
            rng.choice(group_a, size=group_count, replace=False)
            if group_count
            else group_a[:0]
        )
        right_count = DRAW_SIZE - group_count
        right = (
            rng.choice(group_b, size=right_count, replace=False)
            if right_count
            else group_b[:0]
        )
        draws[issue_index] = np.sort(np.concatenate((left, right)))
    return _checked_draws(draws)


def _generate_group_iid(
    issue_count: int, odds: float, rng: np.random.Generator
) -> np.ndarray:
    if issue_count <= 0:
        raise IncrementFixtureError("increment_fixture_issue_count_invalid")
    masses = _group_count_masses(odds)
    counts = rng.choice(DRAW_SIZE + 1, size=issue_count, p=masses)
    draws = np.empty((issue_count, DRAW_SIZE), dtype=np.int8)
    group_a = np.arange(1, 17, dtype=np.int8)
    group_b = np.arange(17, 34, dtype=np.int8)
    for group_count in range(DRAW_SIZE + 1):
        rows = np.flatnonzero(counts == group_count)
        if rows.size == 0:
            continue
        left = _uniform_row_subsets(group_a, rows.size, group_count, rng)
        right = _uniform_row_subsets(
            group_b, rows.size, DRAW_SIZE - group_count, rng
        )
        draws[rows] = np.sort(np.concatenate((left, right), axis=1), axis=1)
    return _checked_draws(draws)


def _group_count_masses(odds: float) -> np.ndarray:
    if not math.isfinite(odds) or odds <= 0.0:
        raise IncrementFixtureError("increment_fixture_odds_invalid")
    raw = np.asarray(
        [
            comb(16, count) * comb(17, DRAW_SIZE - count) * odds**count
            for count in range(DRAW_SIZE + 1)
        ],
        dtype=np.float64,
    )
    return _normalized_masses(raw)


def _normalized_masses(raw: np.ndarray) -> np.ndarray:
    total = float(np.sum(raw))
    if not np.all(np.isfinite(raw)) or np.any(raw < 0.0) or total <= 0.0:
        raise IncrementFixtureError("increment_fixture_probability_mass_invalid")
    values = raw / total
    if abs(float(np.sum(values)) - 1.0) > 1e-14:
        raise IncrementFixtureError("increment_fixture_probability_mass_invalid")
    return values


def _uniform_row_subsets(
    values: np.ndarray,
    row_count: int,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if size == 0:
        return np.empty((row_count, 0), dtype=np.int8)
    keys = rng.random((row_count, values.size))
    positions = np.argpartition(keys, size - 1, axis=1)[:, :size]
    return values[positions]


def _uniform_legal_draw(rng: np.random.Generator) -> np.ndarray:
    rank = int(rng.integers(0, LEGAL_COMBINATION_COUNT))
    output: list[int] = []
    smallest = 1
    for position in range(DRAW_SIZE):
        remaining = DRAW_SIZE - position - 1
        maximum = NUMBER_COUNT - remaining
        for candidate in range(smallest, maximum + 1):
            suffix_count = comb(NUMBER_COUNT - candidate, remaining)
            if rank < suffix_count:
                output.append(candidate)
                smallest = candidate + 1
                break
            rank -= suffix_count
        else:  # pragma: no cover - guarded by the exact legal rank bound
            raise IncrementFixtureError("increment_fixture_lexicographic_rank_invalid")
    return np.asarray(output, dtype=np.int8)


def _uniform_truth(row_count: int) -> np.ndarray:
    return np.full((row_count, NUMBER_COUNT), UNIFORM_MARGINAL, dtype=np.float64)


def _group_truth(row_count: int, odds: float) -> np.ndarray:
    masses = _group_count_masses(odds)
    expected_a = float(np.dot(np.arange(7, dtype=np.float64), masses))
    row = np.concatenate(
        (
            np.full(16, expected_a / 16.0, dtype=np.float64),
            np.full(17, (DRAW_SIZE - expected_a) / 17.0, dtype=np.float64),
        )
    )
    return np.broadcast_to(row, (row_count, NUMBER_COUNT))


def _binary_composite_kl(q_in: float, q_out: float) -> float:
    base = UNIFORM_MARGINAL

    def kl(value: float) -> float:
        return value * math.log2(value / base) + (1.0 - value) * math.log2(
            (1.0 - value) / (1.0 - base)
        )

    result = 6.0 * kl(q_in) + 27.0 * kl(q_out)
    if not math.isfinite(result) or result < -1e-15:
        raise IncrementFixtureError("increment_fixture_temporal_truth_invalid")
    return max(0.0, result)


def _checked_draws(value: np.ndarray) -> np.ndarray:
    draws = np.asarray(value)
    if (
        draws.ndim != 2
        or draws.shape[0] <= 0
        or draws.shape[1] != DRAW_SIZE
        or not np.issubdtype(draws.dtype, np.integer)
        or np.any(draws < 1)
        or np.any(draws > NUMBER_COUNT)
        or np.any(np.diff(draws, axis=1) <= 0)
    ):
        raise IncrementFixtureError("increment_fixture_illegal_draw")
    return draws


def _checked_marginal_rows(value: np.ndarray, *, rows: int) -> np.ndarray:
    marginals = np.asarray(value, dtype=np.float64)
    if (
        marginals.shape != (rows, NUMBER_COUNT)
        or not np.all(np.isfinite(marginals))
        or not np.all((marginals > 0.0) & (marginals < 1.0))
        or float(np.max(np.abs(np.sum(marginals, axis=1) - DRAW_SIZE))) > 1e-11
    ):
        raise IncrementFixtureError("increment_fixture_marginal_rows_invalid")
    return marginals


def _checked_values(value: Sequence[float] | np.ndarray) -> np.ndarray:
    data = np.asarray(value, dtype=np.float64)
    if data.ndim != 1 or data.size == 0 or not np.all(np.isfinite(data)):
        raise IncrementFixtureError("increment_fixture_values_invalid")
    return data


__all__ = [
    "BOOTSTRAP_BLOCK_LENGTHS",
    "BOOTSTRAP_CHILD_COUNT",
    "DRAW_SIZE",
    "JOINT_BRANCH_ID",
    "LEGAL_COMBINATION_COUNT",
    "MINIMUM_TRAINING_ISSUES",
    "PRIMARY_BOOTSTRAP_BLOCK_LENGTH",
    "REPLICATES_PER_CELL",
    "SYNTHETIC_CELL_COUNT",
    "TEMPORAL_BRANCH_ID",
    "IncrementFixtureError",
    "IncrementSequenceScores",
    "SyntheticCell",
    "SyntheticSequence",
    "binary_composite_log_score_difference",
    "build_historical_sensitivity_summary",
    "build_synthetic_health_cell_summary",
    "build_synthetic_health_replicate_evidence",
    "build_temporal_registered_sequence_coordinate",
    "centered_circular_mbb_owner_data",
    "child_seed_full_sha256",
    "circular_centered_mbb_indices",
    "generate_registered_synthetic_sequence",
    "historical_resample_child_seed_full_sha256",
    "historical_resample_mean",
    "historical_resample_owner_data",
    "is4_log_score_difference",
    "iter_health_coordinates",
    "joint_is4_truth_bits",
    "neumaier_mean",
    "pcg64dxsm_generator",
    "score_expanding_marginal_sequence",
    "score_joint_residual_sequence",
    "score_temporal_increment_sequence",
    "solve_joint_local_eta",
    "solve_temporal_local_theta",
    "synthetic_bootstrap_child_seed_full_sha256",
    "synthetic_cells",
    "temporal_overlap_truth_bits",
]
