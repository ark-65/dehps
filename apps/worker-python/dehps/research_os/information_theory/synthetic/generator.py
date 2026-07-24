from __future__ import annotations

from fractions import Fraction
from math import comb

import numpy as np

from .contracts import (
    SyntheticDatasetArtifact,
    SyntheticIssue,
    SyntheticRunManifest,
    SyntheticTruth,
)


def legal_combination_count() -> int:
    return comb(33, 6)


def number_marginal_probability() -> Fraction:
    return Fraction(6, 33)


def pair_marginal_probability() -> Fraction:
    return Fraction(comb(31, 4), comb(33, 6))


def full_combination_probability() -> Fraction:
    return Fraction(1, comb(33, 6))


def _truth() -> SyntheticTruth:
    number = number_marginal_probability()
    pair = pair_marginal_probability()
    full = full_combination_probability()
    return SyntheticTruth(
        scenario_id="NULL_UNIFORM",
        legal_combination_count=legal_combination_count(),
        number_marginal=(number.numerator, number.denominator),
        pair_marginal=(pair.numerator, pair.denominator),
        full_combination_probability=(full.numerator, full.denominator),
    )


def generate_null_dataset(
    manifest: SyntheticRunManifest,
    *,
    scale_id: str,
    seed: int,
    rng: np.random.Generator | None = None,
) -> SyntheticDatasetArtifact:
    scenario = manifest.scenario("NULL_UNIFORM")
    if not scenario.implemented:
        raise ValueError("NULL_UNIFORM is not implemented by this manifest")
    scale = manifest.scale(scale_id)
    normalized_seed = int(seed)
    if normalized_seed not in manifest.seed_policy.seeds:
        raise ValueError("replicate seed is outside the experiment seed policy")
    generator = rng if rng is not None else np.random.default_rng(normalized_seed)
    issues: list[SyntheticIssue] = []
    legal_numbers = np.arange(1, 34, dtype=np.int64)
    for issue_index in range(1, scale.sequence_length + 1):
        numbers = tuple(
            int(value)
            for value in np.sort(
                generator.choice(legal_numbers, size=6, replace=False)
            )
        )
        target = tuple(1 if number in numbers else 0 for number in range(1, 34))
        red_mask = sum(1 << (number - 1) for number in numbers)
        issues.append(
            SyntheticIssue(
                issue_index=issue_index,
                red_mask=red_mask,
                sorted_red_numbers=numbers,
                target_vector=target,
            )
        )
    payload = manifest.payload
    return SyntheticDatasetArtifact(
        scenario=scenario,
        scale=scale,
        truth=_truth(),
        seed_policy=manifest.seed_policy,
        replicate_seed=normalized_seed,
        issues=tuple(issues),
        preregistration_digest=str(payload["preregistration_digest"]),
        decision_policy_digest=str(payload["decision_policy_digest"]),
        config_digest=manifest.artifact_digest,
    )
