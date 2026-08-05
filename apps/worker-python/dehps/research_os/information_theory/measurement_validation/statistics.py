from __future__ import annotations

from collections.abc import Callable, Sequence
from math import fsum, isfinite, sqrt
from statistics import NormalDist
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.resampling.contracts import (
    ResamplingError,
    ResamplingKernelManifest,
)
from dehps.research_os.information_theory.resampling.plans import (
    block_permutation_plan,
    moving_block_plan,
)
from dehps.research_os.information_theory.resampling.statistics import (
    plus_one_p_value,
)
from dehps.research_os.information_theory.seed_domains import derive_m4_p2_seed

PRIMARY_BLOCK_SIZE = 5
CONFIDENCE_LEVEL = 0.95
ALPHA = 0.05
NORMAL = NormalDist()


def _finite(values: Sequence[float], *, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size == 0 or not np.isfinite(result).all():
        raise ResamplingError("nan_statistic", f"{name} must be a finite vector")
    return result


def type7_quantile(values: Sequence[float], probability: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0,1]")
    clean = _finite(values, name="quantile values")
    return float(np.quantile(clean, probability, method="linear"))


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    if not p_values:
        raise ValueError("Holm family cannot be empty")
    if any(
        not isfinite(value) or value < 0.0 or value > 1.0 for value in p_values.values()
    ):
        raise ValueError("p-values must be finite and in [0,1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    family_size = len(ordered)
    adjusted: dict[str, float] = {}
    previous = 0.0
    for rank, (key, value) in enumerate(ordered):
        candidate = min(1.0, (family_size - rank) * value)
        previous = max(previous, candidate)
        adjusted[key] = previous
    return {key: adjusted[key] for key in sorted(adjusted)}


def wilson_interval(
    positive_count: int,
    total_count: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if total_count < 1 or positive_count < 0 or positive_count > total_count:
        raise ValueError("invalid binomial counts")
    proportion = positive_count / total_count
    denominator = 1.0 + z * z / total_count
    center = (proportion + z * z / (2.0 * total_count)) / denominator
    half_width = (
        z
        * sqrt(
            proportion * (1.0 - proportion) / total_count
            + z * z / (4.0 * total_count * total_count)
        )
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def delete_contiguous_block_jackknife(
    issue_statistics: Sequence[float],
    *,
    block_size: int = PRIMARY_BLOCK_SIZE,
) -> tuple[float, ...]:
    values = _finite(issue_statistics, name="issue statistics")
    if block_size < 1 or values.size <= block_size:
        raise ResamplingError(
            "insufficient_issues_for_block_size",
            "delete-block jackknife requires N > L >= 1",
        )
    total = float(values.sum())
    retained = values.size - block_size
    result = [
        (total - float(values[start : start + block_size].sum())) / retained
        for start in range(values.size - block_size + 1)
    ]
    return tuple(result)


def bca_interval(
    *,
    observed: float,
    bootstrap_statistics: Sequence[float],
    jackknife_statistics: Sequence[float],
) -> dict[str, Any]:
    if not isfinite(observed):
        raise ResamplingError("nan_statistic", "observed statistic must be finite")
    bootstrap = _finite(bootstrap_statistics, name="bootstrap statistics")
    jackknife = _finite(jackknife_statistics, name="jackknife statistics")
    replicate_count = int(bootstrap.size)
    failures: list[str] = []

    less = int(np.count_nonzero(bootstrap < observed))
    equal = int(np.count_nonzero(bootstrap == observed))
    mid_tie = (less + 0.5 * equal) / replicate_count
    if not 0.0 < mid_tie < 1.0:
        failures.append("mid_tie_bootstrap_proportion_not_strictly_inside_zero_one")

    jackknife_mean = float(jackknife.mean())
    differences = jackknife_mean - jackknife
    denominator = 6.0 * float(np.sum(differences * differences)) ** 1.5
    acceleration = (
        float(np.sum(differences * differences * differences)) / denominator
        if isfinite(denominator) and denominator > 0.0
        else float("nan")
    )
    if not isfinite(acceleration):
        failures.append("jackknife_acceleration_denominator_nonfinite_or_zero")

    adjusted: tuple[float, float] | None = None
    if not failures:
        z0 = NORMAL.inv_cdf(mid_tie)
        raw: list[float] = []
        for probability in (0.025, 0.975):
            z_alpha = NORMAL.inv_cdf(probability)
            transform_denominator = 1.0 - acceleration * (z0 + z_alpha)
            if not isfinite(transform_denominator) or transform_denominator == 0.0:
                raw.append(float("nan"))
            else:
                raw.append(NORMAL.cdf(z0 + (z0 + z_alpha) / transform_denominator))
        lower_bound = 1.0 / (replicate_count + 1.0)
        upper_bound = replicate_count / (replicate_count + 1.0)
        if (
            not all(isfinite(value) for value in raw)
            or raw[0] > raw[1]
            or raw[0] < lower_bound
            or raw[1] > upper_bound
        ):
            failures.append("adjusted_probabilities_invalid_or_outside_frozen_bounds")
        else:
            adjusted = (raw[0], raw[1])

    if failures:
        lower_probability, upper_probability = 0.025, 0.975
        method = "two_sided_percentile"
        fallback_reason = failures
    else:
        assert adjusted is not None
        lower_probability, upper_probability = adjusted
        method = "moving_block_bootstrap_BCa"
        fallback_reason = []

    lower = type7_quantile(bootstrap, lower_probability)
    upper = type7_quantile(bootstrap, upper_probability)
    return {
        "method": method,
        "confidence_level": CONFIDENCE_LEVEL,
        "lower": lower,
        "upper": upper,
        "lower_probability": lower_probability,
        "upper_probability": upper_probability,
        "bootstrap_replicates": replicate_count,
        "jackknife_replicates": int(jackknife.size),
        "bias_correction_mid_tie_proportion": mid_tie,
        "acceleration": acceleration if isfinite(acceleration) else None,
        "fallback_used": bool(failures),
        "fallback_reason": fallback_reason,
        "quantile_method": "Hyndman-Fan_type_7",
    }


def moving_block_bootstrap_statistics(
    issue_statistics: Sequence[float],
    *,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    parent_run_digest: str,
    replicate_count: int,
    block_size: int = PRIMARY_BLOCK_SIZE,
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    values = _finite(issue_statistics, name="issue statistics")
    statistics: list[float] = []
    seed_digests: list[str] = []
    for replicate_index in range(replicate_count):
        plan = moving_block_plan(
            int(values.size),
            block_size=block_size,
            manifest=manifest,
            scenario_id=scenario_id,
            replicate_index=replicate_index,
            parent_run_digest=parent_run_digest,
        )
        statistics.append(float(values[np.asarray(plan.source_indices)].mean()))
        assert plan.seed_digest is not None
        seed_digests.append(plan.seed_digest)
    if len(set(seed_digests)) != replicate_count:
        raise ResamplingError("duplicate_seed", "bootstrap seed set is not unique")
    return tuple(statistics), tuple(seed_digests)


def block_permutation_statistics(
    *,
    issue_count: int,
    statistic_for_indices: Callable[[tuple[int, ...]], float],
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    parent_run_digest: str,
    replicate_count: int,
    block_size: int = PRIMARY_BLOCK_SIZE,
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    statistics: list[float] = []
    seed_digests: list[str] = []
    for replicate_index in range(replicate_count):
        plan = block_permutation_plan(
            issue_count,
            block_size=block_size,
            manifest=manifest,
            scenario_id=scenario_id,
            replicate_index=replicate_index,
            parent_run_digest=parent_run_digest,
        )
        value = float(statistic_for_indices(plan.source_indices))
        if not isfinite(value):
            raise ResamplingError(
                "nan_statistic", "permutation statistic is non-finite"
            )
        statistics.append(value)
        assert plan.seed_digest is not None
        seed_digests.append(plan.seed_digest)
    if len(set(seed_digests)) != replicate_count:
        raise ResamplingError("duplicate_seed", "permutation seed set is not unique")
    return tuple(statistics), tuple(seed_digests)


def _runtime_rng_and_seed_digest(
    *,
    manifest: ResamplingKernelManifest,
    seed_domain: str,
    scenario_id: str,
    method_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> tuple[np.random.Generator, str]:
    derived = derive_m4_p2_seed(
        root_seed_set_digest=manifest.root_seed_set_digest,
        seed_domain=seed_domain,
        scenario_id=scenario_id,
        method_id=method_id,
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    return np.random.default_rng(int(derived["seed"])), str(derived["seed_digest"])


def moving_block_bootstrap_statistics_exact_runtime(
    issue_statistics: Sequence[float],
    *,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    parent_run_digest: str,
    replicate_count: int,
    block_size: int = PRIMARY_BLOCK_SIZE,
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    """Exact bootstrap without constructing unused immutable plan artifacts."""

    values = _finite(issue_statistics, name="issue statistics")
    issue_count = int(values.size)
    if issue_count < block_size or block_size < 1:
        raise ResamplingError(
            "insufficient_issues_for_block_size",
            "non-circular moving block requires N >= L >= 1",
        )
    statistics: list[float] = []
    seed_digests: list[str] = []
    for replicate_index in range(replicate_count):
        rng, seed_digest = _runtime_rng_and_seed_digest(
            manifest=manifest,
            seed_domain="M4_P2_BOOTSTRAP",
            scenario_id=scenario_id,
            method_id=f"moving_block_L{block_size}",
            replicate_index=replicate_index,
            parent_run_digest=parent_run_digest,
        )
        block_count = (issue_count + block_size - 1) // block_size
        starts = rng.integers(
            0,
            issue_count - block_size + 1,
            size=block_count,
        )
        indices = (
            starts[:, None] + np.arange(block_size, dtype=np.int64)[None, :]
        ).reshape(-1)[:issue_count]
        statistics.append(float(values[indices].mean()))
        seed_digests.append(seed_digest)
    if len(set(seed_digests)) != replicate_count:
        raise ResamplingError("duplicate_seed", "bootstrap seed set is not unique")
    return tuple(statistics), tuple(seed_digests)


def block_permutation_statistics_exact_runtime(
    *,
    issue_count: int,
    statistic_for_indices: Callable[[Sequence[int]], float],
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    parent_run_digest: str,
    replicate_count: int,
    block_size: int = PRIMARY_BLOCK_SIZE,
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    """Exact block permutations without hashing unused full plan payloads."""

    block_count = (issue_count + block_size - 1) // block_size
    if block_count < 2:
        raise ResamplingError(
            "insufficient_blocks_for_permutation",
            "block permutation requires at least two blocks",
        )
    identity_order = np.arange(block_count, dtype=np.int64)
    padded_blocks = (
        identity_order[:, None] * block_size
        + np.arange(block_size, dtype=np.int64)[None, :]
    )
    padded_blocks[padded_blocks >= issue_count] = -1
    statistics: list[float] = []
    seed_digests: list[str] = []
    for replicate_index in range(replicate_count):
        rng, seed_digest = _runtime_rng_and_seed_digest(
            manifest=manifest,
            seed_domain="M4_P2_ISSUE_PERMUTATION",
            scenario_id=scenario_id,
            method_id=f"block_permutation_L{block_size}",
            replicate_index=replicate_index,
            parent_run_digest=parent_run_digest,
        )
        for _ in range(32):
            order = rng.permutation(block_count)
            if not np.array_equal(order, identity_order):
                break
        else:
            raise ResamplingError(
                "identity_permutation_forbidden",
                "could not draw non-identity block order",
            )
        flattened = padded_blocks[order].reshape(-1)
        indices = flattened[flattened >= 0]
        value = float(statistic_for_indices(indices))
        if not isfinite(value):
            raise ResamplingError(
                "nan_statistic", "permutation statistic is non-finite"
            )
        statistics.append(value)
        seed_digests.append(seed_digest)
    if len(set(seed_digests)) != replicate_count:
        raise ResamplingError("duplicate_seed", "permutation seed set is not unique")
    return tuple(statistics), tuple(seed_digests)


def primary_inference(
    *,
    pe1_issue_statistics: Sequence[float],
    permutation_null_statistics: Sequence[float],
    bootstrap_statistics: Sequence[float],
) -> dict[str, Any]:
    issue_values = _finite(pe1_issue_statistics, name="PE1 issue statistics")
    null_values = _finite(
        permutation_null_statistics,
        name="permutation null statistics",
    )
    bootstrap = _finite(bootstrap_statistics, name="bootstrap statistics")
    pe1 = float(issue_values.mean())
    null_center = float(null_values.mean())
    pe2 = pe1 - null_center

    pe1_jackknife = delete_contiguous_block_jackknife(issue_values)
    pe2_jackknife = tuple(value - null_center for value in pe1_jackknife)
    pe1_interval = bca_interval(
        observed=pe1,
        bootstrap_statistics=bootstrap,
        jackknife_statistics=pe1_jackknife,
    )
    pe2_interval = bca_interval(
        observed=pe2,
        bootstrap_statistics=bootstrap - null_center,
        jackknife_statistics=pe2_jackknife,
    )

    raw_p = {
        "PE1": plus_one_p_value(pe1, null_values, tail="upper"),
        "PE2": plus_one_p_value(
            pe2,
            null_values - null_center,
            tail="upper",
        ),
    }
    adjusted = holm_adjust(raw_p)
    positive = (
        adjusted["PE1"] <= ALPHA
        and adjusted["PE2"] <= ALPHA
        and pe1_interval["lower"] > 0.0
        and pe2_interval["lower"] > 0.0
    )
    return {
        "PE1": pe1,
        "permutation_null_center": null_center,
        "PE2": pe2,
        "confidence_intervals": {
            "PE1": pe1_interval,
            "PE2": pe2_interval,
        },
        "raw_p_values": raw_p,
        "Holm_adjusted_p_values": adjusted,
        "positive_signal_decision": positive,
        "unit": "bits_per_issue",
    }


def seed_set_digest(seed_digests: Sequence[str], *, method: str) -> str:
    if not seed_digests or len(set(seed_digests)) != len(seed_digests):
        raise ResamplingError(
            "incomplete_seed_set",
            f"{method} seed set must be non-empty and unique",
        )
    return canonical_digest(
        list(seed_digests),
        domain=f"dehps.m4-p2.{method}-seed-set.v1",
    )


def mean(values: Sequence[float]) -> float:
    clean = _finite(values, name="mean values")
    return fsum(float(value) for value in clean) / clean.size
